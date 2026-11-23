#! python3
"""Builds the Guggenheim Bilbao Grasshopper definition: one Python 3 component,
sliders for the sail rule, a toggle for the titanium skin, coloured previews, info panel.
Run from Rhino (Grasshopper open): _-RunPythonScript "<repo>/grasshopper/setup_gh.py"
"""
import os, traceback
import System
import System.Drawing as SD
import Rhino
import Grasshopper as gh
from Grasshopper.Kernel import GH_ParameterSide
from Grasshopper.Kernel.Special import GH_NumberSlider, GH_ColourSwatch, GH_Panel, GH_BooleanToggle
from Grasshopper.GUI.Base import GH_SliderAccuracy

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # pasted into the editor instead of run from disk
    HERE = os.getcwd()
LOG = []
def log(*a):
    LOG.append(" ".join(str(x) for x in a))

try:
    doc = gh.Instances.ActiveCanvas.Document
    if doc is None:
        raise Exception("open a Grasshopper document first")
    srv = gh.Instances.ComponentServer
    def proxy(name):
        return [p for p in srv.ObjectProxies if p.Desc.Name == name and not p.Obsolete][0]

    # start clean: remove any earlier attempt (Python 3 components named *Guggenheim*)
    MINE = {"Guggenheim", "stage", "belly", "pinch", "rise", "lean", "twist", "panel", "skin", "info",
            "footprints", "stone", "titanium", "roofs", "glass", "panels", "bridge", "ground", "water"}
    old = [o for o in doc.Objects if (o.NickName or "").replace(" colour", "") in MINE]
    for o in old:
        doc.RemoveObject(o, False)
    log("removed", len(old))
    X0, Y0 = 400.0, 100.0
    INS = [("stage", 0, 7, 0, 0), ("belly", 0.0, 0.6, 0.22, 2), ("pinch", 0.0, 0.9, 0.55, 2), ("rise", -0.6, 0.8, 0.35, 2),
           ("lean", 0.0, 0.4, 0.15, 2), ("twist", -30.0, 30.0, 8.0, 1), ("panel", 0.6, 6.0, 2.4, 1)]
    OUTS = ["footprints", "stone", "titanium", "roofs", "glass", "panels", "bridge", "ground", "water", "info"]

    # --- the script component
    c = proxy("Python 3 Script").CreateInstance()
    c.CreateAttributes()
    c.NickName = "Guggenheim"
    c.Attributes.Pivot = SD.PointF(X0, Y0)
    P = c.Params
    for p in list(P.Input):
        P.UnregisterInputParameter(p)
    for p in list(P.Output):
        if p.NickName != "out":
            P.UnregisterOutputParameter(p)
    for i, (n, lo, hi, v, d) in enumerate(INS + [("skin", 0, 0, 0, 0)]):
        p = c.CreateParameter(GH_ParameterSide.Input, i)
        p.Name = p.NickName = n
        p.Optional = True
        P.RegisterInputParam(p, i)
    base = P.Output.Count
    for j, n in enumerate(OUTS):
        p = c.CreateParameter(GH_ParameterSide.Output, base + j)
        p.Name = p.NickName = n
        P.RegisterOutputParam(p, base + j)
    P.OnParametersChanged()
    c.VariableParameterMaintenance()
    c.SetSource(open(os.path.join(HERE, "gugg_bilbao_gh.py"), encoding="utf-8").read())
    try:
        c.SetParametersToScript()
    except Exception as e:
        log("SetParametersToScript:", e)
    c.Hidden = True  # coloured custom previews below do the display
    doc.AddObject(c, False)
    c.Attributes.ExpireLayout()
    c.Attributes.PerformLayout()
    log("component ok; inputs", [p.NickName for p in P.Input], "outputs", [p.NickName for p in P.Output])

    # --- sliders + toggle
    for i, (n, lo, hi, v, d) in enumerate(INS):
        s = GH_NumberSlider()
        s.CreateAttributes()
        if d == 0:
            s.Slider.Type = GH_SliderAccuracy.Integer
        else:
            s.Slider.Type = GH_SliderAccuracy.Float
            s.Slider.DecimalPlaces = d
        s.Slider.Minimum = System.Decimal(lo)
        s.Slider.Maximum = System.Decimal(hi)
        s.SetSliderValue(System.Decimal(v))
        s.NickName = n
        s.Attributes.Pivot = SD.PointF(X0 - 260, Y0 - 40 + 26 * i)
        doc.AddObject(s, False)
        P.Input[i].AddSource(s)
    t = GH_BooleanToggle()
    t.CreateAttributes()
    t.Value = False
    t.NickName = "skin"
    t.Attributes.Pivot = SD.PointF(X0 - 200, Y0 - 40 + 26 * len(INS))
    doc.AddObject(t, False)
    P.Input[len(INS)].AddSource(t)
    log("sliders ok")

    # --- coloured previews
    COL = {"footprints": (255, 60, 60, 60), "stone": (255, 214, 196, 160), "titanium": (255, 196, 202, 210),
           "roofs": (255, 170, 178, 190), "glass": (110, 120, 180, 225), "panels": (255, 215, 220, 226),
           "bridge": (255, 120, 64, 52), "ground": (255, 222, 218, 208), "water": (255, 55, 100, 130)}
    cp_proxy = proxy("Custom Preview")
    out_by = {p.NickName: p for p in P.Output}
    for k, n in enumerate([n for n in OUTS if n != "info"]):
        y = Y0 - 80 + 62 * k
        sw = GH_ColourSwatch()
        sw.CreateAttributes()
        sw.SwatchColour = SD.Color.FromArgb(*COL[n])
        sw.NickName = n + " colour"
        sw.Attributes.Pivot = SD.PointF(X0 + 230, y + 22)
        doc.AddObject(sw, False)
        cp = cp_proxy.CreateInstance()
        cp.CreateAttributes()
        cp.NickName = n
        cp.Attributes.Pivot = SD.PointF(X0 + 430, y)
        doc.AddObject(cp, False)
        cp.Params.Input[0].AddSource(out_by[n])
        cp.Params.Input[1].AddSource(sw)
    pn = GH_Panel()
    pn.CreateAttributes()
    pn.NickName = "info"
    pn.Attributes.Bounds = SD.RectangleF(X0 - 260, Y0 + 230, 470, 70)
    pn.Attributes.Pivot = SD.PointF(X0 - 260, Y0 + 230)
    doc.AddObject(pn, False)
    pn.AddSource(out_by["info"])
    log("previews ok")

    # hide the earlier baked test geometry so only the live Grasshopper model shows
    rd = Rhino.RhinoDoc.ActiveDoc
    i = rd.Layers.FindByFullPath("Guggenheim", -1)
    if i >= 0:
        ly = rd.Layers[i]
        ly.IsVisible = False
        rd.Layers.Modify(ly, i, True)
    # camera: from the north bank of the Nervion, looking south-east at the museum
    vw = rd.Views.ActiveView
    if vw is not None and vw.ActiveViewport.IsPerspectiveProjection:
        vw.ActiveViewport.Camera35mmLensLength = 35
        vw.ActiveViewport.SetCameraLocations(Rhino.Geometry.Point3d(25, -15, 18), Rhino.Geometry.Point3d(-120, 230, 55))
    doc.NewSolution(False)
    gh.Instances.ActiveCanvas.Refresh()
    log("solution started")
except Exception:
    log(traceback.format_exc())
print("setup_gh:\n" + "\n".join(LOG))
