"""Pure-python geometry core for the Guggenheim Bilbao study (no Rhino needed).

Units: metres. x = east, y = north, z = up from the riverside promenade.
Footprints and storey counts come from OpenStreetMap (OSM), (c) OpenStreetMap contributors, ODbL.
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
