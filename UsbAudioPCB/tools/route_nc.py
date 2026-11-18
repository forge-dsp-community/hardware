# Negotiated-congestion router (PathFinder) on top of route.py's grid and rules.
# Pads, fanout and board edge are hard obstacles; routed copper of other nets is a soft cost that
# grows every iteration (present + history), until no track lies within the clearance of another
# net. Result written into the board.
#   /usr/bin/python3 tools/route_nc.py UsbAudioPCB.kicad_pcb [iterations]
import sys, os, math, heapq, time
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'route.py')).read()
exec(src[:src.index('# ---- order')])          # grid, rules, static obstacles, helpers

ITER = int(sys.argv[2]) if len(sys.argv) > 2 else 25
NC = NX * NY
use_t = [[0] * NC for _ in (F, B)]               # inflated copper of routed nets (track clearance)
use_v = [[0] * NC for _ in (F, B)]               # same, inflated for via placement
hist_t = [[0.0] * NC for _ in (F, B)]
hist_v = [0.0] * NC
footprint = {}                                   # net -> (list of (L, k) for use_t, list for use_v)
routes = {}                                      # net -> (tracks, vias, failed list)

def cells_of_seg(xa, ya, xb, yb, r):
    out = []
    i0, j0 = cell(min(xa, xb) - r, min(ya, yb) - r); i1, j1 = cell(max(xa, xb) + r, max(ya, yb) + r)
    dx, dy = xb - xa, yb - ya; L2 = dx * dx + dy * dy
    for j in range(max(0, j0), min(NY, j1 + 1)):
        y = Y0 + j * G
        for i in range(max(0, i0), min(NX, i1 + 1)):
            x = X0 + i * G
            t = 0 if L2 == 0 else max(0, min(1, ((x - xa) * dx + (y - ya) * dy) / L2))
            if (x - xa - t * dx) ** 2 + (y - ya - t * dy) ** 2 <= r * r: out.append(idx(i, j))
    return out

def place(net, tracks, vias, sign):
    ft, fv = [], []
    for xa, ya, xb, yb, w, L in tracks:
        ft += [(L, k) for k in cells_of_seg(xa, ya, xb, yb, w / 2 + INF_T)]
        fv += [(L, k) for k in cells_of_seg(xa, ya, xb, yb, w / 2 + INF_V)]
    for vx, vy in vias:
        for L in (F, B):
            ft += [(L, k) for k in cells_of_seg(vx, vy, vx, vy, VIA_D / 2 + INF_T)]
            fv += [(L, k) for k in cells_of_seg(vx, vy, vx, vy, VIA_D / 2 + INF_V)]
    ft, fv = set(ft), set(fv)
    for L, k in ft: use_t[L][k] += sign
    for L, k in fv: use_v[L][k] += sign

PF = [0.5]
def astar_nc(nid, starts, targets, extra, attract=None):
    tl = list(targets)
    tx = sum(t[0] for t in tl) / len(tl); ty = sum(t[1] for t in tl) / len(tl)
    def h(i, j):
        dx, dy = abs(i - tx), abs(j - ty)
        return (max(dx, dy) + 0.414 * min(dx, dy)) * 0.98
    pf = PF[0]
    openq, best, prev = [], {}, {}
    for (i, j, L) in starts:
        s = (i, j, L, -1); best[s] = 0; heapq.heappush(openq, (h(i, j), 0, s))
    def cellcost(i, j, L):
        if not (0 <= i < NX and 0 <= j < NY): return None
        k = idx(i, j)
        if (i, j, L) in targets: return 1.0
        if not free_t(L, k, nid): return None
        u = use_t[L][k]; hc = hist_t[L][k]
        for di, dj in extra:
            ii, jj = i + di, j + dj
            if not (0 <= ii < NX and 0 <= jj < NY) or not free_t(L, idx(ii, jj), nid): return None
            kk = idx(ii, jj); u = max(u, use_t[L][kk]); hc = max(hc, hist_t[L][kk])
        return (1.0 + hc) * (1.0 + pf * u)
    n = 0
    while openq:
        f_, g, s = heapq.heappop(openq)
        if best.get(s, 1e18) < g: continue
        i, j, L, d = s
        if (i, j, L) in targets:
            path = [s]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path[::-1]
        n += 1
        if n > 1500000: return None
        for nd, (di, dj) in enumerate(DIRS):
            ii, jj = i + di, j + dj
            cc = cellcost(ii, jj, L)
            if cc is None: continue
            if di and dj and (cellcost(i + di, j, L) is None or cellcost(i, j + dj, L) is None): continue
            if di and dj: c = DIAG
            elif (L == F and dj) or (L == B and di): c = OFFDIR
            else: c = 1.0
            if d >= 0 and nd != d:
                turn = min((nd - d) % 8, (d - nd) % 8)
                c += BEND45 if turn == 1 else BEND90 if turn == 2 else 50
            if attract is not None and (ii, jj, L) in attract: c *= 0.55
            c *= cc
            ns = (ii, jj, L, nd); ng = g + c
            if ng < best.get(ns, 1e18):
                best[ns] = ng; prev[ns] = s; heapq.heappush(openq, (ng + h(ii, jj), ng, ns))
        k = idx(i, j)
        if free_v(k, nid):
            uv = max(use_v[F][k], use_v[B][k])
            ns = (i, j, 1 - L, -1); ng = g + VIA_COST * (1.0 + hist_v[k]) * (1.0 + pf * uv)
            if ng < best.get(ns, 1e18):
                best[ns] = ng; prev[ns] = s; heapq.heappush(openq, (ng + h(i, j), ng, ns))
    return None

def path_geometry(path, w):
    """grid path -> (tracks [(xa,ya,xb,yb,w,L)], vias [(x,y)], centre cells [(L,k)], via cells [k])"""
    pts = [(pos(i, j), L, idx(i, j)) for i, j, L, d in path]
    tracks, vias, cells, vcells = [], [], [], []
    seg_start = 0
    for k_ in range(1, len(pts) + 1):
        if k_ == len(pts) or pts[k_][1] != pts[k_ - 1][1]:
            run = [p for p, L, kk in pts[seg_start:k_]]; L = pts[seg_start][1]
            cells += [(L, kk) for p, LL, kk in pts[seg_start:k_]]
            poly = [run[0]]
            for q in range(1, len(run) - 1):
                ax, ay = poly[-1]; bx, by = run[q]; cx, cy = run[q + 1]
                if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9: poly.append(run[q])
            if len(run) > 1: poly.append(run[-1])
            for (xa, ya), (xb, yb) in zip(poly, poly[1:]): tracks.append((xa, ya, xb, yb, w, L))
            if k_ < len(pts):
                (vx, vy), _, kk = pts[k_ - 1]; vias.append((vx, vy)); vcells.append(kk)
            seg_start = k_
    return tracks, vias, cells, vcells

def route_net(net):
    """route all connections of a net with the current costs; returns tracks, vias, centre cells, via cells, failed"""
    pads = pads_of.get(net, [])
    nid = NID[net]; w = width(net)
    extra = ring(max(0.0, (w - 0.15) / 2)) if w > 0.16 else []
    tracks, vias, cells, vcells, failed = [], [], [], [], []
    def tree_cells():
        out = set()
        for xa, ya, xb, yb, ww, L in tracks:
            n = max(1, int(math.hypot(xb - xa, yb - ya) / G))
            for q in range(n + 1):
                i, j = cell(xa + (xb - xa) * q / n, ya + (yb - ya) * q / n); out.add((i, j, L))
        for vx, vy in vias:
            i, j = cell(vx, vy); out |= {(i, j, F), (i, j, B)}
        return out
    attract = PAIR.get(net)
    if net in PLANE:
        base_cells = copper_cells(net)
        for name, x, y, layers, rect, p in [pd for pd in pads if not pad_has_copper(pd[5])]:
            pc = pad_cells(rect, layers)
            tgt = (base_cells | tree_cells()) - pc
            path = astar_nc(nid, pc, tgt, extra)
            if path is None: failed.append(f'{net}:{name}'); continue
            t_, v_, c_, vc_ = path_geometry(path, w); tracks += t_; vias += v_; cells += c_; vcells += vc_
        return tracks, vias, cells, vcells, failed
    if len(pads) < 2: return tracks, vias, cells, vcells, failed
    remaining = pads[1:]
    tree = pad_cells(pads[0][4], pads[0][3]) | copper_cells(net)
    while remaining:
        tl = list(tree)[:300]
        remaining.sort(key=lambda pd: min(abs(pd[1] - pos(i, j)[0]) + abs(pd[2] - pos(i, j)[1]) for i, j, L in tl))
        name, x, y, layers, rect, p = remaining.pop(0)
        tgt = pad_cells(rect, layers)
        path = astar_nc(nid, tree, tgt, extra, attract)
        if path is None: failed.append(f'{net}:{name}'); continue
        t_, v_, c_, vc_ = path_geometry(path, w); tracks += t_; vias += v_; cells += c_; vcells += vc_
        tree |= tgt | tree_cells()
    return tracks, vias, cells, vcells, failed

PAIR = {}
def pair_cells_of(tracks, w):
    out = set(); k = int(round((w + 0.15) / G))
    for xa, ya, xb, yb, ww, L in tracks:
        n = max(1, int(math.hypot(xb - xa, yb - ya) / G))
        for q in range(n + 1):
            i, j = cell(xa + (xb - xa) * q / n, ya + (yb - ya) * q / n)
            for di, dj in ring(k * G + 0.05):
                if abs(math.hypot(di, dj) - k) < 0.75: out.add((i + di, j + dj, L))
    return out

ORDER = ['USB.1.DP', 'USB.1.DM', 'COM.D+', 'COM.D-', 'XMOS.MCLK', 'MCLK.22M', 'MCLK.24M', 'XMOS.CLK', 'XMOS.CLK.OSC',
         'I2S.BCLK.X', 'I2S.LRCK.X', 'I2S.SDATA.X', 'SPDIF.X', 'IN.I2S.BCLK.0', 'IN.I2S.LRCK.0', 'IN.I2S.SDATA.0', 'IN.SPDIF.1']
order = ORDER + sorted(n for n in nets if n not in ORDER and n not in PLANE and len(pads_of.get(n, [])) >= 2) + sorted(PLANE)
OUT = sys.argv[3] if len(sys.argv) > 3 else PATH
PF_MAX, STALL = 400.0, 10

def write_board(sol):
    bb = pcbnew.LoadBoard(PATH)
    for net, (tr, vi, fa) in sol.items():
        for xa, ya, xb, yb, w, L in tr:
            t = pcbnew.PCB_TRACK(bb); t.SetStart(pcbnew.VECTOR2I(mm(xa), mm(ya))); t.SetEnd(pcbnew.VECTOR2I(mm(xb), mm(yb)))
            t.SetWidth(mm(w)); t.SetLayer(pcbnew.F_Cu if L == F else pcbnew.B_Cu); t.SetNet(bb.FindNet(net)); bb.Add(t)
        for vx, vy in vi:
            v = pcbnew.PCB_VIA(bb); v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
            v.SetNet(bb.FindNet(net)); bb.Add(v)
    pcbnew.ZONE_FILLER(bb).Fill(bb.Zones())
    bb.Save(OUT)

t_start = time.time()
best = None; best_score = None; since = 0
bad_nets = set(order)
for it in range(ITER):
    # first iterations: everything; later only the nets in conflict (history keeps the pressure)
    for net in (order if it < 6 else [n for n in order if n in bad_nets or routes[n][4]]):
        if net in routes:
            tr, vi, ce, vc, fa = routes[net]
            place(net, tr, vi, -1)
        tr, vi, ce, vc, fa = route_net(net)
        routes[net] = (tr, vi, ce, vc, fa)
        place(net, tr, vi, +1)
        if net in ('USB.1.DP', 'COM.D+'):
            PAIR['USB.1.DM' if net == 'USB.1.DP' else 'COM.D-'] = pair_cells_of(tr, width(net))
    # conflicts: centre cells of a net inside the inflated copper of another net
    conflicts = 0; bad_nets = set(); spots = {}
    for net, (tr, vi, ce, vc, fa) in routes.items():
        place(net, tr, vi, -1)
        for L, k in ce:
            if use_t[L][k] > 0:
                conflicts += 1; hist_t[L][k] += 0.6; bad_nets.add(net)
                x, y = pos(k % NX, k // NX); spots.setdefault((round(x - 100), round(y - 100), 'FB'[L]), set()).add(net)
        for k in vc:
            if use_v[F][k] > 0 or use_v[B][k] > 0:
                conflicts += 1; hist_v[k] += 0.6; bad_nets.add(net)
                x, y = pos(k % NX, k // NX); spots.setdefault((round(x - 100), round(y - 100), 'V'), set()).add(net)
        place(net, tr, vi, +1)
    nfail = sum(len(r[4]) for r in routes.values())
    print(f'iteration {it}: conflicts {conflicts} in {len(bad_nets)} nets, failed {nfail}, pf {PF[0]:.2f}, {time.time() - t_start:.0f}s', flush=True)
    print('   spots', '; '.join(f'{x},{y}{L}:{"/".join(sorted(n))}' for (x, y, L), n in sorted(spots.items())), flush=True)
    score = (conflicts > 0, nfail + conflicts, conflicts)
    if best_score is None or score < best_score:
        best_score = score; since = 0
        best = (nfail, {n: (r[0], r[1], r[4]) for n, r in routes.items()})
        write_board(best[1]); print(f'   saved best: failed {nfail}, conflicts {conflicts}', flush=True)
    else:
        since += 1
    if conflicts == 0 and nfail == 0: break
    if since >= STALL: print('stalled'); break
    PF[0] = min(PF_MAX, PF[0] * 1.7)

fails = [f for r in best[1].values() for f in r[2]]
print(f'written: failed {len(fails)}, score {best_score}')
for f_ in fails: print('  failed', f_)
