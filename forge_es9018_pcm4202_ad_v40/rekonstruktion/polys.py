"""Kupfer-, Bestückungsdruck- und Umriss-Polygone (mm, Eagle-Koordinaten) -> polys.json"""
import sys, json
sys.path.insert(0, __import__('os').environ.get('REK_TOOLS', 'tools'))
from common import *
from scipy import ndimage as nd
import contourpy

M = json.load(open(S + 'model.json'))
RM = M.get('rootmap', {}); NN = M['netnames']

def rdp(pts, eps):
    pts = np.asarray(pts)
    if len(pts) < 4: return pts
    a, b = pts[0], pts[-1]; ab = b - a; L = np.hypot(*ab)
    if L == 0: d = np.hypot(*(pts - a).T)
    else: d = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / L
    i = int(d.argmax())
    if d[i] > eps:
        return np.vstack([rdp(pts[:i + 1], eps)[:-1], rdp(pts[i:], eps)])
    return np.array([a, b])

def simplify_ring(r, eps=0.025):
    r = np.asarray(r)
    if np.allclose(r[0], r[-1]): r = r[:-1]
    if len(r) < 4: return r
    # an zwei entfernten Punkten aufteilen
    k = len(r) // 2
    a = rdp(np.vstack([r[:k + 1]]), eps); b = rdp(np.vstack([r[k:], r[:1]]), eps)
    return np.vstack([a[:-1], b[:-1]])

def mask_polys(m, sl_off=(0, 0), eps=0.025):
    """Binärmaske -> [(outer, [holes])] in mm"""
    z = np.pad(m.astype(float), 2)
    z = nd.gaussian_filter(z, 0.6)
    g = contourpy.contour_generator(z=z, fill_type=contourpy.FillType.OuterOffset)
    pts_list, offs = g.filled(0.5, 2.0)
    out = []
    for pts, off in zip(pts_list, offs):
        rings = [pts[off[i]:off[i + 1]] for i in range(len(off) - 1)]
        conv = []
        for r in rings:
            x = (r[:, 0] - 2 + sl_off[1] - X0) / PPM; y = (Y0 - (r[:, 1] - 2 + sl_off[0])) / PPM
            rr = simplify_ring(np.c_[x, y], eps)
            if len(rr) >= 3: conv.append(np.round(rr, 4).tolist())
        if conv: out.append((conv[0], conv[1:]))
    return out

def area(r):
    r = np.asarray(r); return 0.5 * abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1)))

res = {'copper': {}, 'silk': {}, 'outline': None}
LM = {'F': 'F.Cu', 'In1': 'In1.Cu', 'In2': 'In2.Cu', 'B': 'B.Cu'}
for L, kl in LM.items():
    lab, n = labs[L]
    items = []
    for i, sl in enumerate(nd.find_objects(lab), 1):
        sl2 = tuple(slice(max(s.start - 1, 0), s.stop + 1) for s in sl)
        m = lab[sl2] == i
        if m.sum() < 4: continue
        r = repr(f((L, i))); r = RM.get(r, r)
        net = NN.get(r, '')
        for outer, holes in mask_polys(m, (sl2[0].start, sl2[1].start)):
            if area(outer) < 0.01: continue
            items.append(dict(net=net, outer=outer, holes=[h for h in holes if area(h) > 0.004]))
    res['copper'][kl] = items
    print(kl, len(items), 'Polygone,', sum(1 for it in items if not it['net']), 'ohne Netz')

for name, kl in (('TPLACE', 'F.SilkS'), ('BPLACE', 'B.SilkS')):
    a = rgb(name)
    m = ((a == 165).all(-1)) | ((a == 49).all(-1))   # Bestückungsdruck (grau)
    items = []
    for outer, holes in mask_polys(m, (0, 0), 0.02):
        if area(outer) < 0.003: continue
        items.append(dict(outer=outer, holes=holes))
    res['silk'][kl] = items
    print(kl, len(items))

# Umriss: Fräs-/Umrisslinie füllen
o = (rgb('TOP') == 75).all(-1) | (rgb('MILLING') == 75).all(-1)
o = nd.binary_closing(o, iterations=1)
fill = nd.binary_fill_holes(o)
lab, n = nd.label(fill); big = np.argmax(nd.sum(fill, lab, range(1, n + 1))) + 1
board = lab == big
# Mittellinie der Umrisslinie: Fläche um halbe Linienbreite erodieren
board = nd.binary_erosion(board, iterations=1)
polys = mask_polys(board, (0, 0), 0.03)
polys.sort(key=lambda p: -area(p[0]))
res['outline'] = polys[0][0]
print('Umriss Punkte', len(polys[0][0]), 'Fläche %.1f mm2' % area(polys[0][0]))
xs = [p[0] for p in polys[0][0]]; ys = [p[1] for p in polys[0][0]]
print('Umriss bbox %.2f..%.2f x %.2f..%.2f' % (min(xs), max(xs), min(ys), max(ys)))
json.dump(res, open(S + 'polys.json', 'w'))
