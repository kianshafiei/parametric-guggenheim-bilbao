#! python3
"""Slow 360-degree orbit around the museum for the final shot (about 30 s)."""
import math, time
import Rhino, Rhino.Geometry as rg
doc = Rhino.RhinoDoc.ActiveDoc
view = doc.Views.ActiveView
vp = view.ActiveViewport
target = rg.Point3d(15, -5, 18)
r, h = 270.0, 75.0
a0 = math.atan2(230 - target.Y, -120 - target.X)   # start at the river-bank view
N = 360
for i in range(N + 1):
    a = a0 + 2 * math.pi * i / N
    cam = rg.Point3d(target.X + r * math.cos(a), target.Y + r * math.sin(a), h)
    vp.SetCameraLocations(target, cam)
    view.Redraw()
    Rhino.RhinoApp.Wait()
    time.sleep(0.07)
vp.SetCameraLocations(target, rg.Point3d(-120, 230, 55))
view.Redraw()
