"""Rekonstruktion ES9018/PCM4202 AD/DA V4.0: Bauteile, Pads, Netze -> model.json"""
import sys, math, json
sys.path.insert(0, __import__('os').environ.get('REK_TOOLS', 'tools'))
from common import *
from scipy import ndimage as nd

SHRINK = 0.10   # Lötstopp-Freistellung -> Kupferpad

# ---------------------------------------------------------------- Bohrungen
def drill_for(dia, inner):
    if dia > 2.0: return 2.0
    if dia > 1.2: return 0.8
    if dia > 1.0: return 0.6
    if dia > 0.85:
        return 0.5 if inner > 0.3 else 0.4
    return 0.3 if inner > 0.1 else 0.25

def holes_of(mask):
    lab, n = nd.label(mask); out = []
    for i, sl in enumerate(nd.find_objects(lab), 1):
        r = lab[sl] == i; fr = nd.binary_fill_holes(r)
        ys, xs = np.nonzero(r)
        cx = (xs.mean() + sl[1].start - X0) / PPM; cy = (Y0 - ys.mean() - sl[0].start) / PPM
        w = (xs.max() - xs.min() + 1) / PPM; h = (ys.max() - ys.min() + 1) / PPM
        inner = 2 * math.sqrt((fr & ~r).sum() / math.pi) / PPM
        sq = r.sum() / ((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)) > 0.93
        out.append(dict(x=cx, y=cy, w=w, h=h, inner=inner, square=bool(sq)))
    return out

VIAS = holes_of(feat('VIAS'))
THP = holes_of(feat('PADS'))

# ---------------------------------------------------------------- Pad-Helfer
def pad(num, x, y, w, h, side, shape='rect', drill=0.0, th=False):
    return dict(num=str(num), x=round(x, 3), y=round(y, 3), w=round(w, 3), h=round(h, 3),
                side=side, shape=shape, drill=drill, th=th)

COMPS = []
def comp(ref, kind, side, pads, **kw):
    d = dict(ref=ref, kind=kind, side=side, pads=pads); d.update(kw); COMPS.append(d); return d

used = set()   # ids der benutzten pads.json-Einträge
PJ = [p for p in json.load(open(S + 'pads.json'))]
def take(x, y, side, tol=0.15):
    best = None
    for i, p in enumerate(PJ):
        if p[1] == 'via': continue
        if p[0] != side: continue
        d = math.hypot(p[2] - x, p[3] - y)
        if d < tol and (best is None or d < best[0]): best = (d, i)
    if best: used.add(best[1]); return PJ[best[1]]
    return None

# ---------------------------------------------------------------- PCM4202 (SSOP-28, Unterseite)
ss = [p for p in PJ if p[1] == 'smd' and (round(p[4], 1), round(p[5], 1)) == (1.4, 0.5)]
pcm = []
for lo, hi in ([10, 19], [25, 34], [41, 50]):
    g = [p for p in ss if lo < p[2] < hi]
    L = sorted([p for p in g if p[2] < (lo + hi) / 2], key=lambda p: -p[3])
    R = sorted([p for p in g if p[2] > (lo + hi) / 2], key=lambda p: -p[3])
    pads = []
    for i, p in enumerate(R): pads.append(pad(i + 1, p[2], p[3], 1.45, 0.42, 'B'))
    for i, p in enumerate(L): pads.append(pad(28 - i, p[2], p[3], 1.45, 0.42, 'B'))
    for p in g: take(p[2], p[3], 'B')
    cx = (L[0][2] + R[0][2]) / 2; cy = (L[0][3] + L[-1][3]) / 2
    pcm.append(comp('IC10x', 'PCM4202', 'B', pads, cx=cx, cy=cy, rot=0))

# ---------------------------------------------------------------- ES9018 (TQFP-64, Unterseite)
pins = qfp_pins(23.33, 19.64, 16, 0.5, 5.59, True, 270)
pads = []
for n, (x, y) in pins.items():
    horiz = abs(x - 23.33) > 4   # Pad liegt links/rechts -> lang in x
    pads.append(pad(n, x, y, 1.55 if horiz else 0.28, 0.28 if horiz else 1.55, 'B'))
for p in PJ:
    if p[1] == 'smd' and p[0] == 'B' and 17 < p[2] < 29.5 and 13.5 < p[3] < 26 and min(p[4], p[5]) < 0.9:
        used.add(PJ.index(p))
comp('IC105', 'ES9018', 'B', pads, cx=23.33, cy=19.64, rot=0)

# ---------------------------------------------------------------- PCA9554 (HVQFN-16 3x3, Unterseite)
pins = qfp_pins(4.53, 43.645, 4, 0.5, 1.52, True, 0)
pads = []
for n, (x, y) in pins.items():
    horiz = abs(x - 4.53) > 1
    pads.append(pad(n, x, y, 0.8 if horiz else 0.28, 0.28 if horiz else 0.8, 'B'))
pads.append(pad(17, 4.53, 43.645, 1.6, 1.6, 'B'))
for p in PJ:
    if p[0] == 'B' and p[1] == 'smd' and abs(p[2] - 4.53) < 2.1 and abs(p[3] - 43.645) < 2.1: used.add(PJ.index(p))
comp('IC104', 'PCA9554', 'B', pads, cx=4.53, cy=43.645, rot=0)

# ---------------------------------------------------------------- Regler / weitere ICs (nicht im Schaltplanbild)
def take_all(lst, side='B', DEF=(0.6, 1.0), FIX=None):
    out = []
    for n, x, y in lst:
        p = take(x, y, side, 0.3)
        w, h = (p[4] - SHRINK, p[5] - SHRINK) if p else DEF
        if FIX: w, h = FIX
        out.append(pad(n, x if FIX else (p[2] if p else x), y if FIX else (p[3] if p else y), w, h, side))
    return out
# SOT-23-5 LDO (1V2_AVCC)
comp('U201', 'SOT23-5', 'B', take_all([(1, 7.15, 7.79), (2, 7.15, 6.77), (3, 7.15, 5.84), (4, 9.78, 5.84), (5, 9.78, 7.79)]),
     cx=8.47, cy=6.8)
# SOT-89 Regler (1V2_DVCC)
comp('U202', 'SOT89', 'B', take_all([(1, 10.71, 24.05), (2, 8.09, 22.48), (3, 10.71, 21.08)]) +
     [pad(4, 10.71, 22.52, 1.17, 0.83, 'B')], cx=9.6, cy=22.5)
take(10.71, 22.52, 'B')
# SOIC-8 (3V3_AVCC_L/R)
comp('U203', 'SOIC8', 'B', take_all([(1, 37.59, 16.98), (2, 38.86, 16.98), (3, 40.13, 16.98), (4, 41.40, 16.98),
                                      (5, 41.40, 22.23), (6, 40.13, 22.23), (7, 38.86, 22.23), (8, 37.59, 22.23)], FIX=(0.75, 2.2)),
     cx=39.5, cy=19.6)
# SOT-23 (3-polig)
comp('U204', 'SOT23', 'B', take_all([(1, 50.50, 7.96), (2, 51.44, 7.96), (3, 49.57, 10.5)]), cx=50.5, cy=9.2)

# ---------------------------------------------------------------- Lötjumper (Oberseite) FS0 / FS1 / HPFD
for ref, (x, y) in (('JP1', (17.72, 36.94)), ('JP2', (33.3, 36.43)), ('JP3', (48.54, 36.43))):
    take(x, y, 'T', 0.3)
    comp(ref, 'SJ3', 'F', [pad(1, x, y + 1.25, 1.0, 0.9, 'F'), pad(2, x, y, 1.0, 0.9, 'F'), pad(3, x, y - 1.25, 1.0, 0.9, 'F')],
         cx=x, cy=y)

# ---------------------------------------------------------------- X100: 20 Halbloch-Kontakte + Versorgungspads
xp = sorted([h for h in THP if h['x'] < 1.5 and 10 < h['y'] < 51], key=lambda h: -h['y'])
pads = []
for i, h in enumerate(xp):
    pads.append(pad(i + 1, h['x'], h['y'], 1.8, 1.7, 'FB', 'rect', 0.7, True))
pw = [(21, 55.71), (22, 52.92), (23, 7.76), (24, 3.40)]   # Versorgungs-Randpads (Lage aus Kupferbild)
for n, y in pw:
    pads.append(pad(n, 0.6, y, 1.2, 1.5, 'FB'))
comp('X100', 'EDGE', 'B', pads, cx=0.5, cy=30.5)
for p in PJ:
    if p[2] < 2.3: used.add(PJ.index(p))

# ---------------------------------------------------------------- TH-Stiftleisten
rest_th = [h for h in THP if h not in xp]
grpA = sorted([h for h in rest_th if h['x'] < 5], key=lambda h: -h['y'])
grpB = sorted([h for h in rest_th if h['x'] > 40], key=lambda h: -h['y'])
for ref, g in (('X101', grpA), ('X102', grpB)):
    pads = [pad(i + 1, h['x'], h['y'], h['w'], h['h'], 'FB', 'rect' if h['square'] else 'circle',
                round(min(1.0, max(0.7, h['inner'] + 0.1)), 1), True) for i, h in enumerate(g)]
    comp(ref, 'HDR', 'B', pads, cx=g[0]['x'], cy=sum(h['y'] for h in g) / len(g))
    for h in g:
        for side in 'BT': take(h['x'], h['y'], side, 0.5)
print('TH-Gruppen', len(xp), len(grpA), len(grpB), 'rest', len(rest_th) - len(grpA) - len(grpB))

# ---------------------------------------------------------------- Ausgangs-Steckplätze J1..J4 (I/V-DAC-Ausgangsplatinen)
for k, x in enumerate((14.78, 24.85, 35.01, 45.17), 1):
    rows = (7.46, 6.19, 4.92, 3.65, 2.38, 1.11)
    comp('J%d' % k, 'OUTSLOT', 'B', [pad(i + 1, x, y, 1.8, 0.72, 'B') for i, y in enumerate(rows)], cx=x, cy=4.28)

# ---------------------------------------------------------------- 2-polige Bauteile (Paarbildung)
def cls(p): return {round(p[4], 1), round(p[5], 1)}
free = [i for i, p in enumerate(PJ) if p[1] == 'smd' and i not in used and min(p[4], p[5]) > 0.3 and p[2] > 2.3]
pairs = []
# Tantal-Reihe y=48.81 (VREF-Elkos): zusammengewachsene Doppelpads teilen, dann der Reihe nach paaren
row = sorted([i for i in free if abs(PJ[i][3] - 48.81) < 0.1 and round(PJ[i][5], 1) == 2.4], key=lambda i: PJ[i][2])
seq = []
for i in row:
    p = PJ[i]; used.add(i)
    if p[4] > 3:
        PJ.append([p[0], 'smd', p[2] - 1.02, p[3], 2.2, 2.37, 1]); seq.append(len(PJ) - 1)
        PJ.append([p[0], 'smd', p[2] + 1.02, p[3], 2.2, 2.37, 1]); seq.append(len(PJ) - 1)
    else: seq.append(i)
free = [i for i in free if i not in row]
for k in range(0, len(seq) - 1, 2): pairs.append((seq[k], seq[k + 1]))
def nearest(i, pool):
    a = PJ[i]; best = None
    for j in pool:
        if j == i: continue
        b = PJ[j]
        if b[0] != a[0] or cls(a) != cls(b): continue
        if not (abs(a[2] - b[2]) < 0.06 or abs(a[3] - b[3]) < 0.06): continue
        d = math.hypot(a[2] - b[2], a[3] - b[3])
        if best is None or d < best[0]: best = (d, j)
    return best
pool = set(free)
for i in sorted(free):
    if i not in pool: continue
    b = nearest(i, pool)
    if not b or b[0] > 6.5: continue
    bb = nearest(b[1], pool)
    if bb and bb[1] == i:
        pairs.append((i, b[1])); pool -= {i, b[1]}
# zusammengewachsene Doppelpads (Tantal nebeneinander, 4.06 breit) aufteilen
for i in list(pool):
    p = PJ[i]
    if round(p[4], 1) == 4.1 and round(p[5], 1) == 2.4:
        pool.discard(i)
        PJ.append([p[0], 'smd', p[2] - 1.02, p[3], 2.2, 2.37, 1]); PJ.append([p[0], 'smd', p[2] + 1.02, p[3], 2.2, 2.37, 1])
        pool |= {len(PJ) - 2, len(PJ) - 1}
for i in sorted(pool):
    if i not in pool: continue
    b = nearest(i, pool)
    if b and b[0] < 6.5:
        bb = nearest(b[1], pool)
        if bb and bb[1] == i: pairs.append((i, b[1])); pool -= {i, b[1]}

def twopin_kind(p, d):
    s = (round(max(p[4], p[5]), 1), round(min(p[4], p[5]), 1))
    if s == (2.4, 2.2): return 'TANT_C' if d > 4 else 'TANT_B'
    if s == (1.7, 1.5): return '0805'
    if s == (1.3, 1.2): return '0603'
    if s == (1.4, 0.8): return '0402L'
    return 'SMD2'
n2 = 0
for i, j in pairs:
    a, b = PJ[i], PJ[j]; used |= {i, j}
    d = math.hypot(a[2] - b[2], a[3] - b[3])
    side = 'B' if a[0] == 'B' else 'F'
    n2 += 1
    comp('P%d' % n2, twopin_kind(a, d), side,
         [pad(1, a[2], a[3], a[4] - SHRINK, a[5] - SHRINK, side), pad(2, b[2], b[3], b[4] - SHRINK, b[5] - SHRINK, side)],
         cx=(a[2] + b[2]) / 2, cy=(a[3] + b[3]) / 2)

# ---------------------------------------------------------------- Restliche Pads -> Anschlussgruppen
rest = [i for i in range(len(PJ)) if i not in used and PJ[i][1] in ('smd', 'th') and i not in pairs
        and min(PJ[i][4], PJ[i][5]) > 0.3 and max(PJ[i][4], PJ[i][5]) < 8 and PJ[i][2] > 2.0]
rest = [i for i in rest if not any(i in pr for pr in pairs)]
groups = []
for i in rest:
    p = PJ[i]
    for g in groups:
        if any(math.hypot(PJ[k][2] - p[2], PJ[k][3] - p[3]) < 3.2 for k in g): g.append(i); break
    else: groups.append([i])
def _ov(a, b):
    return abs(a['x'] - b['x']) < (a['w'] + b['w']) / 2 and abs(a['y'] - b['y']) < (a['h'] + b['h']) / 2 and a['side'] == b['side']
for gi, g in enumerate(groups, 1):
    pads = []
    for k, i in enumerate(g, 1):
        p = PJ[i]; side = 'B' if p[0] == 'B' else 'F'
        q = pad(k, p[2], p[3], p[4] - SHRINK, p[5] - SHRINK, side)
        if q['w'] < 0.35 and q['h'] < 0.35: continue        # Maskenreste
        for o in pads:
            while (_ov(q, o) or abs(q['x']-o['x'])<(q['w']+o['w'])/2+0.1 and abs(q['y']-o['y'])<(q['h']+o['h'])/2+0.1 and q['side']==o['side']) and q['w'] > 0.3 and q['h'] > 0.3:
                q['w'] -= 0.1; q['h'] -= 0.1; o['w'] -= 0.1; o['h'] -= 0.1
        pads.append(q)
    if not pads: continue
    for k, q in enumerate(pads, 1): q['num'] = str(k)
    comp('J%d' % (200 + gi), 'PADGRP', pads[0]['side'], pads,
         cx=sum(p['x'] for p in pads) / len(pads), cy=sum(p['y'] for p in pads) / len(pads))

# ---------------------------------------------------------------- Netze zuordnen
for c in COMPS:
    for p in c['pads']:
        side = 'B' if p['side'] in ('B', 'FB') else 'F'
        r = net_at(side, p['x'], p['y'], p['th'])
        if r is None and p['side'] == 'FB': r = net_at('F', p['x'], p['y'])
        p['root'] = repr(r)

COMPS[:] = [c for c in COMPS if any(p['root'] not in ('None',) for p in c['pads'])]
# Vias (ohne die, die als Bauteil-Pad verwendet werden)
padxy = [(p['x'], p['y']) for c in COMPS for p in c['pads'] if p['th']]
vias = []
for v in VIAS:
    if any(math.hypot(v['x'] - x, v['y'] - y) < 0.3 for x, y in padxy): continue
    dia = max(v['w'], v['h']); dr = drill_for(dia, v['inner'])
    r = net_at('TH', v['x'], v['y'], True)
    vias.append(dict(x=round(v['x'], 3), y=round(v['y'], 3), dia=round(min(dia, dr + 0.9), 2), drill=dr, root=repr(r)))

json.dump(dict(comps=COMPS, vias=vias), open(S + 'model_raw.json', 'w'), indent=0)
from collections import Counter
print('Bauteile', len(COMPS), Counter(c['kind'] for c in COMPS))
print('Vias', len(vias), Counter(v['drill'] for v in vias))
