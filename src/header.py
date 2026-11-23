"""GUGGENHEIM BILBAO - a parametric reading of a non-parametric building
Grasshopper > Python 3 Script component (Rhino 8). Paste this whole file in.

Real inputs: footprint + storey counts of every building part from OpenStreetMap
((c) OpenStreetMap contributors, ODbL), La Salve bridge, river edge.
Published facts used: ~50 m atrium, 130 m Gallery 104, titanium panels 0.6 x 0.3 m.
The rule: orthogonal footprints -> limestone boxes; free-form footprints -> 'sails' that
belly out, lean away from the atrium, twist, and pinch to a ridge. One rule, every volume.
"""
