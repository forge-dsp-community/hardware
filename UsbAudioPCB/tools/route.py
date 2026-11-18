# Grid router for F.Cu/B.Cu: A* on a 0.1 mm grid with 45-degree steps, bend and via costs, net
# classes from the project (width/clearance), nets in priority order. Plane nets (GND, +3V3,
# XMOS.3V3, XMOS.1V0) only get the pads that have no fanout yet, routed to the nearest copper of
# their net. The second USB line is pulled next to the first one (pair at 0.4 mm pitch).
#   /usr/bin/python3 tools/route.py UsbAudioPCB.kicad_pcb
import sys, math, heapq, json, re, time, fnmatch
import pcbnew

PATH = sys.argv[1] if len(sys.argv) > 1 else 'UsbAudioPCB.kicad_pcb'
b = pcbnew.LoadBoard(PATH)
T, mm = pcbnew.ToMM, pcbnew.FromMM
G = 0.1                                  # grid
X0, Y0 = 100.0 - 1, 100.0 - 1             # board origin is (100, 100)
NX, NY = int(67 / G), int(41 / G)
VIA_D, VIA_DRILL = 0.5, 0.25
PLANE = {'GND', '+3V3', 'XMOS.3V3', 'XMOS.1V0'}
F, B = 0, 1

# ---- net classes from the project file
pro = json.load(open(PATH.replace('.kicad_pcb', '.kicad_pro')))
cls = {c['name']: c for c in pro['net_settings']['classes']}
pats = pro['net_settings'].get('netclass_patterns', [])
def netclass(n):
    for p in pats:
        if fnmatch.fnmatchcase(n, p['pattern']): return cls[p['netclass']]
    return cls['Default']
def width(n): return netclass(n)['track_width']
CLR = 0.15

# ---- nets
nets = {}
for n in b.GetNetsByName().keys():
    s = str(n)
    if s and not s.startswith('unconnected'): nets[s] = len(nets) + 1
NID = nets

# ---- occupancy: owner[layer][cell] = net id within reach of copper, -2 = several nets, 0 = free
# we store the copper itself (pad/track/via shapes) as primitives and rasterise with a per-query
# inflation: cell blocked for net n if some copper of another net is closer than w/2 + clr.
# For speed, rasterise once with the largest inflation for the default class (0.075 + 0.15) and
# once for vias (0.25 + 0.15); wider nets check a second ring on the fly.
INF_T = 0.075 + CLR + 0.03
INF_V = VIA_D / 2 + CLR + 0.03
own_t = [bytearray(NX * NY) for _ in (F, B)]     # 0 free, 1..254 net (mod), 255 multiple
own_v = [bytearray(NX * NY) for _ in (F, B)]
netof_t = [dict(), dict()]                       # cell -> net id (exact, for ids >= 255)
def idx(i, j): return j * NX + i
def cell(x, y): return int(round((x - X0) / G)), int(round((y - Y0) / G))
def pos(i, j): return X0 + i * G, Y0 + j * G

def mark(arr, nd, layer, i, j, nid):
    k = idx(i, j)
    cur = nd[layer].get(k)
    if cur is None: nd[layer][k] = nid; arr[layer][k] = 1
    elif cur != nid: nd[layer][k] = -2; arr[layer][k] = 255
netof_v = [dict(), dict()]

def raster_rect(x0, y0, x1, y1, layers, nid, inf, arr, nd):
    i0, j0 = cell(x0 - inf, y0 - inf); i1, j1 = cell(x1 + inf, y1 + inf)
    for j in range(max(0, j0), min(NY, j1 + 1)):
        y = Y0 + j * G
        dy = max(y0 - y, 0, y - y1)
        if dy > inf: continue
        for i in range(max(0, i0), min(NX, i1 + 1)):
            x = X0 + i * G
            dx = max(x0 - x, 0, x - x1)
            if dx * dx + dy * dy <= inf * inf:
                for L in layers: mark(arr, nd, L, i, j, nid)
def raster_seg(xa, ya, xb, yb, hw, layers, nid, inf, arr, nd):
    r = hw + inf
    i0, j0 = cell(min(xa, xb) - r, min(ya, yb) - r); i1, j1 = cell(max(xa, xb) + r, max(ya, yb) + r)
    dx, dy = xb - xa, yb - ya; L2 = dx * dx + dy * dy
    for j in range(max(0, j0), min(NY, j1 + 1)):
        y = Y0 + j * G
        for i in range(max(0, i0), min(NX, i1 + 1)):
            x = X0 + i * G
            t = 0 if L2 == 0 else max(0, min(1, ((x - xa) * dx + (y - ya) * dy) / L2))
            if math.hypot(x - xa - t * dx, y - ya - t * dy) <= r:
                for L in layers: mark(arr, nd, L, i, j, nid)

def add_obstacle_rect(x0, y0, x1, y1, layers, nid):
    raster_rect(x0, y0, x1, y1, layers, nid, INF_T, own_t, netof_t)
    raster_rect(x0, y0, x1, y1, layers, nid, INF_V, own_v, netof_v)
def add_obstacle_seg(xa, ya, xb, yb, hw, layers, nid):
    raster_seg(xa, ya, xb, yb, hw, layers, nid, INF_T, own_t, netof_t)
    raster_seg(xa, ya, xb, yb, hw, layers, nid, INF_V, own_v, netof_v)

t0 = time.time()
pads_of = {}                                   # net -> list of (ref.pad, x, y, layers, rect)
PAD_OF_RECT = {}                               # rect -> pad, for the exact pad shape in pad_cells
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname(); nid = NID.get(n, 9999 + len(pads_of))
        layers = [L for L, lid in ((F, pcbnew.F_Cu), (B, pcbnew.B_Cu)) if p.IsOnLayer(lid)]
        if not layers: continue
        bb = p.GetBoundingBox()
        rect = (T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()))
        add_obstacle_rect(*rect, layers, nid)
        PAD_OF_RECT[rect] = p
        if n in NID:
            pads_of.setdefault(n, []).append((f'{fp.GetReference()}.{p.GetNumber()}', T(p.GetPosition().x), T(p.GetPosition().y), layers, rect, p))
for t in b.GetTracks():
    n = t.GetNetname(); nid = NID.get(n, 0)
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = T(t.GetPosition().x), T(t.GetPosition().y); r = T(t.GetWidth(pcbnew.F_Cu)) / 2
        add_obstacle_seg(x, y, x, y, r, [F, B], nid)
    else:
        L = F if t.GetLayer() == pcbnew.F_Cu else B
        add_obstacle_seg(T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y), T(t.GetWidth()) / 2, [L], nid)
# board edge and rule areas: blocked for everyone
outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)
EDGE_T, EDGE_V = 0.3 + 0.075, 0.3 + VIA_D / 2
edge_ok_t = bytearray(NX * NY); edge_ok_v = bytearray(NX * NY)
chain = outline.Outline(0)
edges = [(T(chain.CPoint(k).x), T(chain.CPoint(k).y), T(chain.CPoint((k + 1) % chain.PointCount()).x), T(chain.CPoint((k + 1) % chain.PointCount()).y))
         for k in range(chain.PointCount())]
for j in range(NY):
    for i in range(NX):
        x, y = pos(i, j)
        if not outline.Contains(pcbnew.VECTOR2I(mm(x), mm(y))): continue
        d = min(math.hypot(x - xa - max(0, min(1, ((x - xa) * (xb - xa) + (y - ya) * (yb - ya)) / (((xb - xa) ** 2 + (yb - ya) ** 2) or 1))) * (xb - xa),
                           y - ya - max(0, min(1, ((x - xa) * (xb - xa) + (y - ya) * (yb - ya)) / (((xb - xa) ** 2 + (yb - ya) ** 2) or 1))) * (yb - ya))
                for xa, ya, xb, yb in edges)
        if d >= EDGE_T: edge_ok_t[idx(i, j)] = 1
        if d >= EDGE_V: edge_ok_v[idx(i, j)] = 1
# rule areas inside footprints (X103: no tracks on F under the card slot): blocked for everyone
for fp in b.GetFootprints():
    for z in fp.Zones():
        if not (z.GetIsRuleArea() and z.GetDoNotAllowTracks()): continue
        bb = z.GetBoundingBox()
        zl = [L for L, lid in ((F, pcbnew.F_Cu), (B, pcbnew.B_Cu)) if z.IsOnLayer(lid)]
        add_obstacle_rect(T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()), zl, -7)
print(f'raster {time.time() - t0:.1f}s', flush=True)

def free_t(L, k, nid):
    if not edge_ok_t[k]: return False
    o = own_t[L][k]
    if o == 0: return True
    return netof_t[L].get(k) == nid
def free_v(k, nid):
    if not edge_ok_v[k]: return False
    for L in (F, B):
        o = own_v[L][k]
        if o and netof_v[L].get(k) != nid: return False
    return True
# wide nets: the track grows by (w - 0.15)/2 -> check neighbours in that radius too
def ring(r):
    n = int(math.ceil(r / G))
    return [(di, dj) for di in range(-n, n + 1) for dj in range(-n, n + 1) if di * di + dj * dj <= (r / G) ** 2]

DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
VIA_COST, BEND45, BEND90 = 7.0, 0.6, 6.0
OFFDIR = 2.2      # step against the preferred direction of the layer (F horizontal, B vertical)
DIAG = 1.7        # diagonal step (only as 45-degree transition)

def astar(nid, starts, targets, extra, attract=None):
    """starts/targets: sets of (i, j, L); extra: list of (di,dj) offsets that must be free (wide nets)"""
    tl = list(targets)
    tx = sum(t[0] for t in tl) / len(tl); ty = sum(t[1] for t in tl) / len(tl)
    def h(i, j):
        dx, dy = abs(i - tx), abs(j - ty)
        return (max(dx, dy) + 0.414 * min(dx, dy)) * 0.98
    openq, best, prev = [], {}, {}
    for (i, j, L) in starts:
        s = (i, j, L, -1)
        best[s] = 0; heapq.heappush(openq, (h(i, j), 0, s))
    def ok(i, j, L):
        if not (0 <= i < NX and 0 <= j < NY): return False
        k = idx(i, j)
        if (i, j, L) in targets: return True
        if not free_t(L, k, nid): return False
        for di, dj in extra:
            ii, jj = i + di, j + dj
            if not (0 <= ii < NX and 0 <= jj < NY) or not free_t(L, idx(ii, jj), nid): return False
        return True
    n = 0
    while openq:
        f, g, s = heapq.heappop(openq)
        if best.get(s, 1e18) < g: continue
        i, j, L, d = s
        if (i, j, L) in targets:
            path = [s]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path[::-1]
        n += 1
        if n > 2500000: return None
        for nd, (di, dj) in enumerate(DIRS):
            ii, jj = i + di, j + dj
            if not ok(ii, jj, L): continue
            if di and dj and not (ok(i + di, j, L) and ok(i, j + dj, L)): continue
            if di and dj: c = DIAG
            elif (L == F and dj) or (L == B and di): c = OFFDIR
            else: c = 1.0
            if d >= 0 and nd != d:
                turn = min((nd - d) % 8, (d - nd) % 8)
                c += BEND45 if turn == 1 else BEND90 if turn == 2 else 50
            if attract is not None and (ii, jj, L) in attract: c *= 0.55
            ns = (ii, jj, L, nd); ng = g + c
            if ng < best.get(ns, 1e18):
                best[ns] = ng; prev[ns] = s; heapq.heappush(openq, (ng + h(ii, jj), ng, ns))
        # via
        if free_v(idx(i, j), nid):
            ns = (i, j, 1 - L, -1); ng = g + VIA_COST
            if ng < best.get(ns, 1e18):
                best[ns] = ng; prev[ns] = s; heapq.heappush(openq, (ng + h(i, j), ng, ns))
    return None

def pad_cells(rect, layers):
    x0, y0, x1, y1 = rect
    out = set()
    i0, j0 = cell(x0, y0); i1, j1 = cell(x1, y1)
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            x, y = pos(i, j)
            if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
                p = PAD_OF_RECT.get(rect)
                # the track end (centre +/- half width) must lie on the pad copper, not in the bbox corner
                if p is not None and not p.HitTest(pcbnew.VECTOR2I(mm(x), mm(y))): continue
                for L in layers: out.add((i, j, L))
    if not out:
        cx, cy = cell((x0 + x1) / 2, (y0 + y1) / 2)
        for L in layers: out.add((cx, cy, L))
    return out

new_tracks, new_vias = [], []
def commit(net, nid, path, w):
    """path of grid states -> segments/vias; rasterise as obstacles"""
    pts = [(pos(i, j), L) for i, j, L, d in path]
    seg_start = 0
    for k in range(1, len(pts) + 1):
        if k == len(pts) or pts[k][1] != pts[k - 1][1]:
            run = [p for p, L in pts[seg_start:k]]; L = pts[seg_start][1]
            # simplify collinear
            poly = [run[0]]
            for q in range(1, len(run) - 1):
                ax, ay = poly[-1]; bx, by = run[q]; cx, cy = run[q + 1]
                if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9: poly.append(run[q])
            if len(run) > 1: poly.append(run[-1])
            for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
                new_tracks.append((xa, ya, xb, yb, w, L, net)); add_obstacle_seg(xa, ya, xb, yb, w / 2, [L], nid)
            if k < len(pts):
                (vx, vy), _ = pts[k - 1]
                new_vias.append((vx, vy, net)); add_obstacle_seg(vx, vy, vx, vy, VIA_D / 2, [F, B], nid)
            seg_start = k

def copper_cells(net):
    """cells of all copper already belonging to the net (pads with fanout, tracks, vias)"""
    out = set()
    for t in b.GetTracks():
        if t.GetNetname() != net: continue
        if t.Type() == pcbnew.PCB_VIA_T:
            i, j = cell(T(t.GetPosition().x), T(t.GetPosition().y)); out |= {(i, j, F), (i, j, B)}
        else:
            L = F if t.GetLayer() == pcbnew.F_Cu else B
            xa, ya, xb, yb = T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y)
            n = max(1, int(math.hypot(xb - xa, yb - ya) / G))
            for q in range(n + 1):
                i, j = cell(xa + (xb - xa) * q / n, ya + (yb - ya) * q / n); out.add((i, j, L))
    for xa, ya, xb, yb, w, L, n2 in new_tracks:
        if n2 != net: continue
        n = max(1, int(math.hypot(xb - xa, yb - ya) / G))
        for q in range(n + 1):
            i, j = cell(xa + (xb - xa) * q / n, ya + (yb - ya) * q / n); out.add((i, j, L))
    for vx, vy, n2 in new_vias:
        if n2 == net:
            i, j = cell(vx, vy); out |= {(i, j, F), (i, j, B)}
    return out

def pad_has_copper(p):
    for t in b.GetTracks():
        if t.GetNetname() == p.GetNetname() and t.Type() != pcbnew.PCB_VIA_T:
            if p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd()): return True
    return p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH

# ---- order and passes: nets that fail move to the front (after the critical ones) in the next pass
import copy
base = (copy.deepcopy(own_t), copy.deepcopy(own_v), copy.deepcopy(netof_t), copy.deepcopy(netof_v))
ORDER = ['USB.1.DP', 'USB.1.DM', 'COM.D+', 'COM.D-', 'XMOS.MCLK', 'MCLK.22M', 'MCLK.24M', 'XMOS.CLK', 'XMOS.CLK.OSC',
         'I2S.BCLK.X', 'I2S.LRCK.X', 'I2S.SDATA.X', 'SPDIF.X', 'IN.I2S.BCLK.0', 'IN.I2S.LRCK.0', 'IN.I2S.SDATA.0', 'IN.SPDIF.1',
         'XQ.CLK', 'XQ.CS', 'XQ.D0', 'XQ.D1', 'XQ.D2', 'XQ.D3']
rest = sorted((n for n in nets if n not in ORDER and n not in PLANE),
              key=lambda n: sum(abs(a[1] - c[1]) + abs(a[2] - c[2]) for a in pads_of.get(n, []) for c in pads_of.get(n, [])[:1]))
order = ORDER + rest + sorted(PLANE)
best_run = None
for pass_no in range(int(sys.argv[2]) if len(sys.argv) > 2 else 3):
    own_t[:], own_v[:], = copy.deepcopy(base[0]), copy.deepcopy(base[1])
    netof_t[:], netof_v[:] = copy.deepcopy(base[2]), copy.deepcopy(base[3])
    new_tracks.clear(); new_vias.clear()
    failed, done = [], 0
    pair_cells = None
    for net in order:
        pads = pads_of.get(net, [])
        if len(pads) < 2 and net not in PLANE: continue
        nid = NID[net]; w = width(net)
        extra = ring(max(0.0, (w - 0.15) / 2)) if w > 0.16 else []
        if net in PLANE:
            todo = [pd for pd in pads if not pad_has_copper(pd[5])]
            for name, x, y, layers, rect, p in todo:
                tree = copper_cells(net) - pad_cells(rect, layers)
                if not tree: failed.append(f'{net}:{name}'); continue
                path = astar(nid, pad_cells(rect, layers), tree, extra)
                if path: commit(net, nid, path, w); done += 1
                else: failed.append(f'{net}:{name}')
            continue
        remaining = pads[1:]
        tree = pad_cells(pads[0][4], pads[0][3])
        attract = pair_cells if net in ('USB.1.DM', 'COM.D-') and pair_cells else None
        while remaining:
            tl = list(tree)[:300]
            remaining.sort(key=lambda pd: min(abs(pd[1] - pos(i, j)[0]) + abs(pd[2] - pos(i, j)[1]) for i, j, L in tl))
            name, x, y, layers, rect, p = remaining.pop(0)
            tgt = pad_cells(rect, layers)
            path = astar(nid, tree | copper_cells(net), tgt, extra, attract)
            if path is None:
                failed.append(f'{net}:{name}'); continue
            commit(net, nid, path, w); done += 1
            tree |= tgt | copper_cells(net)
        if net in ('USB.1.DP', 'COM.D+'):
            cells = copper_cells(net); pair_cells = set()
            k = int(round((w + 0.15) / G))
            for i, j, L in cells:
                for di, dj in ring(k * G + 0.05):
                    if abs(math.hypot(di, dj) - k) < 0.75: pair_cells.add((i + di, j + dj, L))
    print(f'pass {pass_no}: routed {done}, failed {len(failed)}', flush=True)
    if best_run is None or len(failed) < len(best_run[2]):
        best_run = (list(new_tracks), list(new_vias), list(failed), done)
    if not failed: break
    fnets = []
    for f_ in failed:
        n_ = f_.split(':')[0]
        if n_ not in fnets and n_ not in PLANE: fnets.append(n_)
    order = ORDER + fnets + [n for n in order if n not in ORDER and n not in fnets]
new_tracks[:], new_vias[:], failed, done = best_run[0], best_run[1], best_run[2], best_run[3]

# ---- write into the board
for xa, ya, xb, yb, w, L, net in new_tracks:
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(xa), mm(ya))); t.SetEnd(pcbnew.VECTOR2I(mm(xb), mm(yb)))
    t.SetWidth(mm(w)); t.SetLayer(pcbnew.F_Cu if L == F else pcbnew.B_Cu); t.SetNet(b.FindNet(net)); b.Add(t)
for vx, vy, net in new_vias:
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
    v.SetNet(b.FindNet(net)); b.Add(v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PATH)
print(f'routed {done} connections, {len(new_tracks)} tracks, {len(new_vias)} vias, failed {len(failed)}')
for f_ in failed: print('  failed', f_)
