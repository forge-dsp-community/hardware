# Hand fixes after route_nc.py on this placement (coordinates belong to that routing run): KiCad DRC left
# 3 errors and 1 open pad, all local. COM.D- stub on the pad centre, USB.1.DM 0.04 mm away from IC114.27,
# IC114.55 (XMOS.3V3) via to the In2 plane with POR moved to an inner via and BCLK 0.2 mm south,
# POR hops to B between EXT.USB.RX and TX where it crossed XMOS.3V3.PG.
#   /usr/bin/python3 tools/fix_route.py routed.kicad_pcb fixed.kicad_pcb []   (third arg: JSON list of nets to rip)
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); mm = lambda v: pcbnew.FromMM(v + 100); T = lambda v: pcbnew.ToMM(v) - 100
RIP = set(json.load(open(sys.argv[3]))); TR = list(b.GetTracks()); GONE = []
def seg(net, L, a, c):
    for t in TR:
        if t in GONE: continue
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() != net or t.GetLayerName() != L: continue
        p = [(round(T(t.GetStart().x), 2), round(T(t.GetStart().y), 2)), (round(T(t.GetEnd().x), 2), round(T(t.GetEnd().y), 2))]
        if sorted(p) == sorted([a, c]): GONE.append(t); return
    raise SystemExit(f'not found {net} {a} {c}')
def add(net, L, pts, w):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
        t.SetWidth(pcbnew.FromMM(w)); t.SetLayer(b.GetLayerID(L)); t.SetNet(b.FindNet(net)); b.Add(t)
def via(net, x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(pcbnew.FromMM(0.5)); v.SetDrill(pcbnew.FromMM(0.3))
    v.SetNet(b.FindNet(net)); b.Add(v)
# 1 COM.D-: stub on pad centre
seg('COM.D-', 'B.Cu', (45.6, 5.1), (45.6, 4.8)); seg('COM.D-', 'B.Cu', (47.4, 6.9), (45.6, 5.1))
add('COM.D-', 'B.Cu', [(45.428, 4.13), (45.428, 5.3), (47.028, 6.9), (47.4, 6.9)], 0.25)
# 3 USB.1.DM: vertical 0.04 mm further from IC114
seg('USB.1.DM', 'B.Cu', (20.5, 16.0), (20.6, 16.1)); seg('USB.1.DM', 'B.Cu', (20.6, 16.1), (20.6, 19.4)); seg('USB.1.DM', 'B.Cu', (20.6, 19.4), (20.3, 19.7))
add('USB.1.DM', 'B.Cu', [(20.5, 16.0), (20.64, 16.14), (20.64, 19.36), (20.3, 19.7)], 0.25)
# 4 IC114.55 XMOS.3V3 to plane
add('XMOS.3V3', 'B.Cu', [(8.186, 16.041), (7.2, 16.041), (6.6, 15.441)], 0.3); via('XMOS.3V3', 6.6, 15.441)
# POR at IC114: inner via instead of the outer one, F joins the old route at (9.0,16.0)
for a, c, L in [((7.4,15.0),(7.2,15.0),'B.Cu'), ((7.2,15.0),(7.0,15.2),'B.Cu'), ((8.0,15.2),(7.0,15.2),'F.Cu'), ((8.8,16.0),(8.0,15.2),'F.Cu'), ((9.0,16.0),(8.8,16.0),'F.Cu')]:
    seg('XMOS.POR', L, a, c)
for v in TR:
    if v.Type() == pcbnew.PCB_VIA_T and v.GetNetname() == 'XMOS.POR' and abs(T(v.GetPosition().x) - 7.0) < .01 and abs(T(v.GetPosition().y) - 15.2) < .01: GONE.append(v)
add('XMOS.POR', 'B.Cu', [(8.186, 15.041), (9.186, 15.041), (9.436, 14.79)], 0.15); via('XMOS.POR', 9.436, 14.79)
add('XMOS.POR', 'F.Cu', [(9.436, 14.79), (8.95, 15.276), (8.95, 15.95), (9.0, 16.0)], 0.15)
# BCLK 0.2 mm south, clear of the 3V3 via
seg('I2S.BCLK.X', 'F.Cu', (8.1, 16.8), (7.1, 15.8)); seg('I2S.BCLK.X', 'F.Cu', (7.1, 15.8), (6.2, 15.8)); seg('I2S.BCLK.X', 'F.Cu', (6.2, 15.8), (4.7, 14.3))
add('I2S.BCLK.X', 'F.Cu', [(8.1, 16.8), (7.3, 16.0), (6.4, 16.0), (4.7, 14.3)], 0.15)
# 2 POR/PG crossing: POR hops to B between RX and TX, PG one diagonal further south-west
for a, c in [((40.8,20.0),(39.9,20.9)), ((39.9,20.9),(39.9,21.1)), ((39.9,21.1),(40.0,21.2)), ((40.0,21.2),(40.0,21.3))]: seg('XMOS.POR', 'F.Cu', a, c)
add('XMOS.POR', 'F.Cu', [(40.8, 20.0), (40.8, 20.4), (40.6, 20.6)], 0.15); via('XMOS.POR', 40.6, 20.6)
add('XMOS.POR', 'B.Cu', [(40.6, 20.6), (39.9, 21.3)], 0.15); via('XMOS.POR', 39.9, 21.3)
add('XMOS.POR', 'F.Cu', [(39.9, 21.3), (40.0, 21.3)], 0.15)
for a, c in [((39.6,20.1),(39.6,20.0)), ((40.4,20.9),(39.6,20.1)), ((40.4,21.2),(40.4,20.9)), ((41.0,21.8),(40.4,21.2)), ((41.1,21.8),(41.0,21.8))]: seg('XMOS.3V3.PG', 'F.Cu', a, c)
add('XMOS.3V3.PG', 'F.Cu', [(39.6, 20.0), (39.6, 20.3), (41.1, 21.8)], 0.15)
GONE += [t for t in TR if t.GetNetname() in RIP and t not in GONE]
for t in GONE: b.Remove(t)
b.Save(sys.argv[2])
