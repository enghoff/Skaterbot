"""The printed cap that clamps the wheel: a Ø22 cup in the hub's outboard seat.

Drawn on 6 October 2026 in place of the Ø30 penny washer that used to lie on the
hub's outer face, which nobody in India sells in a basket. The cap drops into the
outboard bearing seat the 608 came out of and lands on the hub's centre ridge,
and the M5 that clamps the wheel passes down through its floor, through the
ridge, and into the heat-set insert in the adapter's spigot.

What it is better at than the washer was is the way it carries the load. The
washer spanned the hub's Ø22 bore and was bent by the screw; the cap's walls
stand on the ridge and are squeezed end-on, and the only part of it that bends is
its 6 mm floor across the ridge's narrower bore. cad/wheeled_parameters.py has the
arithmetic beside wheelCapFloor.

The washer and the screw head sit inside it, the head flush with its outer end.
It is one solid of revolution on the wheel's axis, so like the adapter it is not
a handed part: the left wheel's is the right wheel's turned round, and one print
serves both.

On the robot on 7 November 2026 a cap was found partly damaged, most likely by
heat during the bench test, and its M5 had worked loose: the wheel slipped on the
adapter, and the robot could not stand when it was placed. The logs show it as the
robot no longer turning with its wheels from the 14:06 run on. The owner
re-tightened it, and expects it to come loose again, since a damaged floor no
longer holds the preload. What the caps on the robot were printed in is not
recorded (docs/ORDERS.md); the drawing assumes PA12.

So the same day the cap grew a boss under its floor, down into the ridge's bore:
narrower than the bore, so the cap still lands on the ridge as it did, and
stopping inside the ridge, so it bears on nothing and the clamp is unchanged.
It deepens the floor where the screw bends it and centres the cap in the hub.
cad/wheeled_parameters.py has its sizes beside wheelCapBossDiameter: Ø18.6 in
the Ø20 bore the owner measured, 9 deep in a ridge measured 10 long.
"""

from __future__ import annotations

from build123d import Cylinder, Plane, Pos, Rot

from cad.geometry import mirrored
from cad.wheeled_parameters import (
    wheelCapBore,
    wheelCapBossDiameter,
    wheelCapBossLength,
    wheelCapCounterbore,
    wheelCapDiameter,
    wheelCapFloor,
    wheelCapInnerX,
    wheelCapOuterX,
)


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


def wheelCapRight():
    """The +X hand: a Ø22 cup standing on the ridge, its floor inboard, and the
    boss under the floor reaching down into the ridge's bore.

    Both cutters run a millimetre past the faces they open through, so no wall
    of a cut is coplanar with a face of the body -- docs/KCL_GOTCHAS.md's
    coincident-face case, which OCCT is less fussy about but which costs nothing
    to avoid. The boss runs a millimetre up into the floor for the same reason,
    and is united before anything is cut, so the bore goes through both.
    """
    length = wheelCapOuterX - wheelCapInnerX
    blank = _disc(wheelCapDiameter, length, (wheelCapInnerX + wheelCapOuterX) / 2)

    bossInnerX = wheelCapInnerX - wheelCapBossLength
    bossLength = wheelCapBossLength + 1.0
    boss = _disc(wheelCapBossDiameter, bossLength, bossInnerX + bossLength / 2)

    pocketInnerX = wheelCapInnerX + wheelCapFloor
    pocketLength = wheelCapOuterX + 1.0 - pocketInnerX
    pocket = _disc(wheelCapCounterbore, pocketLength, pocketInnerX + pocketLength / 2)

    boreLength = wheelCapOuterX - bossInnerX + 2.0
    bore = _disc(wheelCapBore, boreLength, (bossInnerX + wheelCapOuterX) / 2)
    return blank + boss - pocket - bore


def wheelCapLeft():
    return mirrored(wheelCapRight(), Plane.YZ)
