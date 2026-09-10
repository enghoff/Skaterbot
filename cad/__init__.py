"""The robot's CAD, in build123d.

Ported from the KCL that built it until September 2026; the migration and the
gates it is checked against are in docs/BUILD123D_MIGRATION.md.

The split that lib/ and the project root used to make -- geometry-free modules
below, body-building modules above -- does not need enforcing here. Importing a
Python module runs it, but a module that only defines functions and constants
builds nothing, and a scene assembles what it asks for by calling functions
rather than by importing whichever files happen to leave solids lying about.
"""
