#!/usr/bin/python3
"""Zonen-Kupfer ("orig_*") durch echte Leiterbahnen ersetzen.

Aufruf:  /usr/bin/python3 rekonstruktion/tracks.py <projektordner> [--plot bild.png]

Ablauf je Lage und Kupferinsel aus polys.json:
  1. Insel fein rastern (RES px/mm), Pads/Vias desselben Netzes (aus der .kicad_pcb) abziehen.
  2. Breite Bereiche (lokale Breite >= WIDE, morphologisches Öffnen über den Distanz-Transform)
     werden Flächen-Zonen mit Netz (Umriss = Originalpolygon geschnitten mit der Fläche), KiCad füllt sie.
  3. Rest: Zhang-Suen-Skelett -> Pfade zwischen End- und Knotenpunkten -> Douglas-Peucker,
     kurze Sporne weg. Breite = 2 x Distanz-Transform (Median), auf Eagle-Breiten abgerundet und
     zusätzlich so begrenzt, dass die Clearance zu fremdem Kupfer eingehalten wird.
  4. Endpunkte am Pad/Via desselben Netzes -> Segment zur Pad-/Via-Mitte;
     Endpunkte an einer Fläche -> EXT mm in die Fläche verlängern.
  5. Alte Zonen "orig_*" raus, Tracks und Flächen-Zonen rein. Die Zonen-Platine wird einmalig als
     rekonstruktion/<name>_zonen.kicad_pcb gesichert und bei jedem Lauf als Quelle benutzt.
"""
import sys, os, re, json, math, shutil, subprocess, tempfile
import numpy as np
from scipy import ndimage as ndi
from matplotlib.path import Path
import contourpy
import gc
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly
import pcbnew as K
gc.disable()   # SWIG-Objekte (an Zonen übergebene SHAPE_POLY_SETs) nicht vom GC einsammeln lassen

RES = 25.0          # px/mm
WIDE = 1.2          # mm, ab dieser lokalen Breite Fläche
CORE_MIN = 0.15     # mm², Mindestfläche des Kerns einer Fläche (sonst Knoten breiter Spuren)
MARGIN = 0.10       # mm, Pads/Vias beim Abziehen aufweiten
SNAP = 0.25         # mm, Fangabstand Endpunkt -> Pad/Via
EXT = 0.30          # mm, Verlängerung in eine Fläche
CLR = 0.08 + 0.03   # mm, Clearance + Reserve (auch fremde Spuren weichen um bis zu DP_EPS vom Kupfer ab)
EDGE_CLR = 0.07     # mm, Abstand zum Platinenrand (Edge.Cuts-Linie 0.1 breit -> 0.05 + Reserve)
DP_EPS = 0.04       # mm, Douglas-Peucker
TOL = float(os.environ.get('WTOL', '0.02'))  # mm, Messtoleranz beim Abrunden
EAGLE = [0.1524, 0.2032, 0.254, 0.3048, 0.4064, 0.508, 0.6096, 0.8128, 1.016]
WMIN = 0.1
MISS_TOL = 0.12     # mm, Kupfer weiter als das von Spur/Fläche/Pad weg gilt als nicht nachgebildet
MISS_FAT = 0.15     # mm, ... und so dick (halbe Dicke), dann ist es eine Fläche und keine Spur
MISS_AREA = 0.15    # mm², Mindestgröße dafür
OUT_TOL = 0.08      # mm, so weit darf eine Spur über das Originalkupfer hinausragen
THICK = 0.9         # mm, ab dieser Kupferbreite wird an Flächen angrenzendes Kupfer Teil der Fläche
MISS_GROW = 0.5     # mm, um so viel wird der Bereich als Fläche erweitert
LAY = {'F.Cu': K.F_Cu, 'In1.Cu': K.In1_Cu, 'In2.Cu': K.In2_Cu, 'B.Cu': K.B_Cu}
def mm(v): return K.FromMM(float(v))


def eagle_round(w):
    """größte Eagle-Breite <= w (+TOL); darunter auf 0.01 abgerundet, mind. WMIN"""
    c = [e for e in EAGLE if e <= w + TOL]
    if c: return c[-1]
    return max(WMIN, math.floor(w * 100) / 100)


def limit_round(w):
    """Clearance-Grenze: keine Toleranz nach oben"""
    c = [e for e in EAGLE if e <= w]
    if c: return c[-1]
    return math.floor(w * 100) / 100


# ------------------------------------------------------------------ Skelett
def zhang_suen(img):
    I = np.pad(img.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            P2 = I[:-2, 1:-1]; P3 = I[:-2, 2:]; P4 = I[1:-1, 2:]; P5 = I[2:, 2:]
            P6 = I[2:, 1:-1]; P7 = I[2:, :-2]; P8 = I[1:-1, :-2]; P9 = I[:-2, :-2]
            seq = [P2, P3, P4, P5, P6, P7, P8, P9, P2]
            B = P2 + P3 + P4 + P5 + P6 + P7 + P8 + P9
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
            c = (I[1:-1, 1:-1] == 1) & (B >= 2) & (B <= 6) & (A == 1)
            if step == 0: c &= (P2 * P4 * P6 == 0) & (P4 * P6 * P8 == 0)
            else: c &= (P2 * P4 * P8 == 0) & (P2 * P6 * P8 == 0)
            if c.any():
                I[1:-1, 1:-1][c] = 0; changed = True
        if not changed: break
    return I[1:-1, 1:-1].astype(bool)


NB = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]   # Ring N, NE, E, ...


def ring(S, r, c):
    h, w = S.shape
    return [bool(S[r + dr, c + dc]) if 0 <= r + dr < h and 0 <= c + dc < w else False for dr, dc in NB]


def runs(v):
    """Anzahl Zusammenhangsgruppen der Nachbarn (Ecke zwischen zwei orthogonalen zählt als verbunden)"""
    v = list(v)
    for i in (1, 3, 5, 7):
        if v[i - 1] and v[(i + 1) % 8]: v[i] = True
    if all(v): return 1
    return sum(1 for i in range(8) if not v[i - 1] and v[i])


def thin_corners(S):
    """überzählige Treppenpixel entfernen (Nachbarn bleiben ohne das Pixel zusammenhängend)"""
    S = S.copy()
    for _ in range(3):
        n = 0
        for r, c in zip(*np.nonzero(S)):
            v = ring(S, r, c)
            if sum(v) >= 2 and runs(v) == 1:
                # nur löschen, wenn das Pixel kein Linienende ist: zwei Nachbarn, die sich berühren
                S[r, c] = False; n += 1
        if not n: break
    return S


def degree(S):
    k = np.ones((3, 3), int); k[1, 1] = 0
    return ndi.convolve(S.astype(int), k, mode='constant') * S


def trace_paths(S):
    """Pfade zwischen Endpunkten/Knoten; Knoten = Cluster von Pixeln mit Grad >= 3"""
    D = degree(S)
    J = S & (D >= 3)
    jl, nj = ndi.label(J, np.ones((3, 3)))
    nodepos = ndi.center_of_mass(J, jl, range(1, nj + 1)) if nj else []
    h, w = S.shape
    def nbrs(p):
        r, c = p
        return [(r + dr, c + dc) for dr, dc in NB if 0 <= r + dr < h and 0 <= c + dc < w and S[r + dr, c + dc]]
    seen = set(); paths = []
    starts = [tuple(p) for p in np.argwhere(S & ((D == 1) | J))]
    for s in starts:
        for n in nbrs(s):
            if (s, n) in seen: continue
            if J[s] and J[n] and jl[s] == jl[n]: continue
            path = [s, n]; prev, cur = s, n
            while D[cur] == 2 and not J[cur]:
                nx = [q for q in nbrs(cur) if q != prev and q != path[-2]]
                if not nx: break
                # bevorzugt orthogonal fortsetzen, falls zwei Kandidaten
                nx.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
                prev, cur = cur, nx[0]; path.append(cur)
                if cur == s: break
            seen.add((s, n)); seen.add((path[-1], path[-2]))
            paths.append(path)
    # reine Ringe ohne Knoten
    rest = S.copy()
    for p in paths:
        for q in p: rest[q] = False
    lab, n = ndi.label(rest, np.ones((3, 3)))
    for i in range(1, n + 1):
        pts = [tuple(p) for p in np.argwhere(lab == i)]
        if len(pts) < 3: continue
        path = [pts[0]]; prev = None; cur = pts[0]
        while True:
            nx = [q for q in nbrs(cur) if q != prev and lab[q] == i and q not in path[1:]]
            if not nx: break
            prev, cur = cur, nx[0]; path.append(cur)
            if cur == path[0] or len(path) > len(pts) + 1: break
        paths.append(path)
    return paths, jl, nodepos


def dp(pts, eps):
    pts = np.asarray(pts, float)
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; d = b - a; L = np.hypot(*d)
    if L < 1e-9: dist = np.hypot(*(pts - a).T)
    else: dist = np.abs(d[0] * (pts[:, 1] - a[1]) - d[1] * (pts[:, 0] - a[0])) / L
    i = int(np.argmax(dist))
    if dist[i] > eps:
        l = dp(pts[:i + 1], eps); r = dp(pts[i:], eps)
        return np.vstack([l[:-1], r])
    return np.vstack([a, b])


STEPS = sorted(set(EAGLE + [0.14, 0.12, WMIN]))
DRC_TYPES = ('clearance', 'copper_edge_clearance', 'hole_clearance')


def drc_narrow(pcb, keepfiles, rounds=8):
    """DRC (mit Zonen-Neufüllung) laufen lassen und beteiligte Spuren schrittweise schmaler machen"""
    nfix = 0; unres = []
    for rnd in range(rounds):
        fd, tmp = tempfile.mkstemp(suffix='.json'); os.close(fd)
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--format', 'json', '-o', tmp, pcb],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        d = json.load(open(tmp)); os.unlink(tmp)
        bad = {}; push = {}
        for v in d['violations']:
            if v['type'] not in DRC_TYPES: continue
            m = re.search(r'(?:tatsächlich|actual) ([\d.,]+) mm', v['description'])
            need = re.search(r'(?:Freiraum|clearance) ([\d.,]+) mm', v['description'])
            for it in v['items']:
                if it['description'].startswith(('Leiterbahn', 'Track')):
                    bad[it['uuid']] = v['description'] + ' ' + it['description']
                    others = [o for o in v['items'] if o is not it]
                    if m and need and others and v['type'] != 'copper_edge_clearance':
                        dfc = float(need.group(1).replace(',', '.')) - float(m.group(1).replace(',', '.')) + 0.006
                        push.setdefault(it['uuid'], []).append((others[0]['pos']['x'], others[0]['pos']['y'], dfc))
        if not bad: break
        fd, tmp = tempfile.mkstemp(suffix='.json'); os.close(fd)
        json.dump({'bad': sorted(bad), 'push': push}, open(tmp, 'w'))
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '--narrow', pcb, tmp], capture_output=True, text=True)
        os.unlink(tmp)
        try: changed = int([l for l in r.stdout.splitlines() if l.startswith('NARROWED')][0].split()[1])
        except IndexError: raise RuntimeError('Verschmälern fehlgeschlagen: ' + r.stderr[-500:])
        nfix += changed
        for f, data in keepfiles.items(): open(f, 'wb').write(data)
        if not changed:
            unres = sorted(set(bad.values())); break
    else:
        unres = sorted(set(bad.values()))
    return nfix, unres


def narrow(pcb, uuids_json):
    """Unterprozess: genannte Spuren um eine Stufe schmaler machen"""
    J = json.load(open(uuids_json)); bad = set(J['bad']); push = J['push']
    b = K.LoadBoard(pcb); changed = 0
    tracks = [t for t in b.Tracks() if t.GetClass() == 'PCB_TRACK']
    for t in tracks:
        if t.m_Uuid.AsString() not in bad: continue
        w = K.ToMM(t.GetWidth())
        smaller = [x for x in STEPS if x < w - 1e-6]
        if smaller:
            t.SetWidth(mm(smaller[-1])); changed += 1
        elif t.m_Uuid.AsString() in push:
            # schon minimal breit: Segment um das fehlende Stück vom Hindernis wegschieben,
            # anhängende Endpunkte (gleiche Lage, gleiches Netz) wandern mit
            S_ = np.array([K.ToMM(t.GetStart().x), K.ToMM(t.GetStart().y)]); E_ = np.array([K.ToMM(t.GetEnd().x), K.ToMM(t.GetEnd().y)])
            mv = np.zeros(2)
            for ox, oy, dfc in push[t.m_Uuid.AsString()]:
                o = np.array([ox, oy]); d_ = E_ - S_; l2 = float(d_ @ d_)
                tt = 0.0 if l2 < 1e-12 else min(1.0, max(0.0, float((o - S_) @ d_) / l2))
                c_ = S_ + tt * d_; n_ = c_ - o
                if np.hypot(*n_) < 1e-6: continue
                mv += n_ / np.hypot(*n_) * dfc
            if not mv.any(): continue
            for P_ in (S_, E_):
                for u in tracks:
                    if u.GetLayer() != t.GetLayer() or u.GetNetCode() != t.GetNetCode(): continue
                    for get, set_ in ((u.GetStart, u.SetStart), (u.GetEnd, u.SetEnd)):
                        q = get()
                        if abs(K.ToMM(q.x) - P_[0]) < 2e-4 and abs(K.ToMM(q.y) - P_[1]) < 2e-4:
                            set_(K.VECTOR2I(mm(P_[0] + mv[0]), mm(P_[1] + mv[1])))
            changed += 1
    if changed: b.Save(pcb)
    print('NARROWED', changed); sys.stdout.flush(); os._exit(0)


# ------------------------------------------------------------------ Hauptteil
def canon(n):
    """Netzname ohne '/': sch_layout.py benennt verdrahtete Netze als lokale Labels (/NAME), polys.json kennt NAME"""
    return n[1:] if n.startswith('/') else n


def main(proj, plot=None):
    proj = os.path.abspath(proj)
    name = os.path.basename(proj)
    rk = os.path.join(proj, 'rekonstruktion')
    main_pcb = os.path.join(proj, name + '.kicad_pcb')
    backup = os.path.join(rk, name + '_zonen.kicad_pcb')
    if not os.path.exists(backup):
        shutil.copy2(main_pcb, backup); print('gesichert', backup)
    # Projektdateien sichern: pcbnew schreibt beim Speichern die .kicad_pro neu
    keepfiles = {}
    for ext in ('.kicad_pro', '.kicad_prl'):
        f = os.path.join(proj, name + ext)
        if os.path.exists(f): keepfiles[f] = open(f, 'rb').read()
    shutil.copy2(backup, main_pcb)      # Quelle ist immer die Zonen-Platine; Laden am Projektort holt die Regeln
    b = K.LoadBoard(main_pcb)
    PL = json.load(open(os.path.join(rk, 'polys.json')))
    M = json.load(open(os.path.join(rk, 'model.json')))
    H = float(M['H']) if 'H' in M and name != 'forge_es9018_pcm4202_ad_v40' else 56.39
    def toK(pts): return [(100.0 + x, 100.0 + H - y) for x, y in pts]

    nets = {}
    for code, ni in b.GetNetsByNetcode().items():
        nets[canon(ni.GetNetname())] = ni
    netid = {n: i for i, n in enumerate(sorted(nets))}   # 0 = '' (kein Netz)

    bb = b.GetBoardEdgesBoundingBox()
    X0 = K.ToMM(bb.GetX()) - 1.0; Y0 = K.ToMM(bb.GetY()) - 1.0
    W = int((K.ToMM(bb.GetWidth()) + 2) * RES) + 1; Hh = int((K.ToMM(bb.GetHeight()) + 2) * RES) + 1
    def topx(X, Y): return (Y - Y0) * RES, (X - X0) * RES          # (row, col)
    def tomm(r, c): return X0 + c / RES, Y0 + r / RES

    def raster(poly_list, holes=(), out=None, val=True, box=None):
        """Polygon (KiCad-mm) rastern; Pixelmitte (r,c) <-> (X0+c/RES, Y0+r/RES)"""
        P = np.asarray(poly_list)
        xmin, ymin = P.min(0); xmax, ymax = P.max(0)
        c0 = max(0, int(math.floor((xmin - X0) * RES))); c1 = min(W, int(math.ceil((xmax - X0) * RES)) + 1)
        r0 = max(0, int(math.floor((ymin - Y0) * RES))); r1 = min(Hh, int(math.ceil((ymax - Y0) * RES)) + 1)
        cc, rr = np.meshgrid(np.arange(c0, c1), np.arange(r0, r1))
        pts = np.column_stack([X0 + cc.ravel() / RES, Y0 + rr.ravel() / RES])
        m = Path(P).contains_points(pts)
        for hl in holes:
            m &= ~Path(np.asarray(hl)).contains_points(pts)
        m = m.reshape(rr.shape)
        out[r0:r1, c0:c1][m] = val
        return out

    def polyset(rings):
        ps = K.SHAPE_POLY_SET(); first = True
        for k, rg in enumerate(rings):
            if k == 0:
                ps.NewOutline(); hi = -1
                for x, y in rg: ps.Append(mm(x), mm(y))
            else:
                hi = ps.NewHole()
                for x, y in rg: ps.Append(mm(x), mm(y), 0, hi)
        return ps

    # Pads / Vias je Lage
    pads = []   # dict(net, pos, minsize, layers)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pads.append(dict(obj=p, net=canon(p.GetNetname()), pos=(K.ToMM(p.GetPosition().x), K.ToMM(p.GetPosition().y))))
    for t in b.Tracks():
        if t.GetClass() == 'PCB_VIA':
            pads.append(dict(obj=t, net=canon(t.GetNetname()), pos=(K.ToMM(t.GetPosition().x), K.ToMM(t.GetPosition().y)), via=True))

    new_tracks = []; new_zones = []; stats = dict(free=[], snapped=0, ext=0, narrowed=0)
    ext_keys = set()

    for lname, items in PL['copper'].items():
        L = LAY[lname]
        lab = np.zeros((Hh, W), np.int32)           # Insel-Index + 1
        for i, it in enumerate(items):
            raster(toK(it['outer']), [toK(h) for h in it['holes']], lab, i + 1)
        padlab = np.zeros((Hh, W), np.int32)        # Pad-Index + 1
        padnet = np.full((Hh, W), -1, np.int32)
        pinfo = []
        for pd in pads:
            o = pd['obj']
            if pd.get('via'):
                if not o.IsOnLayer(L): continue
                r = K.ToMM(o.GetWidth(L)) / 2; cx, cy = pd['pos']
                ring_ = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 33)[:-1]]
                minsz = 2 * r
            else:
                if not o.IsOnLayer(L): continue      # auch nicht geflashte THT-Pads: DRC prüft sie trotzdem
                ps = K.SHAPE_POLY_SET(); o.TransformShapeToPolygon(ps, L, 0, mm(0.005), K.ERROR_INSIDE)
                if ps.OutlineCount() == 0: continue
                ol = ps.Outline(0)
                ring_ = [(K.ToMM(ol.CPoint(k).x), K.ToMM(ol.CPoint(k).y)) for k in range(ol.PointCount())]
                s = o.GetSize(L); minsz = K.ToMM(min(s.x, s.y))
            pinfo.append(dict(pd, minsz=minsz, ring=ring_))
            raster(ring_, (), padlab, len(pinfo))
            raster(ring_, (), padnet, netid.get(pd['net'], 0))
        if 'inside' not in locals():
            inside = np.zeros((Hh, W), bool); raster(toK(PL['outline']), (), inside, True)
        itemnet = np.array([-1] + [netid.get(it['net'], 0) for it in items])
        copnet = itemnet[lab]                       # -1 = kein Kupfer

        for i, it in enumerate(items):
            k = i + 1; net = it['net']; nid = netid.get(net, 0); ni = nets.get(net)
            rows, cols = np.nonzero(lab == k)
            if len(rows) == 0: continue
            mg = int(2.0 * RES)
            r0 = max(0, rows.min() - mg); r1 = min(Hh, rows.max() + mg + 1)
            c0 = max(0, cols.min() - mg); c1 = min(W, cols.max() + mg + 1)
            sl = (slice(r0, r1), slice(c0, c1))
            Mk = lab[sl] == k
            own = (padnet[sl] == nid) & (padlab[sl] > 0)
            ownD = ndi.distance_transform_edt(~own) / RES
            Mp = Mk & (ownD > MARGIN)
            Zadd = np.zeros(Mk.shape, bool)       # aus der Formprüfung: Bereiche, die Fläche werden müssen
            for attempt in range(4):
                snap = (len(new_tracks), len(new_zones), stats['snapped'], stats['ext'], stats['narrowed'], len(stats['free']), stats.get('repair', 0))
                D = ndi.distance_transform_edt(Mk) / RES      # Breite mit Pads/Vias: Via-Felder sind Flächen
                core = D >= WIDE / 2
                cl, ncl = ndi.label(core)
                if ncl:                                         # Kern zählt nur außerhalb der eigenen Pads
                    areas = ndi.sum(core & (ownD > 0.3), cl, range(1, ncl + 1)) / RES ** 2
                    keep = np.zeros(ncl + 1, bool); keep[1:] = areas >= CORE_MIN
                    core = keep[cl]
                if core.any():
                    wide = (ndi.distance_transform_edt(~core) / RES <= WIDE / 2) & Mk
                    Z = (ndi.distance_transform_edt(~wide) / RES <= EXT) & Mk
                else:
                    Z = np.zeros_like(Mk)
                Z |= Zadd
                if Z.any():                                     # dickes Kupfer (>= THICK breit), das an eine Fläche grenzt, gehört dazu
                    thick = (ndi.distance_transform_edt(~(D >= THICK / 2)) / RES <= THICK / 2) & Mk
                    tl, ntl = ndi.label(thick | Z)
                    hit = np.unique(tl[Z]); hit = hit[hit > 0]
                    Z |= np.isin(tl, hit) & thick
                if Z.any() and own.any():                # eigene Pads/Vias, die in der Fläche liegen, ganz in die Fläche
                    Zin0 = ndi.distance_transform_edt(Z) / RES >= 0.12
                    ol_, nol = ndi.label(own & Mk)
                    for oi in range(1, nol + 1):
                        m_ = ol_ == oi
                        if (m_ & Zin0).sum() >= 3:
                            Z |= ndi.binary_dilation(m_, iterations=2) & (Mk | own)
                # ---- Flächen-Zonen
                if Z.any():
                    Zc = ndi.distance_transform_edt(~Z) <= 2.0
                    g = contourpy.contour_generator(z=Zc.astype(float), fill_type=contourpy.FillType.OuterOffset)
                    pts_l, offs_l = g.filled(0.5, 2.0)
                    itps = polyset([toK(it['outer'])] + [toK(h) for h in it['holes']])
                    for pts, offs in zip(pts_l, offs_l):
                        rings = []
                        for a, e in zip(offs[:-1], offs[1:]):
                            rg = pts[a:e]
                            rg = dp(np.vstack([rg, rg[:1]]), 0.02)[:-1] if len(rg) > 3 else rg
                            rings.append([tomm(r0 + y, c0 + x) for x, y in rg])
                        zp = polyset(rings)
                        zp.BooleanIntersection(itps)
                        for oi in range(zp.OutlineCount()):
                            one = zp.UnitSet(oi)
                            if K.ToMM(K.ToMM(one.Area())) < 0.2: continue
                            rings_ = []
                            for ci in range(one.OutlineCount()):
                                ol = one.COutline(ci)
                                rings_.append([(K.ToMM(ol.CPoint(j).x), K.ToMM(ol.CPoint(j).y)) for j in range(ol.PointCount())])
                            new_zones.append((L, ni, one, lname, rings_))
                # ---- Leiterbahnen
                R = Mk & ~Z          # Pads bleiben drin: Bild-Pads sind oft größer als die Footprint-Pads
                R = ndi.binary_opening(R, np.ones((3, 3)))
                rl, nr = ndi.label(R, np.ones((3, 3)))
                if nr:
                    ar = ndi.sum(R, rl, range(1, nr + 1)) / RES ** 2
                    keep = np.zeros(nr + 1, bool); keep[1:] = ar >= 0.03
                    R = keep[rl]
                if not R.any(): break
                Dfull = ndi.distance_transform_edt(Mk)
                foreign = ((copnet[sl] >= 0) & (copnet[sl] != nid)) | ((padnet[sl] >= 0) & (padnet[sl] != nid))
                Fd = ndi.distance_transform_edt(~foreign) / RES - 0.5 / RES - CLR
                Fd = np.minimum(Fd, ndi.distance_transform_edt(inside[sl]) / RES - 0.5 / RES - EDGE_CLR)   # erlaubte halbe Breite
                Fd = np.minimum(Fd, Dfull / RES + np.maximum(OUT_TOL, (Fd - Dfull / RES) / 2))   # Lücke zum fremden Kupfer gehört beiden Seiten je zur Hälfte
                # Anker: eigenes Pad/Via (nächstes Pixel), Fläche
                pl = padlab[sl] * own
                dpad, ind = ndi.distance_transform_edt(pl == 0, return_indices=True)
                dZ = ndi.distance_transform_edt(~Z) / RES if Z.any() else np.full(Mk.shape, 1e9)

                S = zhang_suen(R)
                S &= ownD > 0.05     # Skelett an den eigenen Pads/Vias abschneiden
                S = thin_corners(S)

                def anchor(p):
                    if dpad[p] / RES <= SNAP + MARGIN:
                        return ('pad', pl[ind[0][p], ind[1][p]] - 1)
                    if dZ[p] <= 0.15: return ('zone', None)
                    return None

                for _ in range(6):   # Sporne entfernen
                    paths, jl, nodepos = trace_paths(S)
                    Dg = degree(S); removed = 0
                    for pth in paths:
                        a, e = pth[0], pth[-1]
                        fa = Dg[a] == 1 and anchor(a) is None
                        fe = Dg[e] == 1 and anchor(e) is None
                        ln = len(pth) / RES
                        w = 2 * np.median([Dfull[q] for q in pth]) / RES
                        aa = anchor(a) if Dg[a] == 1 else None
                        ae = anchor(e) if Dg[e] == 1 else None
                        same_pad = aa and ae and aa[0] == 'pad' and aa == ae
                        if ((fa or fe) and ln < w + 0.3) or (same_pad and ln < 1.0) or (len(pth) < 3 and Dg[a] < 3 and Dg[e] < 3):
                            for q in pth:
                                if Dg[q] < 3: S[q] = False
                            removed += 1
                    if not removed: break
                paths, jl, nodepos = trace_paths(S)
                Dg = degree(S)

                # doppelte kurze Äste vom selben Knoten ins selbe Pad
                info = []
                for pth in paths:
                    a, e = pth[0], pth[-1]
                    an = [anchor(a) if Dg[a] == 1 else None, anchor(e) if Dg[e] == 1 else None]
                    info.append(an)
                drop = set(); best = {}
                for pi, (pth, an) in enumerate(zip(paths, info)):
                    for end, other in ((0, -1), (1, 0)):
                        if an[end] and an[end][0] == 'pad':
                            o = pth[other]
                            if Dg[o] >= 3:
                                key = (jl[o], an[end][1])
                                if key in best:
                                    pj = best[key]
                                    if len(paths[pj]) <= len(pth): drop.add(pj); best[key] = pi
                                    else: drop.add(pi)
                                else: best[key] = pi

                def seg_dmin(s, e_):
                    n_ = max(2, int(math.hypot(e_[0] - s[0], e_[1] - s[1]) * RES * 2) + 1)
                    xs = np.linspace(s[0], e_[0], n_); ys = np.linspace(s[1], e_[1], n_)
                    rr = np.clip(np.round((ys - Y0) * RES).astype(int) - r0, 0, Fd.shape[0] - 1)
                    cc = np.clip(np.round((xs - X0) * RES).astype(int) - c0, 0, Fd.shape[1] - 1)
                    return float(Fd[rr, cc].min())
                def pt_d(pnt):
                    rr = min(max(int(round((pnt[1] - Y0) * RES)) - r0, 0), Fd.shape[0] - 1)
                    cc = min(max(int(round((pnt[0] - X0) * RES)) - c0, 0), Fd.shape[1] - 1)
                    return float(Fd[rr, cc])
                node_ends = {}; node_poly = {}
                def proj(poly, q):
                    """nächster Punkt auf der Polylinie; innerhalb 0.3 mm eines Endes -> das Ende"""
                    for e_ in (poly[0], poly[-1]):
                        if math.hypot(e_[0] - q[0], e_[1] - q[1]) < 0.3: return e_
                    best = None
                    for a_, b_ in zip(poly[:-1], poly[1:]):
                        d_ = np.subtract(b_, a_); l2 = float(d_ @ d_)
                        t_ = 0.0 if l2 < 1e-12 else min(1.0, max(0.0, float(np.subtract(q, a_) @ d_) / l2))
                        c_ = (a_[0] + t_ * d_[0], a_[1] + t_ * d_[1])
                        dd = math.hypot(c_[0] - q[0], c_[1] - q[1])
                        if best is None or dd < best[0]: best = (dd, c_)
                    return best[1]

                # Union-Find über Pads/Vias, Pfade, Flächen dieser Insel
                par = {}
                def find(x):
                    par.setdefault(x, x)
                    while par[x] != x:
                        par[x] = par[par[x]]; x = par[x]
                    return x
                def union(x, y): par[find(x)] = find(y)
                seeds = {}                                  # Knoten -> Pixelmaske (Ausschnitt)
                zl, nzl = ndi.label(Z) if Z.any() else (np.zeros(Mk.shape, int), 0)
                for zi in range(1, nzl + 1):
                    seeds['z%d' % zi] = zl == zi; find('z%d' % zi)
                dind = None
                if nzl:
                    _, zind = ndi.distance_transform_edt(zl == 0, return_indices=True)
                    deep = ndi.distance_transform_edt(Z & Mk) / RES >= 0.3
                    _, dind = ndi.distance_transform_edt(~deep, return_indices=True) if deep.any() else (None, None)
                def zone_id(p):
                    return 'z%d' % zl[zind[0][p], zind[1][p]]
                Zin = ndi.distance_transform_edt(Z & Mk) / RES >= 0.12 if nzl else Z
                Zext = ndi.distance_transform_edt(Z & Mk) / RES >= 0.25 if nzl else Z   # Verlängerungen enden so tief in der Fläche
                ipads = []
                for idx, q in enumerate(pinfo):
                    if q['net'] != net or not q['net']: continue
                    rg = np.asarray(q['ring'])
                    if rg[:, 0].max() < X0 + c0 / RES or rg[:, 0].min() > X0 + c1 / RES: continue
                    if rg[:, 1].max() < Y0 + r0 / RES or rg[:, 1].min() > Y0 + r1 / RES: continue
                    pm = np.zeros(Mk.shape, bool)
                    xmin, ymin = rg.min(0); xmax, ymax = rg.max(0)
                    cA = max(c0, int(math.floor((xmin - X0) * RES))); cB = min(c1, int(math.ceil((xmax - X0) * RES)) + 1)
                    rA = max(r0, int(math.floor((ymin - Y0) * RES))); rB = min(r1, int(math.ceil((ymax - Y0) * RES)) + 1)
                    if cA >= cB or rA >= rB: continue
                    cc_, rr_ = np.meshgrid(np.arange(cA, cB), np.arange(rA, rB))
                    m_ = Path(rg).contains_points(np.column_stack([X0 + cc_.ravel() / RES, Y0 + rr_.ravel() / RES])).reshape(rr_.shape)
                    pm[rA - r0:rB - r0, cA - c0:cB - c0] = m_
                    if not (pm & Mk).any(): continue
                    ipads.append(idx); seeds['p%d' % idx] = pm; find('p%d' % idx)
                    for zi in range(1, nzl + 1):          # nur echte Überlappung mit dem Flächeninneren zählt
                        if (pm & (zl == zi) & Zin).sum() >= 3: union('p%d' % idx, 'z%d' % zi)
                for x_ in range(len(ipads)):
                    for y_ in range(x_ + 1, len(ipads)):
                        if (seeds['p%d' % ipads[x_]] & seeds['p%d' % ipads[y_]]).any(): union('p%d' % ipads[x_], 'p%d' % ipads[y_])

                def emit(xy, w, ends, node):
                    """xy: Punkte (mm); ends: je Ende None | ('pad', idx) | ('zone', zid)"""
                    xy = [tuple(map(float, v)) for v in xy]
                    for end, a_ in enumerate(ends):          # freie Enden zurücknehmen, bis die Rundung passt
                        if a_ != ('free',) or len(xy) < 2: continue
                        j0, j1 = (0, 1) if end == 0 else (-1, -2)
                        pe, pp = np.array(xy[j0]), np.array(xy[j1]); L_ = np.hypot(*(pe - pp))
                        for t_ in np.arange(0, L_ * 0.95, 0.5 / RES):
                            q_ = pe + (pp - pe) / max(L_, 1e-9) * t_
                            if pt_d(q_) >= w / 2: break
                        xy[j0] = tuple(q_)
                    ends = [None if a_ == ('free',) else a_ for a_ in ends]
                    node_ends[node] = [xy[0], xy[-1]]; node_poly[node] = list(xy)
                    segs = [(tuple(xy[j]), tuple(xy[j + 1])) for j in range(len(xy) - 1)]
                    extra = []
                    for end, a_ in enumerate(ends):
                        p_end = tuple(xy[0] if end == 0 else xy[-1])
                        p_prev = tuple(xy[1] if end == 0 else xy[-2]) if len(xy) > 1 else p_end
                        find('c%.4f,%.4f' % p_end); union(node, 'c%.4f,%.4f' % p_end)
                        if a_ is None: continue
                        if a_[0] == 'pad':
                            q = pinfo[a_[1]]; union(node, 'p%d' % a_[1])
                            extra.append((p_end, q['pos'], q['minsz'], q['ring'])); stats['snapped'] += 1
                        else:
                            union(node, a_[1])
                            d = np.subtract(p_end, p_prev); n_ = np.hypot(*d)
                            if n_ > 1e-6:
                                def inZ(q):
                                    rq = int(round((q[1] - Y0) * RES)) - r0; cq = int(round((q[0] - X0) * RES)) - c0
                                    return 0 <= rq < Z.shape[0] and 0 <= cq < Z.shape[1] and bool(Zext[rq, cq])
                                if inZ(p_end): continue                # Ende liegt schon im Flächeninneren
                                tgt = tuple(np.add(p_end, d / n_ * EXT))
                                if (not inZ(tgt) or seg_dmin(p_end, tgt) < min(w, 0.3) / 2) and dind is not None:   # lieber zum nächsten tiefen Flächenpunkt
                                    rq = min(max(int(round((p_end[1] - Y0) * RES)) - r0, 0), Mk.shape[0] - 1)
                                    cq = min(max(int(round((p_end[0] - X0) * RES)) - c0, 0), Mk.shape[1] - 1)
                                    tgt = tomm(r0 + dind[0][rq, cq], c0 + dind[1][rq, cq])
                                extra.append((p_end, tgt, 9.9)); stats['ext'] += 1
                    if segs:
                        lim = min(seg_dmin(s_, e_) for s_, e_ in segs)
                        wl = min(w, limit_round(2 * lim))
                        if wl < w: stats['narrowed'] += 1
                        w = wl
                        if w < WMIN:
                            stats['free'].append(('zu eng', lname, net, [round(float(v), 2) for v in xy[0]])); w = WMIN
                    for s_, e_ in segs:
                        if math.hypot(e_[0] - s_[0], e_[1] - s_[1]) < 1e-4: continue
                        new_tracks.append((L, ni, s_, e_, w))
                    for s_, e_, msz, *rg in extra:
                        we = min(w, limit_round(msz), limit_round(2 * seg_dmin(s_, e_)))
                        if we < WMIN and rg:             # Pad-Mitte zu nah an Rand/fremdem Kupfer: im Pad früher aufhören
                            pth_ = Path(np.asarray(rg[0]))
                            L_ = math.hypot(e_[0] - s_[0], e_[1] - s_[1])
                            for wc in [x for x in reversed(STEPS) if x <= min(w, limit_round(msz)) + 1e-9]:
                                best_ = None
                                for t_ in np.arange(0, L_ + 1e-9, 0.5 / RES):
                                    q_ = (s_[0] + (e_[0] - s_[0]) * t_ / max(L_, 1e-9), s_[1] + (e_[1] - s_[1]) * t_ / max(L_, 1e-9))
                                    if pt_d(q_) < wc / 2: break
                                    if pth_.contains_point(q_): best_ = q_
                                if best_ is not None:
                                    we, e_ = wc, best_; break
                        we = max(we, WMIN)
                        if math.hypot(e_[0] - s_[0], e_[1] - s_[1]) < 1e-4: continue
                        new_tracks.append((L, ni, s_, e_, we))
                        if msz == 9.9: ext_keys.add((s_, e_))

                for pi, pth in enumerate(paths):
                    if pi in drop or len(pth) < 2: continue
                    an = [(('free',) if Dg[pth[0] if j_ == 0 else pth[-1]] == 1 else None) if x_ is None else x_ if x_[0] == 'pad' else ('zone', zone_id(pth[0] if j_ == 0 else pth[-1])) for j_, x_ in enumerate(info[pi])]
                    def pos(p):
                        if Dg[p] >= 3 and jl[p]:
                            r, c = nodepos[jl[p] - 1]; return tomm(r0 + r, c0 + c)
                        return tomm(r0 + p[0], c0 + p[1])
                    xy = [tomm(r0 + p[0], c0 + p[1]) for p in pth]
                    xy[0] = pos(pth[0]); xy[-1] = pos(pth[-1])
                    xy = dp(xy, DP_EPS)
                    w = eagle_round(2 * np.median([Dfull[q] for q in pth]) / RES - 1 / RES)
                    node = 't%d' % pi
                    m_ = np.zeros(Mk.shape, bool)
                    for q in pth: m_[q] = True
                    seeds[node] = m_
                    emit(xy, w, an, node)
                    for end, x_ in enumerate(an):
                        if x_ == ('free',):
                            f = node_ends[node][0 if end == 0 else 1]
                            stats['free'].append(('offen', lname, net, [round(float(f[0]), 2), round(float(f[1]), 2)]))

                # ---- Reparatur: getrennte Teile derselben Insel über das Originalkupfer verbinden
                objs = [k_ for k_ in seeds]
                def comps():
                    cs = {}
                    for k_ in objs: cs.setdefault(find(k_), []).append(k_)
                    return list(cs.values())
                cs = comps(); G = None; tries = 0
                while len(cs) > 1 and tries < 50:
                    tries += 1
                    if G is None:
                        dom = Mk.copy()
                        for k_ in objs: dom |= seeds[k_]
                        idxmap = -np.ones(Mk.shape, np.int64); nz_ = np.argwhere(dom)
                        idxmap[dom] = np.arange(len(nz_))
                        cost = 1.0 / np.clip(np.minimum(Dfull, (Fd + CLR) * RES), 0.5, 8)   # Mitte bevorzugen, weg von fremdem Kupfer
                        from scipy.sparse import coo_matrix
                        from scipy.sparse.csgraph import dijkstra
                        I_, J_, V_ = [], [], []
                        hh, ww = Mk.shape
                        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                            A_ = dom[max(0, -dr):hh - max(0, dr), max(0, -dc):ww - max(0, dc)]
                            B_ = dom[max(0, dr):hh - max(0, -dr) if dr < 0 else hh, max(0, dc):ww + min(0, dc) if dc < 0 else ww][:A_.shape[0], :A_.shape[1]]
                            rs, cs_ = np.nonzero(A_ & B_)
                            ra, ca = rs + max(0, -dr), cs_ + max(0, -dc)
                            rb, cb = ra + dr, ca + dc
                            wgt = math.hypot(dr, dc) * (cost[ra, ca] + cost[rb, cb]) / 2
                            I_.append(idxmap[ra, ca]); J_.append(idxmap[rb, cb]); V_.append(wgt)
                        I_ = np.concatenate(I_); J_ = np.concatenate(J_); V_ = np.concatenate(V_)
                        G = coo_matrix((np.r_[V_, V_], (np.r_[I_, J_], np.r_[J_, I_])), shape=(len(nz_), len(nz_))).tocsr()
                    cs.sort(key=lambda c_: sum(int(seeds[k_].sum()) for k_ in c_))
                    A = cs[0]
                    sa = np.zeros(Mk.shape, bool)
                    for k_ in A: sa |= seeds[k_]
                    tg = np.zeros(Mk.shape, bool)
                    for c_ in cs[1:]:
                        for k_ in c_: tg |= seeds[k_]
                    src = idxmap[sa]; src = src[src >= 0]
                    dist, pred, srcs = dijkstra(G, indices=src, min_only=True, return_predecessors=True)
                    tix = idxmap[tg & ~sa]; tix = tix[tix >= 0]
                    if not len(tix) or not np.isfinite(dist[tix]).any():
                        stats['free'].append(('nicht verbindbar', lname, net, [round(float(v), 2) for v in tomm(r0 + nz_[src[0]][0], c0 + nz_[src[0]][1])]))
                        for c_ in cs[1:]: union(A[0], c_[0])     # aufgeben
                        cs = comps(); continue
                    t_ = tix[np.argmin(dist[tix])]
                    chain = [t_]
                    while pred[chain[-1]] >= 0: chain.append(pred[chain[-1]])
                    chain = chain[::-1]
                    pix = [tuple(nz_[c_]) for c_ in chain]
                    def owner(p, cand):
                        for pref in ('p', 't', 'r', 'z'):
                            for k_ in cand:
                                if k_[0] == pref and seeds[k_][p]: return k_
                        return None
                    oa = owner(pix[0], A)
                    ob = owner(pix[-1], [k_ for c_ in cs[1:] for k_ in c_])
                    xy = [tuple(v) for v in dp([tomm(r0 + p[0], c0 + p[1]) for p in pix], DP_EPS)]
                    if len(xy) < 2: xy = xy + xy
                    for j0, o_ in ((0, oa), (-1, ob)):       # an Spur: genau auf deren Mittellinie (bzw. nahes Ende) ziehen
                        if o_ and o_[0] in 'tr' and o_ in node_poly:
                            e_ = proj(node_poly[o_], xy[j0])
                            if j0 == 0: xy = [e_] + xy
                            else: xy = xy + [e_]
                    ends = []
                    for o_ in (oa, ob):
                        if o_ is None or o_[0] in 'tr': ends.append(None)
                        elif o_[0] == 'p': ends.append(('pad', int(o_[1:])))
                        else: ends.append(('zone', o_))
                    w = eagle_round(2 * np.median([Dfull[p] for p in pix]) / RES - 1 / RES)
                    node = 'r%d' % tries
                    emit(xy, w, ends, node)
                    seeds[node] = np.zeros(Mk.shape, bool)
                    for p in pix: seeds[node][p] = True
                    objs.append(node)
                    if oa: union(node, oa)
                    if ob: union(node, ob)
                    stats['repair'] = stats.get('repair', 0) + 1
                    cs = comps()
                # ---- Spuren, die ganz in einer Fläche liegen, sind überflüssig
                if Z.any():
                    olz, nolz = ndi.label(own & Mk)               # nur eigene Pads, die selbst in der Fläche liegen
                    hz = np.unique(olz[Z & (ndi.distance_transform_edt(Z & Mk) / RES >= 0.12)]); hz = hz[hz > 0]
                    Zd = ndi.distance_transform_edt((Z & Mk) | np.isin(olz, hz)) / RES
                    keep_ = []
                    for tr in new_tracks[snap[0]:]:
                        if (tr[2], tr[3]) in ext_keys: keep_.append(tr); continue   # Verbindung in die Fläche bleibt
                        s_, e_ = tr[2], tr[3]
                        n_ = max(2, int(math.hypot(e_[0] - s_[0], e_[1] - s_[1]) * RES) + 1)
                        rr = np.round((np.linspace(s_[1], e_[1], n_) - Y0) * RES).astype(int) - r0
                        cc = np.round((np.linspace(s_[0], e_[0], n_) - X0) * RES).astype(int) - c0
                        ok = (rr >= 0) & (rr < Z.shape[0]) & (cc >= 0) & (cc < Z.shape[1])
                        if ok.all() and Zd[rr, cc].min() > 0: stats['inzone'] = stats.get('inzone', 0) + 1; continue
                        keep_.append(tr)
                    new_tracks[snap[0]:] = keep_
                # ---- Formprüfung: dicke Kupferbereiche, die die Spuren nicht nachbilden -> Fläche, Insel neu
                if attempt == 3: break
                T = np.zeros(Mk.shape, bool)
                for _L, _n, s_, e_, w_ in new_tracks[snap[0]:]:
                    xa, ya = min(s_[0], e_[0]) - w_, min(s_[1], e_[1]) - w_
                    xb, yb = max(s_[0], e_[0]) + w_, max(s_[1], e_[1]) + w_
                    ca = max(0, int((xa - X0) * RES) - c0); cb = min(Mk.shape[1], int((xb - X0) * RES) + 2 - c0)
                    ra = max(0, int((ya - Y0) * RES) - r0); rb = min(Mk.shape[0], int((yb - Y0) * RES) + 2 - r0)
                    if ca >= cb or ra >= rb: continue
                    cc_, rr_ = np.meshgrid(np.arange(ca, cb), np.arange(ra, rb))
                    px = X0 + (cc_ + c0) / RES; py = Y0 + (rr_ + r0) / RES
                    d_ = np.subtract(e_, s_); l2 = float(d_ @ d_)
                    t_ = np.clip(((px - s_[0]) * d_[0] + (py - s_[1]) * d_[1]) / max(l2, 1e-12), 0, 1)
                    T[ra:rb, ca:cb] |= np.hypot(px - s_[0] - t_ * d_[0], py - s_[1] - t_ * d_[1]) <= w_ / 2
                cov = T | Z | own
                miss = Mk & (ndi.distance_transform_edt(~cov) / RES > MISS_TOL)
                fat = ndi.distance_transform_edt(miss) / RES >= MISS_FAT
                ml, nm = ndi.label(miss)
                bad = np.zeros(Mk.shape, bool)
                if nm:
                    ar = ndi.sum(miss, ml, range(1, nm + 1)) / RES ** 2
                    hf = ndi.maximum(fat, ml, range(1, nm + 1))
                    keep = np.zeros(nm + 1, bool); keep[1:] = (ar >= MISS_AREA) & (np.asarray(hf) > 0)
                    bad = keep[ml]
                if not bad.any(): break
                Zadd |= Mk & (ndi.distance_transform_edt(~bad) / RES <= MISS_GROW)
                del new_tracks[snap[0]:]; del new_zones[snap[1]:]; del stats['free'][snap[5]:]
                stats['snapped'], stats['ext'], stats['narrowed'] = snap[2:5]; stats['repair'] = snap[6]
                stats['formfix'] = stats.get('formfix', 0) + 1

    # ---- Platine umbauen
    for z in list(b.Zones()):
        if z.GetZoneName().startswith('orig_'): b.Remove(z)
    for fp in b.GetFootprints():                # Montagelöcher: Flächen erreichen sie oft nur von einer Seite -> voll anbinden statt Thermal
        if fp.GetReference().startswith('H') and fp.GetReference()[1:].isdigit():
            for p_ in fp.Pads(): p_.SetLocalZoneConnection(K.ZONE_CONNECTION_FULL)
    uniq = {}
    for L, ni, s, e, w in new_tracks:           # doppelte Segmente zusammenfassen (breiteste bleibt)
        key = (L, ni.GetNetname() if ni else '') + tuple(sorted([(round(s[0], 4), round(s[1], 4)), (round(e[0], 4), round(e[1], 4))]))
        if key not in uniq or uniq[key][4] < w: uniq[key] = (L, ni, s, e, w)
    new_tracks = list(uniq.values())
    for L, ni, s, e, w in new_tracks:
        t = K.PCB_TRACK(b); t.SetLayer(L)
        t.SetStart(K.VECTOR2I(mm(round(s[0], 4)), mm(round(s[1], 4))))
        t.SetEnd(K.VECTOR2I(mm(round(e[0], 4)), mm(round(e[1], 4))))
        t.SetWidth(mm(w))
        if ni: t.SetNet(ni)
        b.Add(t)
    for L, ni, ps, lname, _ in new_zones:
        z = K.ZONE(b); z.SetLayer(L)
        if ni: z.SetNet(ni)
        z.SetOutline(ps)
        z.SetZoneName('flaeche_%s' % lname.split('.')[0])
        z.SetLocalClearance(mm(0.08)); z.SetMinThickness(mm(0.1))
        z.SetPadConnection(K.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(mm(0.2)); z.SetThermalReliefSpokeWidth(mm(0.3))
        z.SetIslandRemovalMode(K.ISLAND_REMOVAL_MODE_NEVER)
        z.SetAssignedPriority(1)
        b.Add(z)
    b.Save(main_pcb)
    for f, data in keepfiles.items():
        open(f, 'wb').write(data)
    nfix, unres = drc_narrow(main_pcb, keepfiles)
    stats['drcfix'] = nfix
    nt = len(new_tracks); nz = len(new_zones)
    ws = {}
    for *_, w in new_tracks: ws[round(w, 4)] = ws.get(round(w, 4), 0) + 1
    print('%s: Tracks %d, Flächen-Zonen %d, Pad/Via-Einrastungen %d, Flächen-Verlängerungen %d, durch Clearance verschmälert %d'
          % (name, nt, nz, stats['snapped'], stats['ext'], stats['narrowed']))
    print('Reparatur-Verbindungen:', stats.get('repair', 0), ' nach DRC verschmälert:', nfix, ' Formprüfung -> Fläche:', stats.get('formfix', 0), ' in Fläche entfallen:', stats.get('inzone', 0))
    for u in unres: print('   DRC nicht behebbar:', u)
    print('Breiten:', dict(sorted(ws.items())))
    for f in stats['free']: print('  ', *f)
    if plot:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MPoly
        layers = list(PL['copper'])
        fig, axs = plt.subplots(1, len(layers), figsize=(9 * len(layers), 8))
        axs = np.atleast_1d(axs)
        for ax, ln in zip(axs, layers):
            for it in PL['copper'][ln]:
                ax.add_patch(MPoly(toK(it['outer']), closed=True, fc='#ddd', ec='#bbb', lw=0.3))
            for L, ni, ps, l2, rings_ in new_zones:
                if l2 != ln: continue
                ax.add_patch(MPoly(rings_[0], closed=True, fc='#9cf', ec='b', lw=0.4, alpha=0.6))
            for L, ni, s, e, w in new_tracks:
                if L != LAY[ln]: continue
                ax.plot([s[0], e[0]], [s[1], e[1]], '-', color='r', lw=w * 72 / 25.4 * 8 / 1.0 * 0.5, solid_capstyle='round', alpha=0.7)
            for f in stats['free']:
                if f[1] == ln: ax.plot(*f[3], 'kx', ms=8)
            ax.set_aspect('equal'); ax.invert_yaxis(); ax.autoscale(); ax.set_title(ln)
        fig.savefig(plot, dpi=110, bbox_inches='tight')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--narrow':
        narrow(a[1], a[2])
    plot = None
    if '--plot' in a:
        i = a.index('--plot'); plot = a[i + 1]; del a[i:i + 2]
    main(a[0], plot)
    sys.stdout.flush(); os._exit(0)   # pcbnew-Destruktoren stürzen beim Beenden sonst gelegentlich ab
