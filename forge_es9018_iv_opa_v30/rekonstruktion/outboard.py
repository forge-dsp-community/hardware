"""Rekonstruktion der Forge I/V-Ausgangsplatinen (ES9018_IV_OPA V30, ES90x8_IV_OPA V40d/V40e)
Quelle: nur Eagle-Renderings (300 dpi). Ergebnis: <OUT>/model.json + polys.json im Format der Trägerplatinen-Pipeline.
Aufruf: outboard.py <variantendir> <prefix> <outdir>"""
import sys, os, json, math
import numpy as np
import matplotlib.image as mi
from scipy import ndimage as nd
import contourpy

VD, PFX, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
PPM = 11.811
def rgb(n): return (mi.imread(os.path.join(VD, '%s-%s.png' % (PFX, n)))[..., :3] * 255).round().astype(np.int16)
def has(n): return os.path.exists(os.path.join(VD, '%s-%s.png' % (PFX, n)))
def feat(n):
    a = rgb(n); return (a != 255).any(-1) & ~((a[..., 0] == a[..., 1]) & (a[..., 1] == a[..., 2]))

top = rgb('TOP'); o = (top == 75).all(-1); ys, xs = np.nonzero(o)
X0, Y0 = xs.min() + 0.5, ys.max() - 0.5          # Ursprung: links unten (Umriss)
H = (ys.max() - ys.min()) / PPM
def mm(x, y): return ((x - X0) / PPM, (Y0 - y) / PPM)
def px(x, y): return int(round(X0 + x * PPM)), int(round(Y0 - y * PPM))

LAYN = [('F', 'TOP')] + ([('In1', 'ROUTE2'), ('In2', 'ROUTE3')] if has('ROUTE2') else []) + [('B', 'BOTTOM')]
LAY = {k: feat(n) for k, n in LAYN}
holes = feat('VIAS') | (feat('PADS') if has('PADS') else False)
holes = nd.binary_fill_holes(holes)
hl, hn = nd.label(holes)
labs = {k: nd.label(v) for k, v in LAY.items()}
par = {}
def f(a):
    par.setdefault(a, a)
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
def u(a, b): par[f(a)] = f(b)
for k, (l, n) in labs.items():
    for i in range(1, n + 1): f((k, i))
CENT = nd.center_of_mass(holes, hl, range(1, hn + 1))
for i, (cy, cx) in enumerate(CENT, 1):
    f(('H', i)); Y, X = int(round(cy)), int(round(cx))
    for k, (l, n) in labs.items():
        v = l[Y - 1:Y + 2, X - 1:X + 2]; v = v[v > 0]
        if len(v): u(('H', i), (k, int(np.bincount(v).argmax())))

def net_at(side, x, y, th=False):
    X, Y = px(x, y)
    if th and hl[Y, X]: return repr(f(('H', int(hl[Y, X]))))
    l = labs[side][0]
    for r in range(0, 3):
        v = l[Y - r:Y + r + 1, X - r:X + r + 1]; v = v[v > 0]
        if len(v): return repr(f((side, int(np.bincount(v).argmax()))))
    return 'None'

# ------------------------------------------------------------ Hauptkörper / Steckzunge
rowsw = o.sum(1)
body_bottom_px = None
cols = [np.nonzero(o[y])[0] for y in range(o.shape[0])]
# Steckzunge: Zeilen, in denen der Umriss schmaler ist als oben
w_full = xs.max() - xs.min()
widths = np.array([(c.max() - c.min()) if len(c) > 1 else 0 for c in cols])
tab_rows = [y for y in range(o.shape[0]) if 0 < widths[y] < 0.85 * w_full]
TAB_Y = mm(0, min(tab_rows))[1] if tab_rows else 0.0   # Oberkante Zunge (mm)
print('Platine %.2f x %.2f mm, Zunge bis y=%.2f' % (w_full / PPM, H, TAB_Y))

# ------------------------------------------------------------ SMD-Pads (Oberseite) aus Gesamtbild
comp_img = (mi.imread(os.path.join(VD, PFX + '.png'))[..., :3] * 255).round().astype(int)
mx, mn = comp_img.max(-1), comp_img.min(-1)
padm = (mn > 80) & (mx < 150) & (mx - mn < 50)
cross = mx < 45
padm |= nd.binary_closing(padm, iterations=2) & nd.binary_dilation(cross, iterations=1)
padm = nd.binary_opening(padm, structure=np.ones((3, 3)))
padm &= LAY['F']                                  # nur echtes Kupfer
padm[px(0, TAB_Y)[1] - 2:, :] = False             # Zunge separat
thm = feat('PADS') if has('PADS') else np.zeros_like(padm)
lab, n = nd.label(padm)
SMD = []
for i, sl in enumerate(nd.find_objects(lab), 1):
    r = lab[sl] == i
    if r.sum() < 14: continue
    yy, xx = np.nonzero(r)
    if thm[sl][r].any(): continue
    x0, x1 = xx.min() + sl[1].start, xx.max() + sl[1].start + 1
    y0, y1 = yy.min() + sl[0].start, yy.max() + sl[0].start + 1
    cx, cy = mm((x0 + x1) / 2, (y0 + y1) / 2)
    SMD.append(dict(x=round(cx, 3), y=round(cy, 3), w=round((x1 - x0) / PPM, 2), h=round((y1 - y0) / PPM, 2)))
print('SMD-Pads', len(SMD))

# ------------------------------------------------------------ Bohrungen
def holes_of(mask):
    lab, n = nd.label(mask); out = []
    for i, sl in enumerate(nd.find_objects(lab), 1):
        r = lab[sl] == i; fr = nd.binary_fill_holes(r); yy, xx = np.nonzero(r)
        cx, cy = mm(xx.mean() + sl[1].start, yy.mean() + sl[0].start)
        w = (xx.max() - xx.min() + 1) / PPM; h = (yy.max() - yy.min() + 1) / PPM
        inner = 2 * math.sqrt((fr & ~r).sum() / math.pi) / PPM
        sq = fr.sum() / ((xx.max() - xx.min() + 1) * (yy.max() - yy.min() + 1)) > 0.9
        out.append(dict(x=cx, y=cy, w=w, h=h, inner=inner, square=bool(sq)))
    return out
VIAS = holes_of(feat('VIAS')); THP = holes_of(thm) if has('PADS') else []

COMPS = []
def pad(num, x, y, w, h, side, shape='rect', drill=0.0, th=False):
    return dict(num=str(num), x=round(x, 4), y=round(y, 4), w=round(w, 3), h=round(h, 3), side=side, shape=shape, drill=drill, th=th)
def comp(ref, kind, side, pads, **kw):
    d = dict(ref=ref, kind=kind, side=side, pads=pads); d.update(kw)
    d.setdefault('cx', sum(p['x'] for p in pads) / len(pads)); d.setdefault('cy', sum(p['y'] for p in pads) / len(pads))
    COMPS.append(d); return d

# ------------------------------------------------------------ Steckzunge
tabpads = []
for side in ('F', 'B'):
    m = LAY[side].copy(); m[:px(0, TAB_Y)[1] + 1, :] = False
    l, nn_ = nd.label(m)
    strip = np.zeros_like(m); strip[px(0, 1.6)[1]:, :] = True          # untere 1.6 mm = Kontaktfinger
    for i, sl in enumerate(nd.find_objects(l), 1):
        r = l[sl] == i
        rs = r & strip[sl]
        if rs.sum() < 10: continue
        yy, xx = np.nonzero(r); ys_, xs_ = np.nonzero(rs)
        x0, x1 = xs_.min() + sl[1].start, xs_.max() + sl[1].start + 1
        y0 = yy.min() + sl[0].start; y1 = yy.max() + sl[0].start + 1
        cx, _ = mm((x0 + x1) / 2, 0); w = (x1 - x0) / PPM
        top_mm = mm(0, y0)[1]; bot_mm = mm(0, y1)[1]
        hgt = min(top_mm, TAB_Y) - bot_mm
        tabpads.append(dict(side=side, x=cx, w=w, ytop=min(top_mm, TAB_Y), h=hgt, cxpx=(x0 + x1) / 2))
# TH-Pads in der Zunge
tab_th = [h for h in THP if h['y'] < TAB_Y + 0.3]
print('Zungen-Kupfer', len(tabpads), 'TH in Zunge', len(tab_th))

# Zungenkontakte gruppieren: Oberseiten-Finger führen, Unterseite nur wenn deckungsgleich
tabpads = [t for t in tabpads if t['h'] >= 1.2 and t['w'] <= 2.2]          # Flächenreste ausschließen
for t in tabpads:
    yb = t['ytop'] - t['h']                                                 # Unterkante des Fingers
    t['ymid'] = yb + min(t['h'], 3.0) / 2
    t['root'] = net_at(t['side'], t['x'], t['ymid'])
Ff = sorted([t for t in tabpads if t['side'] == 'F' and t['w'] >= 0.7], key=lambda t: t['x'])
groups = [[t] for t in Ff]
for t in sorted([t for t in tabpads if t['side'] == 'B'], key=lambda t: t['x']):
    g = next((g for g in groups if abs(g[0]['x'] - t['x']) < 0.5), None)
    if g is not None:
        if t['root'] == g[0]['root'] and t['w'] >= 0.7: g.append(t)
    elif t['w'] >= 0.9: groups.append([t])
for h in tab_th:
    g = next((g for g in groups if abs(g[0]['x'] - h['x']) < 0.8), None)
    (g.append(dict(th=h)) if g is not None else groups.append([dict(th=h)]))
groups.sort(key=lambda g: g[0]['x'] if 'x' in g[0] else g[0]['th']['x'])
TABN = ['O.2+', 'O.2-', 'O.1+', 'O.1-', 'P-12', 'GND', 'P+12', 'I.1-', 'I.1-VREF', 'I.1+', 'I.2-', 'I.2-VREF', 'I.2+']
print('Zungen-Kontakte', len(groups), [round(g[0].get('x', 0), 2) for g in groups])
tpads = []
for gi, g in enumerate(groups, 1):
    for t in g:
        if 'th' in t:
            h = t['th']; tpads.append(pad(gi, h['x'], h['y'], max(h['w'], 1.3), max(h['h'], 1.3), 'FB', 'circle', 0.7, True))
        else:
            hh = min(t['h'], 3.0); tpads.append(pad(gi, t['x'], t['ymid'], t['w'], hh, t['side']))
VPOS = groups[6][0].get('root') if len(groups) >= 7 else None
VNEG = groups[4][0].get('root') if len(groups) >= 5 else None

# ------------------------------------------------------------ SOIC erkennen (Pinreihen 1.27 mm)
used = set()
pinlike = [i for i, p in enumerate(SMD) if 1.0 < p['h'] < 2.6 and p['w'] < 0.7]
rows = []
for i in sorted(pinlike, key=lambda i: (round(SMD[i]['y'], 1), SMD[i]['x'])):
    p = SMD[i]
    for r in rows:
        q = SMD[r[-1]]
        if abs(q['y'] - p['y']) < 0.2 and abs(abs(q['x'] - p['x']) - 1.27) < 0.2: r.append(i); break
    else: rows.append([i])
rows = [r for r in rows if len(r) >= 3]
socs = []
for a in rows:
    for b in rows:
        pa, pb = SMD[a[0]], SMD[b[0]]
        if a is b or not (3.5 < pa['y'] - pb['y'] < 6.5): continue
        xa = [SMD[i]['x'] for i in a]; xb = [SMD[i]['x'] for i in b]
        if abs(min(xa) - min(xb)) < 0.3 or abs(max(xa) - max(xb)) < 0.3: socs.append((a, b))
for k, (a, b) in enumerate(socs):
    used |= set(a) | set(b)
    xs_ = sorted(set([round(SMD[i]['x'], 2) for i in a + b]))
    x0_, x1_ = min(xs_), max(xs_)
    per = int(round((x1_ - x0_) / 1.27)) + 1
    per = 4 if per <= 4 else 7
    x0_ = round((x0_ + x1_) / 2, 3) - (per - 1) * 1.27 / 2
    ym_ = (sum(SMD[i]['y'] for i in a) / len(a) + sum(SMD[i]['y'] for i in b) / len(b)) / 2
    ym_ = round(ym_, 3); yt = ym_ + 2.6; yb = ym_ - 2.6          # SO-Raster: Padmitten ±2.6 mm
    npins = per * 2
    def numbering(rot180):
        pads = []
        for j in range(per):
            if not rot180:
                pads.append((j + 1, x0_ + j * 1.27, yb)); pads.append((npins - j, x0_ + j * 1.27, yt))
            else:
                pads.append((j + 1, x0_ + (per - 1 - j) * 1.27, yt)); pads.append((npins - j, x0_ + (per - 1 - j) * 1.27, yb))
        return sorted(pads)
    best = None
    for rot in (False, True):
        pads = numbering(rot)
        nets = {nmb: net_at('F', x, y) for nmb, x, y in pads}
        vpin, npin = (8, 4) if npins == 8 else (4, 11)
        score = (nets[vpin] == VPOS) * 10 + (nets[npin] == VNEG) * 10
        if best is None or score > best[0]: best = (score, pads)
    kind = 'SOIC8' if npins == 8 else 'SOIC14'
    comp('U%d' % (k + 1), kind, 'F', [pad(nmb, x, y, 0.6, 1.6, 'F') for nmb, x, y in best[1]], cx=round(x0_ + (per - 1) * 0.635, 3), cy=round(ym_, 3))
# senkrechte SOIC (Pinreihen links/rechts)
pinv = [i for i, p in enumerate(SMD) if i not in used and 0.7 < p['w'] < 2.6 and p['h'] < 0.6]
cols_ = []
xcl = []
for i in sorted(pinv, key=lambda i: SMD[i]['x']):
    if xcl and abs(SMD[xcl[-1][-1]]['x'] - SMD[i]['x']) < 0.4: xcl[-1].append(i)
    else: xcl.append([i])
for g in xcl:
    g.sort(key=lambda i: SMD[i]['y'])
    cur = [g[0]]
    for i in g[1:]:
        if abs(SMD[i]['y'] - SMD[cur[-1]]['y'] - 1.27) < 0.2: cur.append(i)
        elif abs(SMD[i]['y'] - SMD[cur[-1]]['y']) < 0.2: pass
        else: cols_.append(cur); cur = [i]
    cols_.append(cur)
cols_ = [r for r in cols_ if len(r) >= 3]
vs = []
for a in cols_:
    for b in cols_:
        pa, pb = SMD[a[0]], SMD[b[0]]
        if a is b or not (3.5 < pb['x'] - pa['x'] < 6.5): continue      # a links, b rechts
        ya = [SMD[i]['y'] for i in a]; yb = [SMD[i]['y'] for i in b]
        if abs(min(ya) - min(yb)) < 0.3 or abs(max(ya) - max(yb)) < 0.3: vs.append((a, b))
print('COLS', [[(round(SMD[i]['x'],2), round(SMD[i]['y'],2)) for i in r] for r in cols_])
print('VS', [(round(SMD[a[0]]['x'],1), round(SMD[a[0]]['y'],1), round(SMD[b[0]]['x'],1), round(SMD[b[0]]['y'],1)) for a, b in vs])
nso = len([c for c in COMPS if c['kind'].startswith('SOIC')])
for k, (a, b) in enumerate(vs):
    used |= set(a) | set(b)
    ys_ = [SMD[i]['y'] for i in a + b]; y0_, y1_ = min(ys_), max(ys_)
    per = int(round((y1_ - y0_) / 1.27)) + 1; per = 4 if per <= 4 else 7
    y0_ = round((y0_ + y1_) / 2, 3) - (per - 1) * 1.27 / 2
    xm_ = (sum(SMD[i]['x'] for i in a) / len(a) + sum(SMD[i]['x'] for i in b) / len(b)) / 2
    xm_ = round(xm_, 3); xl = xm_ - 2.6; xr = xm_ + 2.6
    npins = per * 2
    cands = []
    A_ = [(j + 1, xr, y0_ + j * 1.27) for j in range(per)] + [(per + j + 1, xl, y0_ + (per - 1 - j) * 1.27) for j in range(per)]
    B_ = [(j + 1, xl, y0_ + (per - 1 - j) * 1.27) for j in range(per)] + [(per + j + 1, xr, y0_ + j * 1.27) for j in range(per)]
    best = None
    for pads_ in (A_, B_):
        nets = {nmb: net_at('F', x, y) for nmb, x, y in pads_}
        vpin, npin = (8, 4) if npins == 8 else (4, 11)
        score = (nets[vpin] == VPOS) * 10 + (nets[npin] == VNEG) * 10
        if best is None or score > best[0]: best = (score, pads_)
    comp('U%d' % (nso + k + 1), 'SOIC8' if npins == 8 else 'SOIC14', 'F', [pad(nmb, x, y, 1.6, 0.6, 'F') for nmb, x, y in best[1]], rotv=True, cx=round(xm_, 3), cy=round(y0_ + (per - 1) * 0.635, 3))
print('SOIC', [(c['ref'], c['kind'], round(c['cx'], 1), round(c['cy'], 1)) for c in COMPS])

# ------------------------------------------------------------ 2-polige Bauteile
free = [i for i in range(len(SMD)) if i not in used]
def same(a, b): return abs(a['w'] - b['w']) < 0.25 and abs(a['h'] - b['h']) < 0.25
def near(i, pool):
    a = SMD[i]; best = None
    for j in pool:
        if j == i: continue
        b = SMD[j]
        if not same(a, b): continue
        if not (abs(a['x'] - b['x']) < 0.12 or abs(a['y'] - b['y']) < 0.12): continue
        d = math.hypot(a['x'] - b['x'], a['y'] - b['y'])
        if best is None or d < best[0]: best = (d, j)
    return best
pool = set(free); pairs = []
for i in sorted(free):
    if i not in pool: continue
    b = near(i, pool)
    if not b or b[0] > 4.5: continue
    bb = near(b[1], pool)
    if bb and bb[1] == i: pairs.append((i, b[1])); pool -= {i, b[1]}
# Rest: gleich große, fluchtende Einzelpads paarweise (nächster Partner)
for i in sorted(pool):
    if i not in pool: continue
    cand = [(math.hypot(SMD[i]['x'] - SMD[j]['x'], SMD[i]['y'] - SMD[j]['y']), j) for j in pool if j != i and same(SMD[i], SMD[j])
            and (abs(SMD[i]['x'] - SMD[j]['x']) < 0.12 or abs(SMD[i]['y'] - SMD[j]['y']) < 0.12)]
    cand = [c for c in cand if c[0] < 4.5]
    if cand:
        d, j = min(cand); pairs.append((i, j)); pool -= {i, j}
# Paare zwischen +12V und -12V sind falsch gebildet (zwei Abblock-C übereinander): mit freien Einzelpads neu paaren
fixed = []
for i, j in pairs:
    ri, rj = net_at('F', SMD[i]['x'], SMD[i]['y']), net_at('F', SMD[j]['x'], SMD[j]['y'])
    if {ri, rj} == {VPOS, VNEG}:
        for a in (i, j):
            cand = [k for k in pool if (abs(SMD[k]['x'] - SMD[a]['x']) < 0.15 or abs(SMD[k]['y'] - SMD[a]['y']) < 0.15)
                    and math.hypot(SMD[k]['x'] - SMD[a]['x'], SMD[k]['y'] - SMD[a]['y']) < 4.5]
            if cand:
                k = min(cand, key=lambda k: math.hypot(SMD[k]['x'] - SMD[a]['x'], SMD[k]['y'] - SMD[a]['y']))
                fixed.append((a, k)); pool.discard(k)
            else: pool.add(a)
    else: fixed.append((i, j))
pairs = fixed
for k, (i, j) in enumerate(pairs):
    a, b = SMD[i], SMD[j]
    d = math.hypot(a['x'] - b['x'], a['y'] - b['y'])
    big = max(a['w'], a['h'])
    kind = '0603' if big < 1.25 else ('0805' if big < 1.6 else ('1206' if big < 2.0 else '1210'))
    comp('P%d' % (k + 1), kind, 'F', [pad(1, a['x'], a['y'], a['w'] - 0.05, a['h'] - 0.05, 'F'), pad(2, b['x'], b['y'], b['w'] - 0.05, b['h'] - 0.05, 'F')])
rest = [SMD[i] for i in pool]
rest = [p for p in rest if max(p['w'], p['h']) >= 0.6]
for k, p in enumerate(rest):
    comp('TP%d' % (k + 1), 'PADGRP', 'F', [pad(1, p['x'], p['y'], p['w'], p['h'], 'F')])

# Elkos (TH, nur V30)
body_th = [h for h in THP if h['y'] >= TAB_Y + 0.3]
body_th.sort(key=lambda h: (-round(h['y']), h['x']))
ek = []
for h in body_th:
    for g in ek:
        if abs(g[0]['y'] - h['y']) < 0.3 and abs(g[0]['x'] - h['x']) < 5: g.append(h); break
    else: ek.append([h])
for k, g in enumerate(ek):
    g.sort(key=lambda h: h['x'])     # Pin 1 (+) = linkes Pad, laut '+' im Original-Bestückungsdruck
    comp('CE%d' % (k + 1), 'CP_TH', 'F', [pad(i + 1, h['x'], h['y'], 1.45, 1.45, 'FB', 'rect' if h['square'] else 'circle', 0.8, True) for i, h in enumerate(g)])

X1 = comp('X1', 'TAB', 'F', tpads)

# ------------------------------------------------------------ Netze
for c in COMPS:
    for p in c['pads']:
        side = 'F' if p['side'] in ('F', 'FB') else 'B'
        p['root'] = net_at(side, p['x'], p['y'], p['th'])
        if p['root'] == 'None' and p['side'] == 'FB': p['root'] = net_at('B', p['x'], p['y'])
vias = []
thxy = [(p['x'], p['y']) for c in COMPS for p in c['pads'] if p['th']]
for v in VIAS:
    if any(math.hypot(v['x'] - x, v['y'] - y) < 0.4 for x, y in thxy): continue
    dia = max(v['w'], v['h']); dr = 0.3 if v['inner'] > 0.15 else 0.25
    if dia > 1.1: dr = 0.6
    vias.append(dict(x=round(v['x'], 3), y=round(v['y'], 3), dia=round(min(dia, dr + 0.5), 2), drill=dr,
                     root=net_at('F', v['x'], v['y'], True)))

def R(c, n): return next(p['root'] for p in c['pads'] if p['num'] == str(n))
names = {}
def nm(r, s, prio=1):
    if r == 'None': return
    if r not in names or names[r][0] > prio: names[r] = (prio, s)
# Zunge
for gi, g in enumerate(groups, 1):
    if gi <= len(TABN):
        for p in X1['pads']:
            if p['num'] == str(gi): nm(p['root'], TABN[gi - 1], 2)
ops = [c for c in COMPS if c['kind'].startswith('SOIC')]
vp = vn = None
if ops:
    if ops[0]['kind'] == 'SOIC8':
        vp, vn = R(ops[0], 8), R(ops[0], 4)
    else:
        vp, vn = R(ops[0], 4), R(ops[0], 11)
    nm(vp, '+12V', 0); nm(vn, '-12V', 0)
deg = {}
for c in COMPS:
    for p in c['pads']: deg[p['root']] = deg.get(p['root'], 0) + 1
vp = vn = None
gnd = max((r for r in deg if r not in (vp, vn, 'None')), key=lambda r: deg[r])
nm(gnd, 'AGND', 0)
# Opamp-Sektionen
SECT8 = [(1, 2, 3), (7, 6, 5)]; SECT14 = [(1, 2, 3), (7, 6, 5), (8, 9, 10), (14, 13, 12)]
sections = []
for c in ops:
    for so, si, sp in (SECT8 if c['kind'] == 'SOIC8' else SECT14):
        sections.append(dict(op=c['ref'], out=R(c, so), inv=R(c, si), pos=R(c, sp), pins=(so, si, sp)))
tabnet = {names[r][1]: r for r in names}
# erste Stufe: + Eingang am VREF
for s in sections:
    vr = (tabnet.get('I.1-VREF'), tabnet.get('I.2-VREF'))
    s['stage'] = 1 if (s['pos'] in vr or s['inv'] in vr) else 2
    s['swapped'] = s['inv'] in vr
print('Sektionen', [(s['op'], s['pins'][0], s['stage']) for s in sections])
print('Netze', len(set(p['root'] for c in COMPS for p in c['pads'])))
M = dict(comps=COMPS, vias=vias, names={r: n for r, (p, n) in names.items()}, sections=sections, H=H, TAB_Y=TAB_Y,
         X0=float(X0), Y0=float(Y0))
json.dump(M, open(os.path.join(OUT, 'model_raw.json'), 'w'), indent=0)

# ------------------------------------------------------------ Polygone
def rdp(pts, eps):
    pts = np.asarray(pts)
    if len(pts) < 4: return pts
    a, b = pts[0], pts[-1]; ab = b - a; L = np.hypot(*ab)
    d = np.hypot(*(pts - a).T) if L == 0 else np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / L
    i = int(d.argmax())
    if d[i] > eps: return np.vstack([rdp(pts[:i + 1], eps)[:-1], rdp(pts[i:], eps)])
    return np.array([a, b])
def ring(r, eps):
    r = np.asarray(r)
    if np.allclose(r[0], r[-1]): r = r[:-1]
    if len(r) < 4: return r
    k = len(r) // 2
    return np.vstack([rdp(r[:k + 1], eps)[:-1], rdp(np.vstack([r[k:], r[:1]]), eps)[:-1]])
def area(r):
    r = np.asarray(r); return 0.5 * abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1)))
def mask_polys(m, off=(0, 0), eps=0.025):
    z = nd.gaussian_filter(np.pad(m.astype(float), 2), 0.6)
    g = contourpy.contour_generator(z=z, fill_type=contourpy.FillType.OuterOffset)
    out = []
    for pts, of in zip(*g.filled(0.5, 2.0)):
        conv = []
        for i in range(len(of) - 1):
            r = pts[of[i]:of[i + 1]]
            x = (r[:, 0] - 2 + off[1] - X0) / PPM; y = (Y0 - (r[:, 1] - 2 + off[0])) / PPM
            rr = ring(np.c_[x, y], eps)
            if len(rr) >= 3: conv.append(np.round(rr, 4).tolist())
        if conv: out.append((conv[0], conv[1:]))
    return out
res = {'copper': {}, 'silk': {}, 'outline': None}
KL = {'F': 'F.Cu', 'In1': 'In1.Cu', 'In2': 'In2.Cu', 'B': 'B.Cu'}
for L, (l, n) in labs.items():
    items = []
    for i, sl in enumerate(nd.find_objects(l), 1):
        sl2 = tuple(slice(max(s.start - 1, 0), s.stop + 1) for s in sl)
        m = l[sl2] == i
        if m.sum() < 4: continue
        r = repr(f((L, i)))
        for outer, hs in mask_polys(m, (sl2[0].start, sl2[1].start)):
            if area(outer) < 0.01: continue
            items.append(dict(root=r, outer=outer, holes=[h for h in hs if area(h) > 0.004]))
    res['copper'][KL[L]] = items
for nmx, kl in (('TPLACE', 'F.SilkS'), ('BPLACE', 'B.SilkS')):
    if not has(nmx): continue
    a = rgb(nmx); m = ((a == 165).all(-1)) | ((a == 49).all(-1))
    res['silk'][kl] = [dict(outer=o_, holes=h_) for o_, h_ in mask_polys(m, (0, 0), 0.02) if area(o_) > 0.003]
fill = nd.binary_fill_holes(nd.binary_closing(np.pad(o, 3), iterations=3))[3:-3, 3:-3]
board = nd.binary_erosion(fill, iterations=1)
pl = sorted(mask_polys(board, (0, 0), 0.03), key=lambda p: -area(p[0]))
res['outline'] = pl[0][0]
json.dump(res, open(os.path.join(OUT, 'polys_raw.json'), 'w'))
print('Polygone', {k: len(v) for k, v in res['copper'].items()})
