# Fanout of the plane nets: every SMD pad on GND / +3V3 / XMOS.3V3 / XMOS.1V0 gets a short stub and a
# via into the plane (In1 GND, In2 split). The via must lie inside the In2 zone of its net (GND: anywhere
# on the board) and keep clearance to copper of other nets on F and B. Same-net neighbours share a via.
# XMOS: 1.0 V pins get their via inside the pad rows (under the chip), the others outside.
#   /usr/bin/python3 tools/fanout.py UsbAudioPCB.kicad_pcb
import sys, math
import pcbnew

PATH = sys.argv[1] if len(sys.argv) > 1 else 'UsbAudioPCB.kicad_pcb'
b = pcbnew.LoadBoard(PATH)
mm, T = pcbnew.FromMM, pcbnew.ToMM
PLANE = {'GND', '+3V3', 'XMOS.3V3', 'XMOS.1V0'}
VIA_D, VIA_DRILL, CLR, EDGE = 0.5, 0.25, 0.16, 0.45
STUB_W = {'GND': 0.3, '+3V3': 0.3, 'XMOS.3V3': 0.3, 'XMOS.1V0': 0.3}

outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)
zones = {}
for z in b.Zones():
    if z.GetIsRuleArea() or z.GetLayer() != pcbnew.In2_Cu: continue
    zones.setdefault(z.GetNetname(), []).append(z.Outline())

# obstacles: pads (bbox, net, layers F/B), vias, tracks
obst = []      # (kind, net, onF, onB, geometry)
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        onF = p.IsOnLayer(pcbnew.F_Cu); onB = p.IsOnLayer(pcbnew.B_Cu)
        obst.append(('rect', p.GetNetname(), onF, onB, (T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()))))
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        obst.append(('circ', t.GetNetname(), True, True, (T(t.GetPosition().x), T(t.GetPosition().y), T(t.GetWidth(pcbnew.F_Cu)) / 2)))
    else:
        obst.append(('seg', t.GetNetname(), t.GetLayer() == pcbnew.F_Cu, t.GetLayer() == pcbnew.B_Cu,
                     (T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y), T(t.GetWidth()) / 2)))

def d_rect(x, y, r):
    x0, y0, x1, y1 = r
    dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
    return math.hypot(dx, dy)
def d_seg(px, py, s):
    x1, y1, x2, y2, w = s
    dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy) - w
def free_circle(x, y, rad, net, onF=True, onB=True):
    for kind, n, f, bb, g in obst:
        if n == net or not ((onF and f) or (onB and bb)): continue
        d = d_rect(x, y, g) if kind == 'rect' else (math.hypot(x - g[0], y - g[1]) - g[2]) if kind == 'circ' else d_seg(x, y, g)
        if d < rad + CLR: return False
    return True
def seg_free(x1, y1, x2, y2, w, net, onF, onB, skip_rect=None):
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 0.05))
    for i in range(n + 1):
        t = i / n
        x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        if not free_circle(x, y, w / 2, net, onF, onB): return False
        if skip_rect and skip_rect[0] <= x <= skip_rect[2] and skip_rect[1] <= y <= skip_rect[3]: continue   # on the pad itself
        if not in_board(x, y, w / 2 + 0.32): return False
    return True
def in_board(x, y, margin):
    for a in range(0, 360, 45):
        if not outline.Contains(pcbnew.VECTOR2I(mm(x + margin * math.cos(math.radians(a))), mm(y + margin * math.sin(math.radians(a))))):
            return False
    return True
def in_zone(x, y, net, margin=0.45):
    if net == 'GND': return True
    for o in zones.get(net, []):
        if all(o.Contains(pcbnew.VECTOR2I(mm(x + margin * math.cos(math.radians(a))), mm(y + margin * math.sin(math.radians(a)))))
               for a in range(0, 360, 45)):
            return True
    return False

added = {'via': 0, 'track': 0}
vias = []   # (x, y, net)
def add_via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
    v.SetNet(b.FindNet(net)); b.Add(v)
    obst.append(('circ', net, True, True, (x, y, VIA_D / 2))); vias.append((x, y, net)); added['via'] += 1
def add_track(x1, y1, x2, y2, w, net, layer):
    if math.hypot(x2 - x1, y2 - y1) < 1e-3: return
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)
    obst.append(('seg', net, layer == pcbnew.F_Cu, layer == pcbnew.B_Cu, (x1, y1, x2, y2, w / 2))); added['track'] += 1

xmos = b.FindFootprintByReference('IC114')
XC = (T(xmos.GetPosition().x), T(xmos.GetPosition().y))
todo, failed = [], []
for fp in b.GetFootprints():
    for p in fp.Pads():
        net = p.GetNetname()
        if net not in PLANE or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
        if fp.GetReference() == 'IC114' and p.GetNumber() == '65': continue     # exposed pad has its own vias
        todo.append((fp, p, net))
# XMOS first (tightest), then by pad count of the footprint (ICs before passives)
todo.sort(key=lambda a: (a[0].GetReference() != 'IC114', -len(a[0].Pads())))

# exposed pads without vias (QFN of the CP2102): a 2x2 via grid in the pad
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() != 'GND' or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
        bb = p.GetBoundingBox()
        if T(bb.GetWidth()) < 2.5 or T(bb.GetHeight()) < 2.5 or fp.GetReference() == 'IC114': continue
        if any(t.Type() == pcbnew.PCB_VIA_T and p.HitTest(t.GetPosition()) for t in b.GetTracks()): continue
        cx, cy = T(p.GetPosition().x), T(p.GetPosition().y)
        for dx in (-0.6, 0.6):
            for dy in (-0.6, 0.6): add_via(cx + dx, cy + dy, 'GND')
def ep_of(fp, net):
    for q in fp.Pads():
        bb = q.GetBoundingBox()
        if q.GetNetname() == net and T(bb.GetWidth()) >= 2.5 and T(bb.GetHeight()) >= 2.5: return q
    return None

for fp, p, net in todo:
    ep = ep_of(fp, net) if fp.GetReference() != 'IC114' else None
    if ep is not None and ep.GetNumber() != p.GetNumber():
        # pin on the net of the exposed pad: along the pin axis into the pad, if the pin faces it
        px, py = T(p.GetPosition().x), T(p.GetPosition().y)
        eb = ep.GetBoundingBox(); ex0, ey0, ex1, ey1 = T(eb.GetLeft()), T(eb.GetTop()), T(eb.GetRight()), T(eb.GetBottom())
        pb = p.GetBoundingBox(); horiz = pb.GetWidth() > pb.GetHeight()
        lay = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
        if horiz and ey0 + 0.15 < py < ey1 - 0.15:
            add_track(px, py, (ex0 + 0.2) if px < ex0 else (ex1 - 0.2), py, 0.25, net, lay); continue
        if not horiz and ex0 + 0.15 < px < ex1 - 0.15:
            add_track(px, py, px, (ey0 + 0.2) if py < ey0 else (ey1 - 0.2), 0.25, net, lay); continue
        failed.append(f'{fp.GetReference()}.{p.GetNumber()} ({net}, beside the exposed pad)'); continue
    if ep is not None: continue
    layer = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
    onF, onB = layer == pcbnew.F_Cu, layer == pcbnew.B_Cu
    px, py = T(p.GetPosition().x), T(p.GetPosition().y)
    bb = p.GetBoundingBox(); hw, hh = T(bb.GetWidth()) / 2, T(bb.GetHeight()) / 2
    w = STUB_W[net]
    # existing same-net via close by (shared fanout)
    near = [(math.hypot(vx - px, vy - py), vx, vy) for vx, vy, n in vias if n == net]
    near.sort()
    done = False
    for d, vx, vy in near[:3]:
        if d < 1.6 and seg_free(px, py, vx, vy, w, net, onF, onB, (px - hw, py - hh, px + hw, py + hh)):
            add_track(px, py, vx, vy, w, net, layer); done = True; break
    if done: continue
    # candidate directions
    cx, cy = (XC if fp.GetReference() == 'IC114' else (T(fp.GetPosition().x), T(fp.GetPosition().y)))
    ox, oy = px - cx, py - cy
    if fp.GetReference() == 'IC114':
        # along the pin axis: outward, 1.0 V inward
        if abs(ox) > abs(oy): ox, oy = (1 if ox > 0 else -1), 0
        else: ox, oy = 0, (1 if oy > 0 else -1)
        if net == 'XMOS.1V0': ox, oy = -ox, -oy
        if net == 'XMOS.1V0': dirs = [(ox, oy)]
        else: dirs = [(ox, oy), (ox + oy * 0.7, oy + ox * 0.7), (ox - oy * 0.7, oy - ox * 0.7)]
        dists = [0.45, 0.6, 0.8] if net == 'XMOS.1V0' else [0.45, 0.6, 0.8, 1.0]
    else:
        L = math.hypot(ox, oy) or 1
        base = math.atan2(oy, ox)
        dirs = [(math.cos(base + math.radians(a)), math.sin(base + math.radians(a))) for a in (0, 45, -45, 90, -90, 135, -135, 180)]
        dists = [0.45, 0.6, 0.8, 1.0, 1.3]
    best = None
    for dx, dy in dirs:
        ext = abs(dx) * hw + abs(dy) * hh            # from the pad centre to its edge along the direction
        for dd in dists:
            if fp.GetReference() != 'IC114':
                r = ext + dd; vx, vy = px + dx * r, py + dy * r
            else:   # from the pad tip along the pin axis, diagonals offset sideways
                ax, ay = (1 if dx > 0.5 else -1 if dx < -0.5 else 0), (1 if dy > 0.5 else -1 if dy < -0.5 else 0)
                tip = hw if ax else hh
                vx, vy = px + ax * (tip + dd) + (dx - ax) * 0.7 * dd, py + ay * (tip + dd) + (dy - ay) * 0.7 * dd
            if not in_board(vx, vy, VIA_D / 2 + 0.35) or not in_zone(vx, vy, net): continue
            if not free_circle(vx, vy, VIA_D / 2, net): continue
            if not seg_free(px, py, vx, vy, w, net, onF, onB, (px - hw, py - hh, px + hw, py + hh)): continue
            best = (vx, vy); break
        if best: break
    if not best:
        failed.append(f'{fp.GetReference()}.{p.GetNumber()} ({net})'); continue
    add_track(px, py, best[0], best[1], w, net, layer); add_via(best[0], best[1], net)

b.Save(PATH)
print('fanout:', added, 'failed:', len(failed))
for f in failed: print('  no via for', f)
