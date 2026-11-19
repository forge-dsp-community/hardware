# Placement refinement: rotations (0/90/180/270) and position swaps of parts with the same footprint,
# scored by crossings of the signal ratsnest (MST per net, plane nets left out) plus its length.
# Moves that make courtyards overlap or leave the outline are rejected. Prints the changes in the
# form of placement.py entries; positions are the legalised ones from the generated board.
#   /usr/bin/python3 tools/opt_place.py UsbAudioPCB.kicad_pcb REF REF ...
import sys, itertools, math
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); T = lambda v: pcbnew.ToMM(v) - 100
MOVE = sys.argv[2:]
PLANE = {'GND', '+3V3', 'XMOS.3V3', 'XMOS.1V0', ''}
W_LEN = 0.05
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)

def box(fp):
    bb = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
    return (T(bb.GetLeft()) + 0.03, T(bb.GetTop()) + 0.03, T(bb.GetRight()) - 0.03, T(bb.GetBottom()) - 0.03)
def tht_boxes(fp):
    out = []
    for p in fp.Pads():
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            bb = p.GetBoundingBox(); out.append((T(bb.GetLeft()) - 0.25, T(bb.GetTop()) - 0.25, T(bb.GetRight()) + 0.25, T(bb.GetBottom()) + 0.25))
    return out
def ov(a, c): return a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]
# obstacles for side B: courtyards of B parts, THT pads of F parts
def legal(ref):
    fp = fps[ref]; a = box(fp)
    for x, y in ((a[0], a[1]), (a[2], a[1]), (a[0], a[3]), (a[2], a[3])):
        if not outline.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x + 100), pcbnew.FromMM(y + 100))): return False
    for r, o in fps.items():
        if r == ref: continue
        if o.IsFlipped() == fp.IsFlipped():
            if ov(a, box(o)): return False
        elif any(ov(a, t) for t in tht_boxes(o)): return False
    return True

def ratsnest():
    pts = {}
    for fp in fps.values():
        for p in fp.Pads():
            n = p.GetNetname()
            if n in PLANE or n.startswith('unconnected'): continue
            pts.setdefault(n, []).append((T(p.GetPosition().x), T(p.GetPosition().y)))
    edges = []
    for n, ps in pts.items():
        if len(ps) < 2: continue
        inn = [ps[0]]; rest = ps[1:]
        while rest:
            d, a, c = min((math.dist(a, c), a, c) for a in inn for c in rest)
            edges.append((n, a, c)); inn.append(c); rest.remove(c)
    return edges
def cross(p1, p2, p3, p4):
    def o(a, c, d): return (c[0] - a[0]) * (d[1] - a[1]) - (c[1] - a[1]) * (d[0] - a[0])
    d1, d2, d3, d4 = o(p3, p4, p1), o(p3, p4, p2), o(p1, p2, p3), o(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0
def score():
    e = ratsnest()
    c = sum(1 for (n1, a1, b1), (n2, a2, b2) in itertools.combinations(e, 2) if n1 != n2 and cross(a1, b1, a2, b2))
    return c + W_LEN * sum(math.dist(a, c_) for n, a, c_ in e), c

cur, c0 = score(); print(f'start: crossings {c0}, score {cur:.1f}')
orig = {r: (T(fps[r].GetPosition().x), T(fps[r].GetPosition().y), fps[r].GetOrientationDegrees()) for r in MOVE}
def fpid(r): return str(fps[r].GetFPID().GetLibItemName())
for sweep in range(4):
    improved = False
    for r in MOVE:
        fp = fps[r]; o0 = fp.GetOrientationDegrees()
        for rot in (0, 90, 180, 270):
            if abs((rot - o0) % 360) < 1: continue
            fp.SetOrientationDegrees(rot)
            if legal(r):
                s, c = score()
                if s < cur - 1e-6: cur = s; o0 = rot; improved = True; print(f'  {r} rot {rot}: crossings {c}, score {s:.1f}', flush=True); continue
            fp.SetOrientationDegrees(o0)
        for q in MOVE:
            if q <= r or fpid(q) != fpid(r): continue
            a, c_ = fps[r], fps[q]; pa, pc = a.GetPosition(), c_.GetPosition()
            a.SetPosition(pc); c_.SetPosition(pa)
            if legal(r) and legal(q):
                s, c = score()
                if s < cur - 1e-6: cur = s; improved = True; print(f'  swap {r} <-> {q}: crossings {c}, score {s:.1f}', flush=True); continue
            a.SetPosition(pa); c_.SetPosition(pc)
    if not improved: break
print('result:')
for r in MOVE:
    x, y, o = T(fps[r].GetPosition().x), T(fps[r].GetPosition().y), fps[r].GetOrientationDegrees()
    if (round(x, 2), round(y, 2), round(o) % 360) != (round(orig[r][0], 2), round(orig[r][1], 2), round(orig[r][2]) % 360):
        print(f"  at('{r}', {x:.2f}, {y:.2f}, {round(o) % 360}, 'B')   # was {orig[r][0]:.2f}, {orig[r][1]:.2f}, {round(orig[r][2]) % 360}")
