# Build review — 30 September 2026

A pass over the whole robot asking one question: **can what is drawn be bought,
built and put together?** Gates A to H already said the parts are what was drawn,
that they print as one piece each, and that nothing overlaps once assembled.
None of them asked whether the parts drawn are the parts on sale, whether each
one can get to where it ends up, or whether the screws have thread to bite. This
review did, and changed what it could.

**The short version.** The battery the torso was designed around does not exist,
and nothing held the packs in place. Both are fixed. The torso can be put
together, but only in one order, and the deck cannot come out without first
removing three parts from the rear wall. The screws into the back of each motor
had no margin and now have 0.5 mm. Eight bill-of-materials lines were sold out
or sourced only from a shop whose stock cannot be read, and now point at
in-stock listings; about a dozen parts still cannot be checked from here, mostly
at Robu and element14. Five things wait on a part in hand, and they are at the
end.

## Fixed

**The battery pack was a size nobody makes.** The bay was drawn for "a 3S
2200 mAh pack, 76 × 33 × 25 mm". Every 3S 2200 mAh pack on sale in India is 105
to 108 mm long, so it would have missed the bay by 30 mm. The bay stays as it is.
The pack is now a **Bonka 3S 1000 mAh 35C**, in stock at Indian Hobby Center at
₹1,399, which is 75 × 32 × 17 mm and 95 g by the only published figure, and
86 g each on the scale when the pair arrived. Two in
series give 22.2 Wh where 48.8 was planned, which cuts runtime by a little over
half. The robot is 98 g lighter for it. Its 35 A continuous rating is still above
the 24 A the motors are estimated to draw at once.

**Nothing held the packs.** The deck was said to clamp them through "3 mm of
squeeze", but that 3 mm was air. The two cinch straps meant to back it up had no
route: one lane led into the hip saddle and the other into the looms. Each pack
is now held on all six sides:

- a rail underneath;
- a stop on the rail's end;
- a fin between the two packs;
- a fence down each outer face;
- foam between each pack and its fence, the deck and the left wall.

The fin and fences stand in the pelvis, so each pack is pushed down into a slot
of its own, by hand and in sight, before anything goes in over it. The fences
were first drawn resting on the hip saddle's top, which does not reach them, so
45 mm of each hung in the air; no gate saw it, and gate F now checks that
everything standing in the cavity rests on the pelvis all the way along. They
hung from the deck at first, which meant the fin had to find the 2 mm between
two loose packs blind as the deck came down; now the deck brings only the foam
pads over the packs, which need no lining up. Each pack needs a pull tab of
polyimide tape under it to come out again, because the foam grips it and there
is no room for fingers beside it. The foam is one ₹563 sheet of anti-static EVA
and the tape is a ₹256 roll, both in stock. Gate F now checks that every one of
those faces touches and that no piece of foam is squeezed past half its
thickness. The straps and their slots are gone.

**Moving the rails sealed a void inside the hip saddle**, which the one-solid
rule caught before anything was exported. The rails now start at the saddle's
inboard face, because the saddle's own top already carries the packs there.

**The torso has a build order, and it is now checked.** Gate I (new) runs each
torso part out along the path it goes in on, against everything already in. It
found three things:

- **The rear wall's three parts go in after the deck.** The on/off button, the
  charge socket and the antenna bulkhead each block the controller board on the
  deck's way down.
- **Their nuts go in first, and the parts are threaded into them from outside.**
  With the deck in, the button's and antenna's nuts can't be run up their threads
  from inside: the core board and the SBC are where the nuts would have to start.
  The charge socket's outer nut sits 1.8 mm under a cover boss, so it has to come
  in from the front and slide back to the wall.
- **Getting at the battery means eight fixings, not four.** The BOM said four deck
  screws released the deck. It also takes the button's nut, the antenna's nut and
  the socket's two screws. The BOM now says so.
- **The charge inlet is a male XT60E-M since 2026-10-05, and goes in from
  inside.** The female went onto the charger's lead. The male's ears bear on the
  inside of the wall, so after the deck it comes down in front of the wall and
  goes back 8.5 mm until its nose is through, and only x 58.45 to 59.45 lets it
  do that: inboard, its ears meet the actuator harness plugs; outboard, its nose
  meets the rear right cover boss. It sits at x 59.0, a millimetre below the
  other two so its body clears that boss, and its nuts go on behind its ears
  afterwards. Its pins are live at pack voltage whenever the cells are connected,
  with nothing fused behind them.

**The screws into the back of each motor had no thread to spare.** Both lengths
were chosen to engage 3.8 mm. The motor's rear holes are 3.8 mm deep in the
vendor's STEP and "tapped 4 mm deep" on its drawing. A screw that bottoms stops
clamping before its head is down. One standard 0.5 mm washer under each of the
24 heads leaves 3.3 mm engaged and 0.5 mm clear of the bottom.

**The output screws can probably be M3 × 8.** The same STEP shows the output
holes drilled 6.5 mm deep. An M3 × 8 would engage 5.2 mm and stop 1.3 mm short.
The BOM had been waiting on a measurement to choose between ×6 and ×8.

**The deck ledges were a millimetre too shallow for their screws.** Each M2.5
is placed by its head, 0.5 mm off the wall, and cuts its own thread into the
ledge. At 5 mm deep the ledge's cavity-side face was 1.0 mm outside that thread,
under the 1.25 mm or so a screw cutting its own thread into plastic wants, so a
firm tightening could split it. The ledges are 6 mm deep now, which leaves
2.0 mm, and they still clear the battery and power bays by 0.6 mm. Drawn in
place, each screw's head clears the wall by 0.5 mm, 5 mm of thread is engaged,
and a hex key has a straight path down to it. The head rests on only 41 % of its
underside, because the deck's hole has to run out to the plate edge as a slot,
and no washer fits in the half millimetre to the wall, so tighten them gently.

**Every fastener now comes off a shelf, and one set was wrong.** The M3 × 14
the motors' rear screws needed is not stocked in 12.9 by any hobby shop, so it
came from MISUMI at ₹38 a screw. Working out a replacement found that the bill
had the knees wrong. It listed sixteen M3 × 14 for "knee and wheel" through a
6 mm plate, but the knees are straddled clevises with a 3 mm cheek, like the
hips. There, an M3 × 14 would have bottomed about 2.5 mm before it clamped.
The hips and knees now take an M3 × 10 on one 0.5 mm washer. The wheel motors'
6 mm plate has a 1 mm washer spot face at each rear screw, so an M3 × 12 on
one 0.5 mm washer gets the same 3.3 mm of thread. The first version of the spot
faces was partly filled back in by the shin's waist, 1.8 mm³ of it, which gate
B's arithmetic caught. The waist now takes the same cuts. The output screws
default to M3 × 8, because the vendor STEP shows 6.5 mm of thread. The two
fasteners nobody stocks are designed out:

- **The journal's 5.3 × 9 × 1 washer** was an import only. It was a 1 mm spacer
  under the screw head, so the printed sleeve is now 1 mm longer and does the
  same job.
- **The power switch board's Ø6 × 8 unthreaded spacers** were in nobody's stock.
  They are printed now, four PA12 tubes.

The M5 thin nut is an ordinary M5 nut filed to 2.7 mm. MISUMI is off the bill,
and the fastdep and Robu carts match it.

**The wheel's heat-set insert was the wrong size.** The bore is drawn Ø6.4 × 12,
which is the melt-in hole for a 7 mm knurl. The BOM named an 8 mm insert, 1.5 mm
short of the drawing. It now names a 10 mm insert on a 7 mm knurl, in stock.

**Everything still prints.** Gate G passes all nine pieces with the new fences,
fin, rails and stops.

## Re-sourced

Every purchase link on the bill was opened: 143 different pages, 166 mentions.
The first pass read 77 of the mentions as in stock. Of the rest, the
ElectronicsComp, Probots and Sunrom parts turned out to be in stock once each
page was read on its own. These lines were sold out, or pointed only
at a shop that refuses automated reads, and each now points at an in-stock
listing:

| Line | Was | Now |
|---|---|---|
| Battery | GenX / Bonka 2200 mAh, 105 mm long | Bonka 3S 1000 mAh, Indian Hobby Center, ₹1,399 |
| Battery series harness | Robu only | QuartzComponents ₹111 · Indian Hobby Center ₹149 |
| 14 AWG bus wire | QuartzComponents, black sold out | Indian Hobby Center, ₹89/m |
| 18 AWG motor wire | QuartzComponents, sold out | Indian Hobby Center, ₹65/m |
| M5 × 12 wheel screw and M5 insert | Robu only | Amazon.in, ₹109 and ₹495 |
| M5 × 12 journal screw | Robu only | Amazon.in, ₹315 |
| M2 × 10 screws and nuts | Robu only | fastdep, ₹42 and ₹28 |
| Battery straps | "local hardware" | deleted; foam instead, Amazon.in ₹563 |

## Still open

**Waiting on a part in hand.** None of these can be answered from a listing.

- **~~Measure a battery pack before the pelvis is printed.~~ Done 5 October.**
  The packs are 77 × 38 × 19 mm at most against the listing's 75 × 32 × 17, but
  only the last 12 mm, where the leads come out, is that big; the 65 mm of body
  furthest from the leads is within 35 × 17. The rails, fin, fences and foam now
  stop at that 65 mm, so nothing presses beside the lead end, and the band under
  the deck went from 36 mm to 39 to clear the body's foam and a lead end up to
  38 mm tall. That makes the torso 89 mm and the robot 363 mm, 3 mm taller, and
  3.1 g heavier. The end stop still bears on the foot of each lead end, end-on;
  check that the wrap there is firm before the pelvis prints.
- **Measure the Banana Pi's mounting holes before the controller carrier PCB is
  ordered.** Its hole pattern is inferred, not published, and the carrier's holes
  are drilled by the board house. The Pi is already on order.
- **Measure a skate wheel before the wheel adapter is printed.** The hub's
  Ø45 mm and the tread's 20 mm crown radius are representative figures.
- **Look at where the battery management board takes its wires.** The balance
  and charge leads attach somewhere on the Daly board, and the only air beside it
  is 3.45 mm to the pack ends since the packs were measured, where it was 4.95.
  The balance tails now come straight down that gap from the packs' lead ends. A
  plug on the board's inboard face may not fit. The board is already on order.
- **Measure the motor's output thread depth** on the first motor, to confirm
  M3 × 8.

**Not drawn, so not checked by any gate.**

- **The pack leads' route to the power bay.** The management board stands
  across the whole gap between the bays, with 1.5 mm over it. The leads can only
  pass under it, where there is 13.5 mm since the deck rose 3 mm, or round its
  ends, where there is 4.6 mm. So the packs have to be connected before the board drops in. That is
  the order gate I checks, but the leads themselves are not drawn, and nobody
  has checked the packs' leads are long enough.
- **Motor lead lengths.** The 300 mm pigtails have not been laid along a leg to
  the carrier.
- **The legs are not in gate I.** Their joints were worked through for assembly
  by hand in `docs/NOTES.md` on 14 September, but no gate repeats it.

**The distribution board is out of stock.** Robu, its only seller, showed the
SwiftWing PDB-02-XT60 out of stock at ₹450 when read in a browser later on
30 September. The pelvis posts and the power switch board are drawn to it. A
generic "100 A multirotor PDB" is in stock at three readable shops for ₹86–120,
with the same 50 × 50 mm outline and 45 mm hole square, but no factory-fitted
XT60, so the bus input would be soldered on. **This needs a decision.** Robu's
motor pigtails and thermal pad were in stock the same day, and are in its cart.

**Read in a browser on 1 October, and three parts did not exist.** element14 and
Techtonics, which refuse automated reads, were read in a browser instead. The
INA226 was in stock at Techtonics and is ordered. But the power switch board's
through-hole BAT46 is no longer made, and nor is its WIMA C7, and its 14.7 kΩ
1 % and 680 kΩ are not stocked in the 0204 body the board is drawn around. The
board was changed the same day to 1N4148s, a KEMET C7 of the same size, 15 kΩ and
1 MΩ, and still passes every check it is held to, with less margin in the
switch-off transient: docs/POWER_SWITCH.md has the figures.

**Decisions this review did not take.**

- **The runtime.** 22.2 Wh is about 55 minutes balancing, under half an hour
  driving and under 10 minutes in a loaded crouch. Those are the plan's own
  estimates scaled, none of them measured. Bonka's 1300 mAh pack is the same
  72 mm long and would give 59 % of the planned energy, but no readable shop has
  it, and at 22 mm thick it fits only with the side foam cut to 2 mm. The 1500 mAh
  is 26 mm thick and would not fit without moving the CAN loom.
- **Servicing.** Opening the battery bay now means undoing the rear wall. The
  two rear deck screws sit directly under the on/off button and the charge
  socket, so a notch in the controller carrier's rear edge would not be enough on
  its own: the parts themselves would have to move along the wall, clear of the
  screws and of the carrier's path.
- **The motors' torque envelope** has still not been re-derived for the wheeled
  robot.

## What was run

- `/check`: clean. Every piece builds as one solid.
- Gates A to I: all pass.
- `/mass`: 2,005.1 g against the 2,300 g ceiling, 294.9 g of headroom.
  - Pelvis: +8.5 g (−2.2 g of rail, +10.5 g of fin and fences, +0.2 g of deck
    ledge).
  - Deck: +0.7 g.
  - Battery: −98 g.
- `/step`: all nine pieces exported and verified as one solid each.
- `/urdf`: regenerated; the model agrees with the CAD at 1,979.9 g.
