
# ================================================================== Rhino / Grasshopper layer
# Inputs (all optional, Python 3 Script component in Rhino 8):
#   belly, pinch, rise, lean, twist   -> the sail rule
#   panel                             -> titanium panel length in m (real panels are 0.6 x 0.3)
#   skin                              -> True to build the fish-scale panels (slower)
#   stage                             -> 0..7, builds the museum up step by step (default 7 = all)
# Outputs: footprints, stone, titanium, roofs, glass, panels, bridge, ground, water, info
import Rhino.Geometry as rg
import Rhino

TOL = 0.01


def _in(name, default):
    v = globals().get(name)
    return default if v is None else v


P3 = lambda p: rg.Point3d(p[0], p[1], p[2] if len(p) > 2 else 0.0)


def closed_curve(loop):
    return rg.Curve.CreateInterpolatedCurve([P3(p) for p in loop], 3, rg.CurveKnotStyle.ChordPeriodic)


def open_curve(row):
    return rg.Curve.CreateInterpolatedCurve([P3(p) for p in row], 3)


def polyline(pts, z=0.0, close=False):
    ps = [rg.Point3d(p[0], p[1], z) for p in pts]
    if close and ps[0].DistanceTo(ps[-1]) > TOL:
        ps.append(ps[0])
    return rg.PolylineCurve(ps)


def loft(curves, closed=False):
    b = rg.Brep.CreateFromLoft(curves, rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, closed)
    return b[0] if b else None


def sail_brep(sections):
    """Loft the stacked loops, close the flat bottom, patch the warped top."""
    crvs = [closed_curve(s) for s in sections]
    b = loft(crvs)
    if b is None:
        return None, None
    b = b.CapPlanarHoles(TOL) or b   # flat floor; the top already closes to a ridge
    return b, None


def fish_scales(breps, size, lift):
    """Staggered, slightly lifted quads on every titanium face -> one mesh (fast to display)."""
    m = rg.Mesh()
    n = 0
    w, hgt = size, size * 0.5  # real panels are 2:1 (60 x 30 cm)
    for b in breps:
        if b is None:
            continue
        for f in b.Faces:
            s = f.UnderlyingSurface()
            du, dv = s.Domain(0), s.Domain(1)
            # physical lengths along the two directions, measured on the mid isocurves
            cu = s.IsoCurve(0, dv.Mid)
            cv = s.IsoCurve(1, du.Mid)
            Lu = cu.GetLength() if cu else 0
            Lv = cv.GetLength() if cv else 0
            if Lu < size or Lv < size * 0.5:
                continue
            nu, nv = max(2, int(Lu / w)), max(2, int(Lv / hgt))
            if nu * nv > 40000:  # keep the preview responsive
                k = (nu * nv / 40000.0) ** 0.5
                nu, nv = int(nu / k), int(nv / k)
            gap = 0.08
            for j in range(nv):
                off = 0.5 if j % 2 else 0.0
                for i in range(nu):
                    u0 = du.ParameterAt((i + off + gap) / nu)
                    u1 = du.ParameterAt(min(1.0, (i + off + 1 - gap) / nu))
                    v0 = dv.ParameterAt((j + gap) / nv)
                    v1 = dv.ParameterAt((j + 1 - gap) / nv)
                    if u0 >= du.Max:
                        continue
                    pts = []
                    for (u, v, up) in ((u0, v0, lift), (u1, v0, lift), (u1, v1, 0.0), (u0, v1, 0.0)):
                        if f.IsPointOnFace(u, v) == rg.PointFaceRelation.Exterior:
                            pts = None
                            break
                        p = s.PointAt(u, v)
                        nrm = s.NormalAt(u, v)
                        if f.OrientationIsReversed:
                            nrm.Reverse()
                        pts.append(p + nrm * up)
                    if not pts:
                        continue
                    a = m.Vertices.Count
                    for p in pts:
                        m.Vertices.Add(p)
                    m.Faces.AddFace(a, a + 1, a + 2, a + 3)
                    n += 1
    m.Normals.ComputeNormals()
    m.Compact()
    return m, n


def compute(params):
    """Build every element once for a given set of rule parameters."""
    M = build(OSM_DATA, params)
    G = {}
    G["outline"] = [polyline(M["outline"], 0.0, True)]
    G["parts"] = [polyline(P, 0.0, True) for t, P in parse(OSM_DATA) if t.startswith("P")]

    stone = []
    for s in M["stone"]:
        c = polyline(s["poly"], s["z0"], True)
        srf = rg.Surface.CreateExtrusion(c, rg.Vector3d(0, 0, s["h"]))
        if srf:
            b = srf.ToBrep().CapPlanarHoles(TOL)
            stone.append(b or srf.ToBrep())
    G["stone"] = stone

    G["sails"] = [b for b in (sail_brep(h["sections"])[0] for h in M["hulls"]) if b]
    g104 = [b for b in (sail_brep(M[n])[0] for n in ("tower", "hook")) if b]
    gal = loft([open_curve(s) for s in M["gallery"]])
    if gal:
        g104.append(gal)
    G["gallery"] = g104

    G["petals"] = [b for b in (loft([open_curve(r) for r in pet]) for pet in M["petals"]) if b]
    glass = []
    ac = M["atrium_centre"]
    for pet in M["petals"]:  # ruled glass walls from the river-facing petal rims down to the ground
        rim = pet[2]
        mid = rim[len(rim) // 2]
        if mid[1] - ac[1] > -2.0:
            top = open_curve(rim)
            bot = open_curve([(x, y, 0.0) for x, y, z in rim])
            g = rg.Brep.CreateFromLoft([bot, top], rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Straight, False)
            if g:
                glass.append(g[0])
    G["glass"] = glass

    # La Salve bridge: deck ribbon between the two OSM edge lines, rising to the north
    B = M["bridge"]
    west = sorted(set(B[1] + B[0][1:] + B[3][1:]), key=lambda p: -p[1])
    east = sorted(set(B[4] + B[2][1:]), key=lambda p: -p[1])
    clip = lambda pts: [p for p in pts if -62 <= p[1] <= 110]
    dz = lambda y: M["deck_z"] + 0.05 * y
    bridge = []
    we = rg.Curve.CreateInterpolatedCurve([rg.Point3d(x, y, dz(y)) for x, y in clip(west)], 3)
    ea = rg.Curve.CreateInterpolatedCurve([rg.Point3d(x, y, dz(y)) for x, y in clip(east)], 3)
    deck = loft([we, ea])
    if deck:
        bridge.append(deck)

        def x_at(chain, y):
            ch = sorted(chain, key=lambda p: p[1])
            for (x0, y0), (x1, y1) in zip(ch[:-1], ch[1:]):
                if y0 <= y <= y1:
                    return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
            return ch[0][0]
        for y in (-30.0, 45.0):  # two piers on the deck centre line
            x = 0.5 * (x_at(west, y) + x_at(east, y))
            pier = rg.Cylinder(rg.Circle(rg.Plane(rg.Point3d(x, y, 0), rg.Vector3d.ZAxis), 2.2), dz(y) - 1.5)
            bridge.append(pier.ToBrep(True, True))
    G["bridge"] = bridge

    quay = M["quay"][0] + M["quay"][1][1:] + M["quay"][2][1:]
    G["ground"] = list(rg.Brep.CreatePlanarBreps(polyline(quay + [(360, -160), (-120, -160)], 0.0, True), TOL) or [])
    G["water"] = list(rg.Brep.CreatePlanarBreps(polyline(quay + [(360, 260), (-120, 260)], -2.5, True), TOL) or [])
    return G


# ---- inputs, cache (moving the step slider must be instant), and the build-up steps
params = dict(belly=_in("belly", 0.22), pinch=_in("pinch", 0.55), rise=_in("rise", 0.35),
              lean=_in("lean", 0.15), twist=_in("twist", 8.0))
step = int(_in("stage", 7))
psize = float(_in("panel", 2.4))
try:
    import scriptcontext as _sc
    CACHE = _sc.sticky.setdefault("gugg_cache", {})
except Exception:
    CACHE = {}
key = tuple(round(float(params[k]), 4) for k in ("belly", "pinch", "rise", "lean", "twist"))
if CACHE.get("key") != key:
    CACHE.clear()
    CACHE["key"] = key
    CACHE["G"] = compute(params)
G = CACHE["G"]

STEPS = ["0  empty site",
         "1  site: OpenStreetMap footprints, quay and the Nervion",
         "2  La Salve bridge",
         "3  rule A: orthogonal parts -> limestone blocks",
         "4  rule B: free-form parts -> titanium sails (belly, pinch, rise, lean, twist)",
         "5  Gallery 104 under the bridge, the tower and the hook",
         "6  atrium: a flower of petals with glass to the river",
         "7  titanium skin: staggered fish-scale panels"]
step = max(0, min(step, len(STEPS) - 1))

footprints = (G["outline"] + G["parts"]) if 1 <= step <= 3 else []
ground = G["ground"] if step >= 1 else []
water = G["water"] if step >= 1 else []
bridge = G["bridge"] if step >= 2 else []
stone = G["stone"] if step >= 3 else []
titanium = (G["sails"] if step >= 4 else []) + (G["gallery"] if step >= 5 else [])
roofs = G["petals"] if step >= 6 else []
glass = G["glass"] if step >= 6 else []

panels = None
n_panels = 0
if step >= 7 or _in("skin", False):
    pk = ("panels", psize, len(titanium), len(roofs))
    if pk not in CACHE:
        CACHE[pk] = fish_scales(titanium + roofs, psize, psize * 0.06)
    panels, n_panels = CACHE[pk]

area_ti = sum(b.GetArea() for b in titanium + roofs if b)
info = ("Step %s\nstone blocks: %d | titanium volumes: %d | titanium area ~ %d m2\n"
        "panels shown: %d at %.1f m | real panels are 0.6 x 0.3 m -> ~%d for this area"
        % (STEPS[step], len(stone), len(titanium), area_ti, n_panels, psize, area_ti / 0.18 if area_ti else 0))


# ---------------------------------------------------------------- run outside Grasshopper -> bake to layers
if "ghenv" not in globals():
    import scriptcontext as sc
    import System.Drawing as SD
    doc = Rhino.RhinoDoc.ActiveDoc
    sc.doc = doc
    COLORS = {"footprints": (90, 90, 90), "stone": (214, 196, 160), "titanium": (190, 196, 204),
              "roofs": (170, 178, 190), "glass": (120, 170, 210), "panels": (205, 210, 216),
              "bridge": (110, 60, 50), "ground": (225, 222, 215), "water": (60, 110, 140)}
    parent = doc.Layers.FindName("Guggenheim")
    if parent is None:
        doc.Layers.Add("Guggenheim", SD.Color.Black)
        parent = doc.Layers.FindName("Guggenheim")
    for name, items in (("footprints", footprints), ("stone", stone), ("titanium", titanium),
                        ("roofs", roofs), ("glass", glass), ("panels", [panels] if panels else []),
                        ("bridge", bridge), ("ground", list(ground or [])), ("water", list(water or []))):
        full = "Guggenheim::" + name
        idx = doc.Layers.FindByFullPath(full, -1)
        if idx < 0:
            ly = Rhino.DocObjects.Layer()
            ly.Name = name
            ly.ParentLayerId = parent.Id
            ly.Color = SD.Color.FromArgb(*COLORS[name])
            idx = doc.Layers.Add(ly)
        else:  # rerun: clear the old geometry on this layer
            for o in doc.Objects.FindByLayer(doc.Layers[idx]) or []:
                doc.Objects.Delete(o, True)
        att = Rhino.DocObjects.ObjectAttributes()
        att.LayerIndex = idx
        for g in items:
            if g is None:
                continue
            if isinstance(g, rg.Brep):
                doc.Objects.AddBrep(g, att)
            elif isinstance(g, rg.Mesh):
                doc.Objects.AddMesh(g, att)
            elif isinstance(g, rg.Curve):
                doc.Objects.AddCurve(g, att)
    # camera: the classic view from the north bank of the Nervion, looking south-east
    view = doc.Views.ActiveView
    if view is not None:
        vp = view.ActiveViewport
        if vp.IsPerspectiveProjection:
            vp.Camera35mmLensLength = 35
            vp.SetCameraLocations(rg.Point3d(25, -15, 18), rg.Point3d(-120, 230, 55))
    doc.Views.Redraw()
    print(info)
