"use strict";
const $ = id => document.getElementById(id);
let ws, state = {}, schema = [], selected = null, sequence = 0, loaded = null;
let reconnect, heartbeat, lastState = 0, shutdownRequested = false;
let queuedCommand = null, queuedLimits = null, queuedZero = null, limitsLoaded = false;
let autoScanNeeded = true, autoControlAfter = 0, wifiState = {}, wifiSignature = "";
let bluetoothState = {}, bluetoothSignature = "", padLimitsLoaded = false;
// A CAN ID change in flight: {from, to, master, target, until}. While it is
// pending the selection stays put, and once it lands the selection follows the
// motor to wherever it now answers, instead of falling back to the first motor.
let idChange = null;
const hex = n => "0x" + Number(n).toString(16).toUpperCase();
const pending = new Map(), history = new Map(), zeroRevisions = new Map(), logs = [];
const fields = {p:["Position · rad",0,-100,100,.01],v:["Speed · rad/s",0,-100,100,.01],kp:["Kp",1,0,500,.1],kd:["Kd",.05,0,5,.01],t:["Torque · Nm",0,-5,5,.01],vlim:["Speed limit · rad/s",1,0,100,.1],ilim:["Current · pu",.2,0,1,.01]};
const limits = {torque:["Torque · Nm",.5,0,5,.1],kp:["Kp",10,0,500,1],kd:["Kd",1,0,5,.1],speed:["Speed · rad/s",5,0,100,1],current:["Current · pu",.3,0,1,.01],rate:["Stream · Hz",200,10,500,10]};
function makeFields(id, data) {
  for (const [name,[title,value,min,max,step]] of Object.entries(data)) {
    const label = document.createElement("label"); label.textContent = title;
    const input = document.createElement("input");
    Object.assign(input, {name, type:"number", value, min, max, step, required:true});
    label.append(input); $(id).append(label);
  }
}
makeFields("command-fields", fields); makeFields("limit-fields", limits);
function notice(text, error=false) { $("notice").textContent = text; $("notice").classList.toggle("error",error); }
// Ask in the page, never with confirm(): the native dialog stops this page's
// heartbeat for as long as it is open, and half a second without one releases
// control, so the action confirmed after it was refused with "take control".
function ask(text, then) {
  const dialog = $("ask");
  $("ask-text").textContent = text; dialog.returnValue = "";
  dialog.onclose = () => { if (dialog.returnValue === "yes") then(); };
  dialog.showModal(); $("ask-yes").focus();
}
function send(op, extra={}) {
  if (!ws || ws.readyState !== WebSocket.OPEN) { notice("Console disconnected",true); return; }
  const req = ++sequence; pending.set(req,op);
  ws.send(JSON.stringify({op,req,...extra}));
}
function motor() { return state.motors?.find(m => m.key === selected); }
function formValues(form) { return Object.fromEntries(new FormData(form)); }
function flushCommand() {
  if (pending.size) return;
  // An ID change waits for whatever was running, such as the scan that follows
  // taking control, rather than being refused as "another action is running".
  if(idChange && !idChange.sent){idChange.sent=true;notice(`Moving ${idChange.from} to ${idChange.to}…`);send("id",{motor:idChange.from,new_id:idChange.id,master:idChange.value});return;}
  if(queuedZero){const target=queuedZero;queuedZero=null;send("zero",{motor:target});return;}
  if (queuedLimits) {
    const values=queuedLimits; queuedLimits=null;
    if(state.control && state.connected && !shutdownRequested) send("limits",values);
    return;
  }
  if (!queuedCommand) return;
  const command = queuedCommand; queuedCommand = null;
  if (command.motor === selected && state.control && state.connected && !shutdownRequested) send("command",command);
}
function validNumbers(form) {
  return [...form.querySelectorAll("input")].every(input => input.value !== "" && Number.isFinite(input.valueAsNumber) && input.valueAsNumber >= Number(input.min) && input.valueAsNumber <= Number(input.max));
}
function editLimits() {
  const form=$("limits-form");
  if(!state.control || !state.connected || !validNumbers(form)){queuedLimits=null;return;}
  queuedLimits=formValues(form); flushCommand();
}
function autoDiscover() {
  if(document.hidden || shutdownRequested || !state.connected || !state.status?.link_up || pending.size) return;
  if(!state.control) {
    if(!state.status?.pi?.control && performance.now()>=autoControlAfter) {
      autoControlAfter=performance.now()+3000; send("take");
    }
  } else if(autoScanNeeded) {
    autoScanNeeded=false; $("scan-status").textContent="Scanning CAN buses A, B and C…";
    send("scan",{last:$("scan-last").value});
  }
}
function editCommand() {
  const form = $("command-form");
  // Feedback positions need not fall on the input spinner's step grid.
  // Accept finite in-range values, including those loaded from the motor.
  const valid = validNumbers(form);
  if (!motor() || !state.control || !state.connected || !valid || queuedZero || [...pending.values()].includes("zero")) { queuedCommand=null; return; }
  queuedCommand = {motor:selected,...formValues(form)};
  flushCommand();
}
function connect() {
  clearTimeout(reconnect); ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => { notice("Console connected"); clearInterval(heartbeat); heartbeat = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN && !document.hidden) ws.send('{"op":"ping"}');
  },100); };
  ws.onmessage = ({data}) => {
    const message = JSON.parse(data);
    if (message.type === "schema") { schema = message.registers; buildRegisters(); }
    if (message.type === "reply") {
      const op = pending.get(message.req); pending.delete(message.req);
      const result = typeof message.result === "string" ? message.result : JSON.stringify(message.result,null,2);
      if(op?.startsWith("wifi.")) {
        if(message.ok){wifiState=message.result;renderWifi();}
        else {$("wifi-status").textContent=message.error;$("wifi-status").className="error";}
      } else if(op?.startsWith("bluetooth.")) {
        if(message.ok){bluetoothState=message.result;renderBluetooth();}
        else {$("bt-status").textContent=message.error;$("bt-status").className="error";}
      } else if(op==="pad.limits") {
        if(!message.ok) notice(message.error,true);
      } else notice(message.ok ? `${op}: ${result}` : `${op || "Action"}: ${message.error}`, !message.ok);
      if (message.ok && op === "power.off") { shutdownRequested = true; notice("Power-off accepted; robot is shutting down"); render(); }
      if (op === "i2c") $("i2c-result").textContent = message.ok ? result : message.error;
      if (op?.startsWith("imu.") && !["imu.on","imu.off"].includes(op)) $("imu-diag").textContent = message.ok ? result : message.error;
      if (message.ok && ["enable","hold"].includes(op)) loaded = null;
      if (op === "write") $("motor-mode").value = motor()?.mode || "";
      if (op === "scan") $("scan-status").textContent=message.ok?"CAN discovery complete":message.error;
      if (op === "id" && idChange) idReply(message);
      flushCommand();
    }
    if (message.type === "state") {
      // Every browser keeps its own motor list, and another one may have
      // changed an ID since this one last scanned: rescan on taking control.
      if (message.control && !state.control) autoScanNeeded = true;
      state = message; lastState = performance.now();
      if(!state.connected){autoScanNeeded=true;limitsLoaded=false;}
      if(message.status?.shutting_down && !shutdownRequested){shutdownRequested=true;notice("Robot is shutting down");}
      for (const event of message.events) { logs.push(event); if(logs.length > 2000) logs.shift(); }
      for (const m of message.motors) {
        const revision=m.command.zero_revision || 0;
        if(zeroRevisions.get(m.key)!==revision){history.delete(m.key);zeroRevisions.set(m.key,revision);}
        if (!history.has(m.key)) history.set(m.key,[]);
        const points = history.get(m.key), fb = m.feedback;
        if (fb && points.at(-1)?.t !== fb.t) points.push(fb);
        while(points.length && points[0].t < (fb?.t || 0)-10) points.shift();
      }
      render();
      autoDiscover();
    }
  };
  ws.onclose = () => { clearInterval(heartbeat); pending.clear(); idChange = null; queuedCommand = queuedLimits = queuedZero = null; zeroRevisions.clear();history.clear();limitsLoaded=false;autoScanNeeded=true; state = {}; loaded = null; lastState = 0; padLimitsLoaded = false; render(); renderWifi(); renderBluetooth(); if(shutdownRequested){notice("Shutdown requested; console disconnected. Refresh after turning the robot on again.");}else{notice("Console disconnected; reconnecting…",true); reconnect = setTimeout(connect,1500);} };
}
function cell(row,text,tag="td") { const element = document.createElement(tag); element.textContent = text ?? "—"; row.append(element); return element; }
function reading(parent,title,value,unit="") {
  const box = document.createElement("div"); box.className="reading";
  const label=document.createElement("span"), strong=document.createElement("strong"), small=document.createElement("small");
  label.textContent=title; strong.textContent=value; small.textContent=unit; box.append(label,strong,small); parent.append(box);
}
const fmt = (x,d=3) => typeof x === "number" && Number.isFinite(x) ? x.toFixed(d) : "—";
function loadCommand(m) {
  queuedCommand = null;
  for(const key of [...Object.keys(fields),"wave","amp","freq"]) $("command-form").elements[key].value = m.command[key];
  const shown = {1:["p","v","kp","kd","t"],2:["p","vlim"],3:["v"],4:["p","vlim","ilim"]}[m.mode] || [];
  for(const key of Object.keys(fields)) $("command-form").elements[key].parentElement.hidden = !shown.includes(key);
  $("new-id").value=m.id; $("new-master").value=hex(m.master);
  loaded=commandVersion(m);
}
function commandVersion(m){return `${m.key}:${m.mode}:${m.command.zero_revision || 0}`;}
function render() {
  const connected = Boolean(state.connected), live = !shutdownRequested && ws?.readyState === WebSocket.OPEN && performance.now()-lastState < 1500;
  $("connection").textContent=shutdownRequested ? "Shutting down" : live ? "Console online" : "Console offline";
  $("connection").className=`badge ${live?"good":"bad"}`;
  $("daemon").textContent=connected ? "diagd running" : "diagd stopped / unavailable";
  $("daemon").className=`badge ${connected?"good":"bad"}`;
  $("owner").textContent=state.control ? "Ready" : state.status?.pi?.control ? "In use by another console" : "Connecting to controller…";
  if(!connected) $("scan-status").textContent="Waiting for controller…";
  else if(!state.control) $("scan-status").textContent=state.status?.pi?.control?"Waiting for the other console to finish…":"Connecting to controller…";
  const motors=state.motors || [];
  if(idChange && performance.now()<idChange.until){
    if(idChange.target && motors.some(m=>m.key===idChange.target)){selected=idChange.target;loaded=null;idChange=null;}
  } else {
    idChange=null;
    if(!motors.some(m=>m.key===selected)){selected=motors[0]?.key || null; loaded=null;}
  }
  // Preserve button identity across telemetry updates, including between
  // pointer-down and click, so incoming feedback cannot swallow a selection.
  const buttons = new Map([...$("motors").children].map(b=>[b.dataset.key,b]));
  for(const m of motors){let button=buttons.get(m.key);
    if(!button){button=document.createElement("button");button.type="button";button.dataset.key=m.key;button.setAttribute("role","option");
      const text=document.createElement("span"), sub=document.createElement("small"), mode=document.createElement("small");text.append(document.createTextNode(m.key),sub);button.append(text,mode);
      button.onclick=()=>{selected=m.key;loaded=null;queuedCommand=queuedZero=null;render();};$("motors").append(button);}
    buttons.delete(m.key);button.className=`motor ${m.key===selected?"selected":""}`;button.setAttribute("aria-selected",String(m.key===selected));
    button.firstChild.lastChild.textContent=m.age>.5?"stale":m.state;button.lastChild.textContent=["","MIT","Position","Velocity","Hybrid"][m.mode] || m.mode;}
  for(const button of buttons.values()) button.remove();
  const m=motor(), fb=m?.feedback;
  $("motor-title").textContent=m?`${m.key} · ${["","MIT","Position–velocity","Velocity","Force–position"][m.mode] || m.mode}`:"Select a motor";
  document.querySelectorAll(".target").forEach(el=>el.textContent=m?.key || "");
  $("motor-state").textContent=m ? `${m.command.active?"driving · ":""}${m.age>.5?"stale":m.state}` : "—";
  $("readings").replaceChildren();
  for(const [label,key,unit] of [["Position","pos","rad"],["Speed","vel","rad/s"],["Torque","torque","Nm"],["MOSFET","t_mos","°C"],["Winding","t_rotor","°C"]]) reading($("readings"),label,fmt(fb?.[key],key.startsWith("t_")?0:3),unit);
  if(m && loaded!==commandVersion(m)) loadCommand(m);
  $("motor-mode").value=m?.mode || "";
  $("motor-mode").disabled=!live||!connected||!state.control||!m||m.command.active||m.feedback?.state===1||!m.feedback||m.age>.5||pending.size>0;
  const zeroPending=Boolean(queuedZero)||[...pending.values()].includes("zero");
  for(const input of $("command-form").querySelectorAll("input,select")) input.disabled=!live||!connected||!state.control||!m||zeroPending||m.command.homing;
  for(const button of document.querySelectorAll("[data-op]")) {
    const op=button.dataset.op, motorOp=["enable","disable","hold","clear","zero","read","save"].includes(op);
    button.disabled=!live || (op==="take" ? !connected || state.control : op==="release" ? !state.control : op==="power.off" ? !connected : op.startsWith("daemon.") ? false : !state.control || !connected || (motorOp&&!m) || (motorOp&&zeroPending));
  }
  if(state.limits && !limitsLoaded){for(const key of Object.keys(limits)) $("limits-form").elements[key].value=key==="rate"?state.rate:state.limits[key];limitsLoaded=true;}
  for(const input of $("limits-form").querySelectorAll("input")) input.disabled=!live||!connected||!state.control;
  for(const id of ["register-form","id-form","i2c-form"]) $(id).querySelector("button").disabled=!live||!state.control||(!m && ["register-form","id-form"].includes(id));
  renderRegisters(m); renderSystem(); renderPad(); for(const key of ["pos","vel","torque"]) drawPlot(key); renderLog();
  $("footer-status").textContent=connected ? `${state.rate} Hz stream · ${state.status?.link_up?"controller online":"controller offline"}${m?.registers?.[9]===0?" · motor TIMEOUT off":""}` : state.error || "Waiting for diagd";
}
function buildRegisters(){
  $("reg-select").replaceChildren();
  for(const r of schema){const option=document.createElement("option");option.value=r.rid;option.textContent=r.name;$("reg-select").append(option);} selectRegister();
}
function selectRegister(){const r=schema.find(r=>r.rid===Number($("reg-select").value));$("reg-description").textContent=r ? `${r.text} · ${r.span} · ${r.writable?"RAM":"read only"}` : "";$("reg-value").value=motor()?.registers?.[r?.rid] ?? "";}
function renderRegisters(m){$("register-rows").replaceChildren();for(const r of schema){const row=document.createElement("tr");cell(row,`0x${r.rid.toString(16).padStart(2,"0")}`);cell(row,r.name);cell(row,m?.registers?.[r.rid]);cell(row,r.span);cell(row,r.writable && ![8,35].includes(r.rid)?"RW":"R");row.onclick=()=>{$("reg-select").value=r.rid;selectRegister();};$("register-rows").append(row);}}
function renderSystem(){const s=state.status;$("system-readings").replaceChildren();reading($("system-readings"),"Battery",fmt(s?.vbus,2),"V");reading($("system-readings"),"Uptime",fmt(s?.uptime,1),"s");reading($("system-readings"),"Link",s?.link_up?"UP":"DOWN");reading($("system-readings"),"IMU",s?.imu_found?"Found":"Absent");
  $("controller").textContent=JSON.stringify({controller:state.info || {},power:s?{hold:s.hold,button:s.button,off:s.off,deadman:s.lost}:null,link:s?.link,pi:s?.pi},null,2);
  $("bus-rows").replaceChildren();for(const [name,b] of Object.entries(s?.buses || {})){const row=document.createElement("tr");for(const v of [name,b.state,`${b.tec} / ${b.rec}`,`${b.tx} / ${b.tx_fail}`,`${b.rx} / ${b.rx_errors}`,b.rx_drop+b.queue_drop])cell(row,v);$("bus-rows").append(row);}
  $("imu-readings").replaceChildren();for(const [name,r] of Object.entries(state.imu || {})){const row=document.createElement("div");row.className="imu-row";let values=r.v.map(v=>fmt(v));let unit=name==="gyro"?"rad/s":name==="game"?"quaternion":"m/s²";
    if(name==="game" && r.v.length>=4){const [x,y,z,w]=r.v;values=[Math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),Math.asin(Math.max(-1,Math.min(1,2*(w*y-z*x)))),Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))].map(v=>fmt(v*180/Math.PI,1));unit="° roll / pitch / yaw";}
    row.textContent=`${name.padEnd(8)} ${values.join("  ")} ${unit} · ${fmt(r.hz,1)} Hz · accuracy ${r.status} · ${fmt(r.age,2)} s${r.age>.5?" · STALE":""}`;$("imu-readings").append(row);}
  if(s?.imu_diag) $("imu-firmware").textContent=JSON.stringify(s.imu_diag,null,2);
}
function drawPlot(key){const canvas=$("plot-"+key), ctx=canvas.getContext("2d"), w=canvas.width,h=canvas.height, points=history.get(selected)||[];ctx.clearRect(0,0,w,h);if(points.length<2)return;
  const values=points.map(p=>p[key]), min=Math.min(...values), max=Math.max(...values), pad=Math.max((max-min)*.15,.01), low=min-pad, high=max+pad, end=points.at(-1).t;
  ctx.font="12px monospace";ctx.lineWidth=1;for(let i=0;i<=4;i++){const y=20+i*(h-40)/4;ctx.strokeStyle="#2a3c46";ctx.beginPath();ctx.moveTo(65,y);ctx.lineTo(w-15,y);ctx.stroke();ctx.fillStyle="#98aab5";ctx.fillText((high-i*(high-low)/4).toFixed(3),4,y+4);}
  ctx.strokeStyle="#69dac0";ctx.lineWidth=2;ctx.beginPath();points.forEach((p,i)=>{const x=65+(p.t-end+10)/10*(w-80),y=20+(high-p[key])/(high-low)*(h-40);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}
function renderLog(){if($("pause").checked)return;const bus=$("traffic-bus").value, id=$("traffic-id").value.trim();$("log").textContent=logs.filter(e=>e.ev!=="can" || ((!bus||e.bus===bus)&&(!id||e.id===Number(id)))).map(e=>e.ev==="can"?`${fmt(e.t,6)}  ${e.bus}  ${e.id.toString(16).padStart(3,"0")}  ${e.data}`:JSON.stringify(e)).join("\n");$("log").scrollTop=$("log").scrollHeight;}
function renderWifi() {
  const online=ws?.readyState===WebSocket.OPEN && !shutdownRequested, saved=wifiState.saved || [], networks=wifiState.networks || [];
  $("wifi-connection").textContent=wifiState.current?`Connected to ${wifiState.current}${wifiState.ip?" · "+wifiState.ip:""}`:"Wi-Fi disconnected";
  $("wifi-status").textContent=wifiState.error || wifiState.message || "";
  $("wifi-status").className=wifiState.error?"error":"muted";
  const signature=JSON.stringify([networks,saved,wifiState.current,wifiState.preferred]);
  if(signature!==wifiSignature) {
    wifiSignature=signature;
    const choice=$("wifi-network").value;
    $("wifi-network").replaceChildren(new Option("Choose a network", ""));
    const names=[...new Set([...networks.map(n=>n.ssid),...saved])];
    for(const ssid of names) {
      const point=networks.find(n=>n.ssid===ssid), security=point?.security;
      const option=new Option(`${ssid}${point?` · ${point.dbm} dBm · ${security}`:" · out of range"}${saved.includes(ssid)?" · saved":""}`,ssid);
      option.disabled=!point || ["Enterprise","Unsupported"].includes(security) && !saved.includes(ssid);
      $("wifi-network").append(option);
    }
    $("wifi-network").value=names.includes(choice)?choice:wifiState.current || "";
    $("wifi-saved").replaceChildren();
    for(const ssid of saved) {
      const row=document.createElement("div"), name=document.createElement("span"), forget=document.createElement("button");row.className="saved-network toolbar";
      name.textContent=ssid+(ssid===wifiState.current?" · connected":"")+(ssid===wifiState.preferred?" · preferred":"");
      forget.textContent="Forget";forget.type="button";
      const forgetNow=()=>{queuedCommand=queuedLimits=null;send("wifi.forget",{ssid});renderWifi();};
      forget.onclick=()=>{if(ssid===wifiState.current)ask(`Forget ${ssid} and disconnect the BPI from this network?`,forgetNow);else forgetNow();};
      row.append(name,forget);$("wifi-saved").append(row);
    }
    if(!saved.length) $("wifi-saved").textContent="No saved networks";
  }
  const busy=wifiState.busy || [...pending.values()].some(op=>op.startsWith("wifi."));
  for(const control of document.querySelectorAll("#wifi button,#wifi input,#wifi select")) control.disabled=!online||busy;
  $("wifi-connect").disabled=!online||busy||!$("wifi-network").value;
}
function renderDevices(id, devices, none, label, primary, act) {
  $(id).replaceChildren();
  for(const device of devices) {
    const row=document.createElement("div"), name=document.createElement("span"), action=document.createElement("button");row.className="saved-network toolbar";
    const link=!device.paired?"":device.ready?" · connected":device.connected?" · linked, setting up":" · not connected";
    name.textContent=device.name+link;
    action.textContent=label;action.type="button";if(primary&&device.gamepad)action.className="primary";
    action.onclick=()=>act(device);
    row.append(name,action);$(id).append(row);
  }
  if(!devices.length) $(id).textContent=none;
}
function renderBluetooth() {
  const online=ws?.readyState===WebSocket.OPEN && !shutdownRequested, b=bluetoothState, paired=b.paired || [], found=b.found || [];
  $("bt-adapter").textContent=b.available===undefined||b.available===null?"Loading Bluetooth status…":!b.available?"No Bluetooth adapter is answering on this computer":b.powered?"Bluetooth adapter on":"Bluetooth adapter off; finding a controller switches it on";
  $("bt-status").textContent=b.error || b.message || "";
  $("bt-status").className=b.error?"error":"muted";
  const signature=JSON.stringify([paired,found]);
  if(signature!==bluetoothSignature) {
    bluetoothSignature=signature;
    renderDevices("bt-paired",paired,"No paired controllers","Forget",false,device=>{
      const forget=()=>{send("bluetooth.forget",{address:device.address});renderBluetooth();};
      if(device.connected)ask(`Forget ${device.name}? It is connected, and would have to be paired again.`,forget);else forget();
    });
    renderDevices("bt-found",found,"Nothing found yet","Pair",true,device=>{bluetoothState.scanning=false;send("bluetooth.pair",{address:device.address});renderBluetooth();});
  }
  const busy=b.busy || [...pending.values()].some(op=>op.startsWith("bluetooth."));
  for(const control of document.querySelectorAll("#bt-scan,#bt-paired button")) control.disabled=!online||busy||(control.id==="bt-scan"&&b.available===false);
  // A scan gives way to a pairing: a controller's pairing mode runs out while it goes.
  for(const control of document.querySelectorAll("#bt-found button")) control.disabled=!online||(busy&&!b.scanning);
}
function renderPad() {
  const pad=state.pad, command=pad?.command, driving=Boolean(pad?.name&&command?.live);
  $("pad-state").textContent=!pad?.name?"No controller":driving?"Driving":"Not driving";
  $("pad-state").className=`badge ${driving?"good":pad?.name?"":"bad"}`;
  $("pad-why").textContent=pad?.error||(pad?.name?`${pad.name}${pad.why_not?": "+pad.why_not:""}`:"No game controller is connected");
  $("pad-why").className=pad?.error?"error":"";
  $("pad-readings").replaceChildren();
  reading($("pad-readings"),"Forward",fmt(command?.forward,2),"m/s");
  reading($("pad-readings"),"Turn",fmt(command?.turn,2),"rad/s");
  reading($("pad-readings"),"Leg height",fmt(command&&command.height*1000,1),"mm");
  reading($("pad-readings"),"Jumps asked",command?command.jump&255:"—");
  reading($("pad-readings"),"Buttons held",pad?.held?.length?pad.held.join(", "):"—");
  $("pad-reach").textContent=!pad?.name?"":!pad.diagd?"diagd is not running, so none of this is going anywhere.":pad.taken?"Going to the policy on the controller.":"This reaches diagd, and from there any program on the Pi running a policy, as balance.py with --drive and launcher.py do. The controller's firmware runs no policy yet.";
  const form=$("pad-limits");
  if(pad && !padLimitsLoaded){form.elements.speed.max=pad.top_speed;form.elements.turn.max=pad.top_turn;form.elements.speed.value=pad.speed_limit;form.elements.turn.value=pad.turn_limit;padLimitsLoaded=true;}
  for(const input of form.querySelectorAll("input")) input.disabled=!pad;
}
document.querySelectorAll("[data-tab]").forEach(button=>button.onclick=()=>{document.querySelectorAll(".panel").forEach(panel=>panel.hidden=panel.id!==button.dataset.tab);document.querySelectorAll("[data-tab]").forEach(b=>b.classList.toggle("selected",b===button));if(button.dataset.tab==="wifi"){send("wifi.status");renderWifi();}if(button.dataset.tab==="gamepad"){send("bluetooth.status");renderBluetooth();}});
document.querySelectorAll("[data-op]").forEach(button=>button.onclick=()=>{
  const op=button.dataset.op;
  queuedCommand=queuedLimits=queuedZero=null;
  if(op==="zero"){queuedZero=selected;flushCommand();render();return;}
  const confirmations={save:"Save this motor’s settings to flash?", "power.off":"Stop all motors and power off the robot?", "daemon.stop":"Stop diagd and all motors?"};
  const extra={motor:selected,last:$("scan-last").value,hz:$("imu-hz").value};
  if(confirmations[op]) ask(confirmations[op],()=>send(op,extra)); else send(op,extra);
});
$("stop").onclick=()=>{queuedCommand=queuedLimits=queuedZero=null;send("stop");};document.addEventListener("keydown",e=>{if(e.key==="Escape"){if(!$("ask").open)e.preventDefault();queuedCommand=queuedLimits=queuedZero=null;send("stop");}});
$("command-form").onsubmit=e=>{e.preventDefault();editCommand();};
$("command-form").oninput=editCommand;
$("command-form").onchange=editCommand;
$("motor-mode").onchange=()=>{queuedCommand=null;send("write",{motor:selected,rid:10,value:$("motor-mode").value});$("motor-mode").disabled=true;};
$("limits-form").onsubmit=e=>{e.preventDefault();editLimits();};
$("limits-form").oninput=editLimits;$("limits-form").onchange=editLimits;
$("wifi-scan").onclick=()=>{send("wifi.scan");renderWifi();};
$("wifi-form").onsubmit=e=>{e.preventDefault();queuedCommand=queuedLimits=null;send("wifi.connect",{ssid:$("wifi-network").value,password:$("wifi-password").value});$("wifi-password").value="";renderWifi();};
$("wifi-network").onchange=renderWifi;
setInterval(()=>{if(!$("wifi").hidden && ws?.readyState===WebSocket.OPEN && !document.hidden && ![...pending.values()].some(op=>op.startsWith("wifi."))){send("wifi.status");}},2000);
$("bt-scan").onclick=()=>{send("bluetooth.scan");renderBluetooth();};
$("pad-limits").onsubmit=e=>e.preventDefault();
$("pad-limits").oninput=()=>{if(validNumbers($("pad-limits")))send("pad.limits",formValues($("pad-limits")));};
setInterval(()=>{if(!$("gamepad").hidden && ws?.readyState===WebSocket.OPEN && !document.hidden && ![...pending.values()].some(op=>op.startsWith("bluetooth."))){send("bluetooth.status");}},2000);
$("register-form").onsubmit=e=>{e.preventDefault();send("write",{motor:selected,rid:$("reg-select").value,value:$("reg-value").value});};
$("id-form").onsubmit=e=>{e.preventDefault();
  if(!selected) return;
  if(idChange){notice(`${idChange.from} is still being moved to ${idChange.to}`,true);return;}
  const id=Number($("new-id").value), master=Number($("new-master").value);
  if(!Number.isInteger(id) || !Number.isInteger(master)){notice("The CAN ID and feedback ID must be whole numbers",true);return;}
  const to=`${selected.split(":")[0]}:${id}`;
  const from=selected;
  ask(`Give ${from} CAN ID ${id} and feedback ID ${hex(master)}, and save them to its flash?`,()=>{
    if(idChange) return;
    idChange={from,to,id,value:master,master:hex(master),target:null,until:Infinity,sent:false};
    if(pending.size) notice(`Moving ${from} to ${to} once the current action finishes…`);
    flushCommand();});};
function idReply(message){
  const {from,to,master}=idChange, r=message.result || {};
  if(!message.ok){idChange=null;notice(`${from} was not changed: ${message.error}`,true);render();return;}
  idChange.target=r.at_new ? to : r.at_old ? from : null;
  idChange.until=performance.now()+3000;
  if(idChange.target){selected=idChange.target;loaded=null;}
  if(r.at_new && from===to) notice(r.saved?`${to} now sends feedback on ${master}, saved to flash.`:`${to} now sends feedback on ${master}, but the save to flash was not confirmed: it may revert at power-off.`,!r.saved);
  else if(r.at_new) notice(r.saved?`${from} is now ${to}, feedback on ${master}, saved to flash.`:`${from} is now ${to}, feedback on ${master}, but the save to flash was not confirmed: it may revert at power-off.`,!r.saved);
  else if(r.at_old) notice(`${from} still answers at its old ID. Power-cycle it and scan; if it is still at ${from}, the change did not take.`,true);
  else notice(`${from} answers at neither ${from} nor ${to}. Power-cycle it and scan.`,true);
  render();
}
// Typing a CAN ID suggests the bench convention's feedback ID, CAN ID + 0x10.
$("new-id").oninput=()=>{const id=Number($("new-id").value);if(Number.isInteger(id)&&id>=1&&id<=15)$("new-master").value="0x"+(id+0x10).toString(16).toUpperCase();};
$("i2c-form").onsubmit=e=>{e.preventDefault();send("i2c",formValues(e.target));};
$("reg-select").onchange=selectRegister;
$("traffic-bus").onchange=renderLog;$("traffic-id").oninput=renderLog;$("pause").onchange=renderLog;
$("clear-log").onclick=()=>{logs.length=0;renderLog();};
$("export-log").onclick=()=>{const url=URL.createObjectURL(new Blob([logs.map(e=>JSON.stringify(e)).join("\n")],{type:"application/x-ndjson"}));const a=document.createElement("a");a.href=url;a.download="bipedal-diagnostics.jsonl";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.addEventListener("visibilitychange",()=>{if(document.hidden){queuedCommand=queuedLimits=queuedZero=null;send("release");}else{autoControlAfter=0;autoDiscover();}});
window.addEventListener("pagehide",()=>{if(ws?.readyState===WebSocket.OPEN){ws.send('{"op":"release"}');ws.close();}});
setInterval(()=>{if(lastState && performance.now()-lastState>1500){notice("Console updates lost",true);ws.close();}},500);
connect();
