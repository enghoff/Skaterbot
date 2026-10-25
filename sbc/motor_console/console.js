"use strict";
const $ = id => document.getElementById(id);
let ws, state = {}, schema = [], selected = null, sequence = 0, loaded = null;
let reconnect, heartbeat, lastState = 0;
const pending = new Map(), history = new Map(), logs = [];
const fields = {p:["Position · rad",0,-100,100,.01],v:["Speed · rad/s",0,-100,100,.01],kp:["Kp",0,0,500,.1],kd:["Kd",0,0,5,.01],t:["Torque · Nm",0,-5,5,.01],vlim:["Speed limit · rad/s",1,0,100,.1],ilim:["Current · pu",.2,0,1,.01]};
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
function send(op, extra={}) {
  if (!ws || ws.readyState !== WebSocket.OPEN) { notice("Console disconnected",true); return; }
  const req = ++sequence; pending.set(req,op);
  ws.send(JSON.stringify({op,req,...extra}));
}
function motor() { return state.motors?.find(m => m.key === selected); }
function formValues(form) { return Object.fromEntries(new FormData(form)); }
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
      notice(message.ok ? `${op}: ${result}` : `${op || "Action"}: ${message.error}`, !message.ok);
      if (op === "i2c") $("i2c-result").textContent = message.ok ? result : message.error;
      if (op?.startsWith("imu.") && !["imu.on","imu.off"].includes(op)) $("imu-diag").textContent = message.ok ? result : message.error;
      if (message.ok && ["enable","hold"].includes(op)) loaded = null;
    }
    if (message.type === "state") {
      state = message; lastState = performance.now();
      for (const event of message.events) { logs.push(event); if(logs.length > 2000) logs.shift(); }
      for (const m of message.motors) {
        if (!history.has(m.key)) history.set(m.key,[]);
        const points = history.get(m.key), fb = m.feedback;
        if (fb && points.at(-1)?.t !== fb.t) points.push(fb);
        while(points.length && points[0].t < (fb?.t || 0)-10) points.shift();
      }
      render();
    }
  };
  ws.onclose = () => { clearInterval(heartbeat); pending.clear(); state = {}; loaded = null; lastState = 0; render(); notice("Console disconnected; reconnecting…",true); reconnect = setTimeout(connect,1500); };
}
function cell(row,text,tag="td") { const element = document.createElement(tag); element.textContent = text ?? "—"; row.append(element); return element; }
function reading(parent,title,value,unit="") {
  const box = document.createElement("div"); box.className="reading";
  const label=document.createElement("span"), strong=document.createElement("strong"), small=document.createElement("small");
  label.textContent=title; strong.textContent=value; small.textContent=unit; box.append(label,strong,small); parent.append(box);
}
const fmt = (x,d=3) => typeof x === "number" && Number.isFinite(x) ? x.toFixed(d) : "—";
function loadCommand(m) {
  for(const key of [...Object.keys(fields),"wave","amp","freq"]) $("command-form").elements[key].value = m.command[key];
  const shown = {1:["p","v","kp","kd","t"],2:["p","vlim"],3:["v"],4:["p","vlim","ilim"]}[m.mode] || [];
  for(const key of Object.keys(fields)) $("command-form").elements[key].parentElement.hidden = !shown.includes(key);
  $("new-id").value=m.id; $("new-master").value=m.master;
  loaded=m.key+":"+m.mode;
}
function render() {
  const connected = Boolean(state.connected), live = ws?.readyState === WebSocket.OPEN && performance.now()-lastState < 1500;
  $("connection").textContent=live ? "Console online" : "Console offline";
  $("connection").className=`badge ${live?"good":"bad"}`;
  $("daemon").textContent=connected ? "diagd running" : "diagd stopped / unavailable";
  $("daemon").className=`badge ${connected?"good":"bad"}`;
  $("owner").textContent=state.control ? "Control: this browser" : `Control: ${state.status?.pi?.control || "nobody"}`;
  const motors=state.motors || [];
  if(!motors.some(m=>m.key===selected)){selected=motors[0]?.key || null; loaded=null;}
  $("motors").replaceChildren();
  for(const m of motors){const button=document.createElement("button");button.className=`motor ${m.key===selected?"selected":""}`;button.setAttribute("role","option");button.setAttribute("aria-selected",m.key===selected);
    const text=document.createElement("span"), sub=document.createElement("small");text.textContent=m.key;sub.textContent=m.age>.5?"stale":m.state;text.append(sub);button.append(text);const mode=document.createElement("small");mode.textContent=["","MIT","Position","Velocity","Hybrid"][m.mode] || m.mode;button.append(mode);button.onclick=()=>{selected=m.key;loaded=null;render();};$("motors").append(button);}
  const m=motor(), fb=m?.feedback;
  $("motor-title").textContent=m?`${m.key} · ${["","MIT","Position–velocity","Velocity","Force–position"][m.mode] || m.mode}`:"Select a motor";
  document.querySelectorAll(".target").forEach(el=>el.textContent=m?.key || "");
  $("motor-state").textContent=m ? `${m.command.active?"driving · ":""}${m.age>.5?"stale":m.state}` : "—";
  $("readings").replaceChildren();
  for(const [label,key,unit] of [["Position","pos","rad"],["Speed","vel","rad/s"],["Torque","torque","Nm"],["MOSFET","t_mos","°C"],["Winding","t_rotor","°C"]]) reading($("readings"),label,fmt(fb?.[key],key.startsWith("t_")?0:3),unit);
  if(m && loaded!==m.key+":"+m.mode) loadCommand(m);
  for(const button of document.querySelectorAll("[data-op]")) {
    const op=button.dataset.op, motorOp=["enable","disable","hold","clear","zero","read","save"].includes(op);
    button.disabled=!live || (op==="take" ? !connected || state.control : op==="release" ? !state.control : op.startsWith("daemon.") ? false : !state.control || !connected || (motorOp&&!m));
  }
  for(const id of ["command-form","register-form","id-form","limits-form","i2c-form"]) $(id).querySelector("button").disabled=!live||!state.control||(!m && ["command-form","register-form","id-form"].includes(id));
  renderRegisters(m); renderSystem(); drawPlot(); renderLog();
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
function drawPlot(){const canvas=$("plot"), ctx=canvas.getContext("2d"), w=canvas.width,h=canvas.height,key=$("plot-kind").value, points=history.get(selected)||[];ctx.clearRect(0,0,w,h);if(points.length<2)return;
  const values=points.map(p=>p[key]), min=Math.min(...values), max=Math.max(...values), pad=Math.max((max-min)*.15,.01), low=min-pad, high=max+pad, end=points.at(-1).t;
  ctx.font="12px monospace";ctx.lineWidth=1;for(let i=0;i<=4;i++){const y=20+i*(h-40)/4;ctx.strokeStyle="#2a3c46";ctx.beginPath();ctx.moveTo(65,y);ctx.lineTo(w-15,y);ctx.stroke();ctx.fillStyle="#98aab5";ctx.fillText((high-i*(high-low)/4).toFixed(3),4,y+4);}
  ctx.strokeStyle="#69dac0";ctx.lineWidth=2;ctx.beginPath();points.forEach((p,i)=>{const x=65+(p.t-end+10)/10*(w-80),y=20+(high-p[key])/(high-low)*(h-40);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}
function renderLog(){if($("pause").checked)return;const bus=$("traffic-bus").value, id=$("traffic-id").value.trim();$("log").textContent=logs.filter(e=>e.ev!=="can" || ((!bus||e.bus===bus)&&(!id||e.id===Number(id)))).map(e=>e.ev==="can"?`${fmt(e.t,6)}  ${e.bus}  ${e.id.toString(16).padStart(3,"0")}  ${e.data}`:JSON.stringify(e)).join("\n");$("log").scrollTop=$("log").scrollHeight;}
document.querySelectorAll("[data-tab]").forEach(button=>button.onclick=()=>{document.querySelectorAll(".panel").forEach(panel=>panel.hidden=panel.id!==button.dataset.tab);document.querySelectorAll("[data-tab]").forEach(b=>b.classList.toggle("selected",b===button));});
document.querySelectorAll("[data-op]").forEach(button=>button.onclick=()=>{
  const op=button.dataset.op;
  const confirmations={zero:"Set this motor’s current position as zero?",save:"Save this motor’s settings to flash?", "power.off":"Stop all motors and power off the robot?", "daemon.stop":"Stop diagd and all motors?"};
  if(confirmations[op]&&!confirm(confirmations[op]))return;
  send(op,{motor:selected,last:$("scan-last").value,hz:$("imu-hz").value});
});
$("stop").onclick=()=>send("stop");document.addEventListener("keydown",e=>{if(e.key==="Escape"){e.preventDefault();send("stop");}});
$("command-form").onsubmit=e=>{e.preventDefault();send("command",{motor:selected,...formValues(e.target)});};
$("limits-form").onsubmit=e=>{e.preventDefault();send("limits",formValues(e.target));};
$("register-form").onsubmit=e=>{e.preventDefault();send("write",{motor:selected,rid:$("reg-select").value,value:$("reg-value").value});};
$("id-form").onsubmit=e=>{e.preventDefault();if(confirm("Change this motor’s CAN and feedback IDs and save to flash?"))send("id",{motor:selected,new_id:$("new-id").value,master:$("new-master").value});};
$("i2c-form").onsubmit=e=>{e.preventDefault();send("i2c",formValues(e.target));};
$("reg-select").onchange=selectRegister;$("plot-kind").onchange=drawPlot;
$("traffic-bus").onchange=renderLog;$("traffic-id").oninput=renderLog;$("pause").onchange=renderLog;
$("clear-log").onclick=()=>{logs.length=0;renderLog();};
$("export-log").onclick=()=>{const url=URL.createObjectURL(new Blob([logs.map(e=>JSON.stringify(e)).join("\n")],{type:"application/x-ndjson"}));const a=document.createElement("a");a.href=url;a.download="bipedal-diagnostics.jsonl";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.addEventListener("visibilitychange",()=>{if(document.hidden)send("release");});
window.addEventListener("pagehide",()=>{if(ws?.readyState===WebSocket.OPEN){ws.send('{"op":"release"}');ws.close();}});
setInterval(()=>{if(lastState && performance.now()-lastState>1500){notice("Console updates lost",true);ws.close();}},500);
connect();
