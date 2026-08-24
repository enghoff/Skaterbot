# Zookeeper task brief — fix three defects in the knee module

**Status:** open, written 2026-08-24. The previous brief asked for the knee
actuator interface to be built; it was, and the delivery is committed as
`def8540`. This brief fixes three defects found afterwards by checking the axial
stations in `knee_module.kcl` arithmetically, plus one analysis error that was
inherited from `NOTES.md` and is not yours.

All paths below are relative to the repository root, not to this file.

---

Read [`AGENTS.md`](AGENTS.md) first — it is binding.

The module is sound in structure, scope and constraint discipline. All three
defects are the same class of mistake: features whose **X extents** do not do what
the design intends, in a model where nothing looks wrong on screen because the
actuator proxy is a plain cylinder that does not carry the 1 mm output boss. They
were found on paper, not in the viewer, and they will not show up in a render.
Everything else checked out — the stop angles reproduce exactly, the rear bolt
stack is consistent, the clearances against Ø46 hold, and the mass estimate is
about right.

The X convention below is the module's own: the actuator spans −18.95 to +18.95,
the output face is +X.

## Defect 1 — the output hub does not touch the actuator

The hub occupies X 18.95 to 24.95 and the Ø30.4 register pocket is cut from 18.95
to 20.15.

But **X = 18.95 is the top of the 1 mm output boss**, not the housing face. The
37.9 mm overall length is measured over the boss, so the housing face is at 17.95.
That means:

- the hub's land, Ø30.4 to Ø36, sits 1 mm clear of the housing — which is
  correct and is exactly the stator relief you want;
- the pocket roof sits **1.2 mm clear of the boss**, which is the face the six
  screws thread into.

Nothing contacts anything. The hub is held only by six M3 screws bridging a
1.2 mm air gap while transmitting 6 Nm. It also makes the reported 4.2 mm thread
engagement actually 3.2 mm, because the screw crosses 1.6 mm of hub and then
1.2 mm of nothing.

**Fix.** Delete the register pocket entirely. A flat hub face at 18.95 seats on
the boss top and clears the housing by 1 mm without needing any feature — the
pocket as drawn opens away from the actuator and cannot pilot on anything. Then
set `hubThickness = 5mm`: the counterbore floor lands at 20.75, leaving 1.8 mm of
material, and an M3 × 6 gives exactly the 4.2 mm engagement you reported into the
5 mm of available thread.

If you want a positive pilot, add a lip at ID Ø30.3 projecting about 0.6 mm
**towards** the actuator, sitting in the annular groove between the boss and the
housing bore. Check it clears the housing face by at least 0.3 mm.

**This cascades.** `hubOuterFaceX` becomes 23.95, so `bearingCenterX` becomes
28.45 and the span becomes 47.4 mm. Re-report both.

## Defect 2 — the 110° stop pads have no axial overlap

The moving pad spans X 18.95 to 24.95. The fixed pad spans X 24.95 to 31.95. They
share one plane and no volume, so they can never touch.

The angular work is correct and worth keeping — contact reproduces at exactly
110.00° and surface clearance at 100° at 3.42 mm, from your `movingStopRadius`,
`movingStopStartAngle` and `fixedStopAngle` unchanged. The render looks right
because the YZ projection **is** right. Only the axial overlap is missing.

**Do not fix this by extending the fixed pad rearwards.** At R = 20 with a Ø6 pad
it reaches inward to r = 17, and the hub disc is Ø36, so it would foul the hub.
The radial band between the hub OD at r = 18 and the side arms at y = 23.5 is only
5.5 mm wide, which is not enough to move both pads outwards.

**Fix.** Give the moving stop a lug on the hub that projects **forward** past the
hub's outer face, into the fixed pad's X range — roughly X 23.95 to 30 once the
hub is 5 mm. Keep it at R = 20 and Ø6. That preserves every angle you computed,
so contact stays at exactly 110°, and both features then live outboard of the hub
disc where there is room.

Check the lug against the side arms through the full sweep. At R = 20 with a Ø6
pad the outer edge reaches r = 23 and the arms start at y = 23.5, so the clearance
is **0.5 mm** with full axial overlap. That is real but thin — report it, and say
whether you think it is enough.

## Defect 3 — the journal engages 1 mm, not 2.2 mm

`journalSeatCutter` spans X 22.75 to 24.95, a 2.2 mm seat. `journalRaw` starts at
23.95, so only 1 mm of the journal is in it and 1.2 mm of the seat is empty air.

The translate reads `hubOuterFaceX + journalLength / 2 - 1mm` where it wants
`- journalSeatDepth`.

Even at full depth, a Ø10 steel stub in 2.2 mm of PETG under a few hundred newtons
needs a retention feature. You already have that on your open-risk list; this
brief does not ask you to solve it, only to seat the part correctly and to say
what you would do about retention.

## Item 4 — the support reaction uses the wrong span, and that one is ours

The 48.4 mm you measured is rear-face-to-bearing. That is the **bracket's** lever
arm, and it is the right number for the bracket's own stress. It is not the
bearing's.

The 6800's reaction is set by its distance to the actuator's **internal output
bearing**, because those two straddle the moving assembly — hub, journal and shin.
That span is much shorter, plausibly 15 to 25 mm, which puts the reaction nearer
500 to 650 N than 307 N, or 55 to 70% of the 6800's 925 N static rating under a
landing impact.

You took 48.4 mm because `NOTES.md` framed it that way, and that text was written
outside Design Studio before this module existed. The framing error is inherited,
not yours.

**What to do.** Re-derive the reaction from the moving assembly's actual supports.
The internal bearing position is unpublished, so give it as a range with your
assumption stated, and check the 6800 against its static rating at the pessimistic
end. If it does not survive, say so and propose an alternative — do not silently
upsize the bearing, because a bigger bearing costs mass and the headroom is
already at its limit. Correct the span discussion in `NOTES.md` while you are
there.

## What to hand back

- Each defect: what you changed, and the new X extents that prove it.
- The revised span and reaction, with the internal-bearing assumption stated.
- The stop lug's clearance to the side arms, and your judgement on it.
- The mass delta from the thinner hub and the new lug.
- Confirmation that all five files still execute and that the 110° stop still
  meets, now with real contact area.

Update [`NOTES.md`](NOTES.md), [`CHECKLIST.md`](CHECKLIST.md) and
[`BOM.md`](BOM.md).

Report only what you measured in the model you just changed, and say where you
read each number. The three defects above were all invisible in a render and only
appeared in the station arithmetic, so a visual confirmation is not evidence that
a feature engages. Where a number depends on something unpublished, give the range
and name the assumption rather than picking a single figure.

Do not change any frozen parameter. Do not touch anything outside the knee.
