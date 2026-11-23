#! python3
"""GUGGENHEIM BILBAO - a parametric reading of a non-parametric building
Grasshopper > Python 3 Script component (Rhino 8). Paste this whole file in.

Real inputs: footprint + storey counts of every building part from OpenStreetMap
((c) OpenStreetMap contributors, ODbL), La Salve bridge, river edge.
Published facts used: ~50 m atrium, 130 m Gallery 104, titanium panels 0.6 x 0.3 m.
The rule: orthogonal footprints -> limestone boxes; free-form footprints -> 'sails' that
belly out, lean away from the atrium, twist, and pinch to a ridge. One rule, every volume.
"""
import math

LEVEL_H = 4.0  # m per storey: calibrates the tallest OSM part (13 storeys) to the ~50 m atrium


# ------------------------------------------------------------------ data
def parse(text):
    out = []
    for line in text.strip().splitlines():
        tag, body = line.split(" ", 1)
        pts = [tuple(int(v) / 10.0 for v in p.split()) for p in body.split(",")]
        out.append((tag, pts))
    return out


def area(P):
    return 0.5 * sum(P[i][0] * P[i + 1][1] - P[i + 1][0] * P[i][1] for i in range(len(P) - 1))


def centroid(P):
    a = area(P)
    cx = cy = 0.0
    for i in range(len(P) - 1):
        f = P[i][0] * P[i + 1][1] - P[i + 1][0] * P[i][1]
        cx += (P[i][0] + P[i + 1][0]) * f
        cy += (P[i][1] + P[i + 1][1]) * f
    return (cx / (6 * a), cy / (6 * a))


def orthogonality(P):
    """Share of the perimeter running along one dominant axis or its perpendicular (within 8 deg).
    Gehry's limestone galleries are orthogonal boxes; the titanium ones are free-form."""
    segs = []
    for i in range(len(P) - 1):
        dx, dy = P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]
        L = math.hypot(dx, dy)
        if L > 1e-6:
            segs.append((math.degrees(math.atan2(dy, dx)) % 90.0, L))
    tot = sum(L for _, L in segs)
    best = 0.0
    for a0, _ in segs:  # try each edge direction as the dominant axis
        s = sum(L for a, L in segs if min(abs(a - a0), 90 - abs(a - a0)) < 8.0)
        best = max(best, s / tot)
    return best


# ------------------------------------------------------------------ curves
def resample_closed(P, n):
    """n points evenly spaced along a closed polyline (P[0] == P[-1])."""
    seg = [math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]) for i in range(len(P) - 1)]
    total = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(n):
        d = total * k / n
        while acc + seg[i] < d:
            acc += seg[i]
            i += 1
        t = (d - acc) / seg[i] if seg[i] else 0
        out.append((P[i][0] + t * (P[i + 1][0] - P[i][0]), P[i][1] + t * (P[i + 1][1] - P[i][1])))
    return out


def smooth_closed(Q, iters, keep_area=True):
    """Laplacian smoothing of a closed point loop, rescaled to keep the original area."""
    a0 = abs(area(Q + [Q[0]]))
    c = centroid(Q + [Q[0]])
    n = len(Q)
    for _ in range(iters):
        Q = [((Q[i - 1][0] + 2 * Q[i][0] + Q[(i + 1) % n][0]) / 4, (Q[i - 1][1] + 2 * Q[i][1] + Q[(i + 1) % n][1]) / 4)
             for i in range(n)]
    if keep_area:
        a1 = abs(area(Q + [Q[0]]))
        s = math.sqrt(a0 / a1) if a1 > 0 else 1
        Q = [(c[0] + (x - c[0]) * s, c[1] + (y - c[1]) * s) for x, y in Q]
    return Q


# ------------------------------------------------------------------ the rule
def hull_sections(foot, z0, h, lean_dir, bulge=0.12, lean=0.18, twist=6.0, taper=0.30, n_sec=7, seed=0):
    """Turn a footprint into stacked section loops for a Gehry-like billowing volume.

    Every section is the footprint scaled by s(t) (bulges out then pulls in near the top),
    shifted along lean_dir by lean*h*t^2 (volumes lean away from the atrium like petals),
    and rotated by twist*t degrees about its centre. Small per-volume variation via seed.
    """
    rnd = _rng(seed)
    bulge *= 0.7 + 0.6 * rnd()
    lean *= 0.6 + 0.8 * rnd()
    twist *= (1 if rnd() > 0.5 else -1) * (0.5 + rnd())
    c = centroid(foot + [foot[0]])
    secs = []
    for k in range(n_sec):
        t = k / (n_sec - 1.0)
        s = 1 + bulge * math.sin(math.pi * min(1.0, t * 1.15)) - taper * t ** 3
        a = math.radians(twist * t)
        dx, dy = lean_dir[0] * lean * h * t * t, lean_dir[1] * lean * h * t * t
        ca, sa = math.cos(a), math.sin(a)
        z = z0 + h * t
        loop = []
        for x, y in foot:
            px, py = (x - c[0]) * s, (y - c[1]) * s
            loop.append((c[0] + ca * px - sa * py + dx, c[1] + sa * px + ca * py + dy, z))
        secs.append(loop)
    return secs


def fish_gallery_sections(outline, x_from, x_to, n, h_profile, ymin_clip=-15.0, ymax_clip=40.0, roundness=2.6):
    """Gallery 104: an upturned-boat hull. For each x station, take the outline's y-extent as the
    width and build a superellipse arch whose height follows h_profile(x)."""
    secs = []
    for k in range(n):
        x = x_from + (x_to - x_from) * k / (n - 1.0)
        ys = _y_hits(outline, x)
        ys = [y for y in ys if ymin_clip <= y <= ymax_clip]
        if len(ys) < 2:
            continue
        y0, y1 = min(ys), max(ys)
        yc, w = (y0 + y1) / 2, (y1 - y0) / 2
        H = h_profile(x)
        loop = []
        m = 24
        for j in range(m + 1):  # arch from south foot over the top to north foot
            th = math.pi * j / m
            cy, sz = math.cos(th), math.sin(th)
            yy = yc - w * _sgnpow(cy, 2.0 / roundness)
            zz = H * _sgnpow(sz, 2.0 / roundness)
            loop.append((x, yy, zz))
        secs.append(loop)
    return secs


def flower_petals(center, z_top, n=7, r_rim=22.0, z_rim=30.0, curl=0.35, seed=3):
    """Atrium 'flower': petals radiating from a high centre. Each petal is three curves
    (spine root, mid, tip) given as point lists; Rhino lofts them."""
    rnd = _rng(seed)
    petals = []
    for i in range(n):
        a0 = 2 * math.pi * i / n + 0.25 * (rnd() - 0.5)
        span = 2 * math.pi / n * (0.75 + 0.35 * rnd())
        r = r_rim * (0.8 + 0.4 * rnd())
        zr = z_rim + 8 * (rnd() - 0.5)
        rows = []
        for f, zf, wf in [(0.08, 1.0, 0.25), (0.45, 0.45, 0.85), (0.8, 0.05, 1.0), (1.0, 0.25, 0.8)]:
            row = []
            for j in range(7):
                a = a0 + span * (j / 6.0 - 0.5) * wf
                rr = r * f * (1 + curl * math.sin(math.pi * j / 6.0) * (1 - f))
                z = zr + (z_top - zr) * zf + curl * 4 * math.sin(math.pi * j / 6.0) * f
                row.append((center[0] + rr * math.cos(a), center[1] + rr * math.sin(a), z))
            rows.append(row)
        petals.append(rows)
    return petals


# ------------------------------------------------------------------ helpers
def _rng(seed):
    state = [seed * 9301 + 49297]

    def r():
        state[0] = (state[0] * 9301 + 49297) % 233280
        return state[0] / 233280.0
    r()
    return r


def _sgnpow(v, p):
    return math.copysign(abs(v) ** p, v)


def _y_hits(P, x):
    ys = []
    for i in range(len(P) - 1):
        (x0, y0), (x1, y1) = P[i], P[i + 1]
        if (x0 - x) * (x1 - x) <= 0 and x0 != x1:
            ys.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return ys


# ------------------------------------------------------------------ assembly
STONE_THRESHOLD = 0.70


def build(data_text, params=None):
    """Return every element as plain data: stone boxes, hull sections, gallery sections,
    tower/hook sections, petals, bridge, river edge. Rhino only has to loft/extrude."""
    p = dict(belly=0.22, pinch=0.55, rise=0.35, lean=0.15, twist=8.0, n_sec=8, smooth=6, res=48,
             gallery_h0=22.0, gallery_h1=16.0, tower_h=40.0, petals=7, deck_z=22.0)
    p.update(params or {})
    D = parse(data_text)
    outline = D[0][1]
    parts = [(t, P) for t, P in D if t.startswith("P")]
    out = dict(outline=outline, stone=[], hulls=[], bridge=[], quay=[])

    # atrium centre = area-weighted centre of the tall curved parts (>= 9 storeys)
    tall = [(abs(area(P)), centroid(P)) for t, P in parts if int(t[1:].split("/")[0]) >= 9]
    W = sum(a for a, _ in tall)
    ac = (sum(a * c[0] for a, c in tall) / W, sum(a * c[1] for a, c in tall) / W)
    out["atrium_centre"] = ac

    for i, (t, P) in enumerate(parts):
        lv, mn = (int(v) for v in t[1:].split("/"))
        lv = max(lv, 1)
        z0, h = mn * LEVEL_H, (lv - mn) * LEVEL_H
        if orthogonality(P) >= STONE_THRESHOLD:
            out["stone"].append(dict(poly=P, z0=z0, h=h, idx=i))
            continue
        c = centroid(P)
        d = (c[0] - ac[0], c[1] - ac[1])
        L = math.hypot(*d) or 1.0
        lean_dir = (d[0] / L, d[1] / L)
        foot = smooth_closed(resample_closed(P, p["res"]), p["smooth"])
        secs = sail_sections(foot, z0, h, lean_dir, p["belly"], p["pinch"], p["rise"], p["lean"], p["twist"], p["n_sec"], seed=i + 1)
        out["hulls"].append(dict(sections=secs, idx=i, levels=lv, atrium=lv >= 9))

    # Gallery 104: upturned boat from the atrium to the bridge
    def H(x):
        f = min(1.0, max(0.0, (x - 20.0) / 90.0))
        return p["gallery_h0"] + (p["gallery_h1"] - p["gallery_h0"]) * f + 1.2 * math.sin(x / 9.0) + 0.5 * math.sin(x / 4.3)
    out["gallery"] = fish_gallery_sections(outline, 22.0, 112.0, 14, H)

    # tower beyond the bridge and the hook beside it (sub-loops of the OSM outline)
    tower = outline[13:23] + [(112.0, -2.8)]
    hook = outline[1:13]
    for name, poly, h, tw in [("tower", tower, p["tower_h"], 22.0), ("hook", hook, 12.0, 4.0)]:
        foot = smooth_closed(resample_closed(poly + [poly[0]], p["res"]), p["smooth"])
        c = centroid(foot + [foot[0]])
        d = (c[0] - ac[0], c[1] - ac[1]); L = math.hypot(*d)
        secs = sail_sections(foot, 0.0, h, (d[0] / L, d[1] / L), p["belly"], p["pinch"], p["rise"], p["lean"] * 0.6, tw, p["n_sec"], seed=99 if name == "tower" else 77)
        out[name] = secs

    out["petals"] = flower_petals(ac, z_top=13 * LEVEL_H + 4.0, n=p["petals"], r_rim=20.0, z_rim=34.0)
    for t, P in D:
        if t == "B":
            out["bridge"].append(P)
        elif t == "Q":
            out["quay"].append(P)
    out["deck_z"] = p["deck_z"]
    return out


def principal_axis(P):
    """Unit vector of the footprint's long axis (PCA of its points)."""
    c = centroid(P + [P[0]]) if P[0] != P[-1] else centroid(P)
    sxx = sum((x - c[0]) ** 2 for x, y in P); syy = sum((y - c[1]) ** 2 for x, y in P)
    sxy = sum((x - c[0]) * (y - c[1]) for x, y in P)
    a = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return (math.cos(a), math.sin(a))


def sail_sections(foot, z0, h, lean_dir, belly=0.22, pinch=0.80, rise=0.35, lean=0.15, twist=8.0, n_sec=8, seed=0):
    """Gehry 'sail' rule. Work in the footprint's own frame: u = long axis, v = across.
    - the side facing lean_dir bellies out (asymmetric bulge, strongest mid-height)
    - v is pinched towards the top so the volume closes to a crisp ridge, not a dome
    - the ridge rises towards one end (a sail tip), the whole volume leans and twists slightly
    """
    rnd = _rng(seed)
    belly *= 0.6 + 0.8 * rnd()
    rise *= (1 if rnd() > 0.35 else -1) * (0.5 + rnd())
    lean *= 0.5 + rnd()
    twist *= (1 if rnd() > 0.5 else -1) * (0.4 + rnd())
    c = centroid(foot + [foot[0]])
    ux, uy = principal_axis(foot)
    vx, vy = -uy, ux
    if vx * lean_dir[0] + vy * lean_dir[1] < 0:  # make +v face the lean (belly) side
        vx, vy = -vx, -vy
    loc = [((x - c[0]) * ux + (y - c[1]) * uy, (x - c[0]) * vx + (y - c[1]) * vy) for x, y in foot]
    umax = max(abs(u) for u, _ in loc) or 1.0
    secs = []
    for k in range(n_sec):
        t = k / (n_sec - 1.0)
        mid = math.sin(math.pi * min(1.0, t * 1.1))
        sv_back = (1 + 0.25 * belly * mid) * (1 - pinch * t ** 2.2)
        sv_front = (1 + belly * mid) * (1 - pinch * t ** 2.2)
        su = 1 + 0.35 * belly * mid - 0.15 * t ** 2
        a = math.radians(twist * t)
        ca, sa = math.cos(a), math.sin(a)
        dl = lean * h * t * t
        loop = []
        for u, v in loc:
            uu = u * su
            vv = v * (sv_front if v > 0 else sv_back)
            ru, rv = ca * uu - sa * vv, sa * uu + ca * vv
            x = c[0] + ru * ux + rv * vx + lean_dir[0] * dl
            y = c[1] + ru * uy + rv * vy + lean_dir[1] * dl
            z = z0 + h * t * (1 + rise * (u / umax) * t)
            loop.append((x, y, z))
        secs.append(loop)
    # close the volume with a thin ridge just above the last section (no flat lid)
    zt = [p[2] for p in secs[-1]]
    ridge = []
    for (u, v), p in zip(loc, secs[-1]):
        q = 1 - (u / umax) ** 2
        cx = sum(pp[0] for pp in secs[-1]) / len(secs[-1])
        cy = sum(pp[1] for pp in secs[-1]) / len(secs[-1])
        # pull each point 95% of the way to the section's centre line (across v only)
        vv = (p[0] - cx) * vx + (p[1] - cy) * vy
        ridge.append((p[0] - 0.95 * vv * vx, p[1] - 0.95 * vv * vy, p[2] + 0.06 * h * max(q, 0.0) + 0.3))
    secs.append(ridge)
    return secs


OSM_DATA = """
M 720 316,855 263,865 276,908 332,874 367,869 390,873 430,886 467,899 504,965 471,1002 438,1032 390,1049 299,1096 218,1123 192,1166 262,1273 195,1238 139,1304 93,1341 40,1345 -10,1325 -89,1210 -50,1030 -5,764 34,669 43,573 75,512 92,427 97,357 108,248 132,206 144,240 108,256 64,260 25,256 -22,249 -61,194 -80,122 -82,76 -71,21 -59,55 -114,40 -165,35 -185,94 -190,137 -200,176 -222,129 -414,71 -400,90 -445,36 -454,18 -517,-54 -531,-59 -555,-79 -659,-49 -702,-64 -741,-97 -784,-147 -823,-225 -847,-290 -841,-362 -795,-351 -769,-371 -767,-401 -789,-418 -810,-442 -767,-445 -725,-421 -685,-387 -685,-363 -704,-335 -743,-172 -545,-289 -529,-314 -432,-323 -391,-380 -421,-444 -432,-490 -430,-492 -344,-488 -273,-434 -175,-354 -11,-316 99,-381 94,-432 91,-495 9,-537 16,-601 25,-660 10,-686 -9,-719 -41,-760 -104,-812 -83,-849 -39,-812 6,-777 28,-771 47,-801 58,-816 119,-847 248,-802 262,-797 280,-838 334,-731 390,-699 289,-637 305,-697 464,-703 546,-674 596,-606 603,-508 592,-447 546,-429 524,-395 482,-366 406,-331 431,-362 468,-379 511,-379 559,-315 573,-243 588,-225 568,-166 578,-99 568,-17 534,-28 488,-12 434,120 447,234 451,371 438,496 398,720 316
P5/0 55 -114,21 -59,-29 -20,-15 108,-65 128,-106 141,-156 132,-204 123,-223 -24,-266 -356,-289 -529,-172 -545,-59 -555,-54 -531,18 -517,36 -454,90 -445,71 -400,-21 -371,-41 -365,-17 -192,35 -185,40 -165,55 -114
P7/0 -173 119,-250 -457,-127 -473,-50 102,-79 118,-107 125,-137 125,-173 119
P7/0 -17 -192,35 -185,94 -190,137 -200,176 -222,129 -414,71 -400,-21 -371,-41 -365,-17 -192
P5/0 -319 41,-280 22,-248 -2,-223 -24,-266 -356,-323 -391,-380 -421,-444 -432,-490 -430,-492 -344,-488 -273,-434 -175,-354 -11,-319 41
P6/0 -348 -71,-358 -112,-401 -87,-413 -140,-411 -179,-417 -211,-432 -231,-400 -246,-374 -254,-350 -248,-332 -231,-313 -220,-282 -226,-274 -181,-280 -131,-298 -101,-319 -75,-348 -71
P6/0 -789 225,-763 108,-474 175,-476 218,-485 259,-504 292,-789 225
P0/0 -731 390,-838 334,-797 280,-802 262,-847 248,-816 119,-801 58,-771 47,-777 28,-812 6,-849 -39,-812 -83,-760 -104,-719 -41,-686 -9,-660 10,-601 25,-537 16,-495 9,-432 91,-316 99,-369 160,-398 162,-426 184,-424 238,-411 281,-439 303,-495 303,-558 324,-637 305,-699 289,-731 390
P6/3 29 221,105 197,206 144,240 108,256 64,260 25,256 -22,249 -61,194 -80,122 -82,76 -71,21 -59,-29 -20,-15 108,29 115,55 121,55 160,44 193,29 221
P5/2 -697 464,-703 546,-674 596,-606 603,-508 592,-447 546,-395 482,-366 406,-411 281,-439 303,-495 303,-558 324,-637 305,-697 464
P6/0 -280 437,-261 521,-225 568,-243 588,-315 573,-379 559,-379 511,-362 468,-331 431,-366 406,-308 318,-302 417,-280 437
P7/0 -411 281,-439 303,-495 303,-558 324,-613 359,-591 476,-539 497,-487 508,-437 508,-395 482,-366 406,-411 281
P9/0 -106 141,-156 132,-204 123,-235 143,-243 197,-219 247,-206 279,-176 244,-148 203,-106 141
P11/0 -206 279,-154 253,-117 262,-89 288,-65 322,-63 383,-28 402,-8 424,-12 434,-28 488,-17 534,-99 568,-166 578,-225 568,-261 521,-280 437,-302 417,-308 318,-206 279
P13/0 -95 467,-182 471,-184 421,-174 365,-141 348,-95 409,-95 467
P10/0 -154 253,-117 262,-89 288,-65 322,-37 275,29 221,44 193,55 160,55 121,29 115,-15 108,-65 128,-106 141,-148 203,-176 244,-206 279,-154 253
P8/0 -8 424,68 434,122 434,168 415,213 370,224 322,226 247,174 247,83 264,35 288,-15 285,-37 275,-65 322,-63 383,-28 402,-8 424
P6/0 -189 -624,-256 -710,-226 -745,-200 -751,-176 -745,-128 -671,-189 -624
P5/0 -617 54,-537 16,-495 9,-432 91,-316 99,-369 160,-398 162,-426 184,-424 238,-411 281,-439 303,-495 303,-558 324,-637 305,-699 289,-802 262,-847 248,-816 119,-801 58,-582 113,-617 54
P9/0 -366 406,-308 318,-282 253,-274 216,-289 195,-369 160,-398 162,-426 184,-424 238,-411 281,-366 406
P5/0 -59 -555,-79 -659,-49 -702,-64 -741,-97 -784,-147 -823,-225 -847,-290 -841,-362 -795,-351 -769,-371 -767,-401 -789,-418 -810,-442 -767,-445 -725,-421 -685,-387 -685,-363 -704,-335 -743,-172 -545,-59 -555
B 2026 1675,1997 1578,1942 1436,1915 1370,1829 1226,1738 1103,1188 366,1032 111
B 2099 2210,2105 2063,2096 1962,2083 1889,2070 1804,2026 1675
B 1128 82,1273 320,1824 1060
B 1032 111,906 -116,809 -324,706 -615
B 792 -584,885 -364,982 -156,1128 82
Q -1122 664,-1028 733,-762 824
Q -762 824,-646 860,-549 889,-434 908,-353 922,-150 927,45 900,238 852,406 788,483 746,590 684
Q 590 684,740 591,1060 475,1462 339,1622 281,1814 152,2283 -164,2573 -409,2834 -690,3028 -899,3528 -1508
Q 44 -620,116 -611,256 -594,647 -561,925 -551,1112 -551,1321 -551,1567 -547,1645 -543,1665 -541,1706 -539
"""



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
