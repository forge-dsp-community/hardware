# Generate UsbAudioPCB.kicad_pcb: outline and the positions of the mechanical parts from the
# 300 dpi Eagle exports of the original (USB_AUDIO-PADS/TPLACE/BPLACE.png), footprints from the
# KiCad library with the nets of parts.py. Board-local coordinates in mm (origin = top left
# corner of the bounding box, y down), shifted by ORIGIN.
#   /usr/bin/python3 tools/gen_pcb.py [placement.py]
import os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import pcbnew
from parts import P

PROJ = 'UsbAudioPCB'
FPLIB = '/usr/share/kicad/footprints'
ORIGIN = (100.0, 100.0)
SX, SY = 63.5 / 749, 38.1 / 451          # px -> mm (outline 2500 x 1500 mil)
def px(x, y): return ((x - 4) * SX, (y - 9) * SY)
mm = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))

# outline in mil (Eagle grid of the original), clockwise from the lower left
MIL = 0.0254
OUTLINE = [(0, 1070), (100, 1070), (100, 160), (900, 160), (900, 0), (1480, 0), (1480, 60), (1495, 66), (1615, 66),
           (1630, 60), (1630, 0), (1965, 0), (1965, 160), (2500, 160), (2500, 650), (1870, 650), (1770, 750),
           (1770, 1500), (0, 1500)]

from placement import PLACE, KEEPOUT_B      # ref -> (x, y, rot, side) in board mm

b = pcbnew.CreateEmptyBoard()
b.SetCopperLayerCount(4)
b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER); b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
pts = [(x * MIL, y * MIL) for x, y in OUTLINE]
def seg(a, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(mm(0.05)); s.SetStart(V(*a)); s.SetEnd(V(*c)); b.Add(s)
def arc(a, m, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(mm(0.05)); s.SetArcGeometry(V(*a), V(*m), V(*c)); b.Add(s)
# PORT: cut-out open to the bottom edge above X-PDI of the base board, so a 2x3 Dupont plug
# fits on the header with this board mounted (housing ~7.6 x 5.1 mm around 22.42/35.31)
NX0, NX1, NY, R = 18.1, 26.7, 32.5, 0.5
k = math.sqrt(0.5) * R
for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
    if y1 == y2 == 1500 * MIL and x1 > NX1 and x2 < NX0:          # bottom edge, right to left
        seg((x1, y1), (NX1, y1)); seg((NX1, y1), (NX1, NY + R))
        arc((NX1, NY + R), (NX1 - R + k, NY + R - k), (NX1 - R, NY))
        seg((NX1 - R, NY), (NX0 + R, NY))
        arc((NX0 + R, NY), (NX0 + R - k, NY + R - k), (NX0, NY + R))
        seg((NX0, NY + R), (NX0, y1)); seg((NX0, y1), (x2, y2))
    else:
        seg((x1, y1), (x2, y2))

# rule area above X-PDI of the base board: no footprints on the bottom side
ka = pcbnew.ZONE(b); ka.SetIsRuleArea(True); ka.SetLayer(pcbnew.B_Cu)
ka.SetDoNotAllowFootprints(True); ka.SetDoNotAllowTracks(False); ka.SetDoNotAllowVias(False)
ka.SetDoNotAllowPads(False); ka.SetDoNotAllowZoneFills(False); ka.SetZoneName('X-PDI Mainboard')
x0, y0, x1, y1 = KEEPOUT_B
for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): ka.AppendCorner(V(x, y), -1)
b.Add(ka)

nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n); nets[name] = n
    return nets[name]

missing = []
for p in P:
    lib, name = p['fp'].split(':')
    path = f'{FPLIB}/{lib}.pretty' if lib != PROJ else os.path.abspath(f'{PROJ}.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None: raise SystemExit('footprint not found: ' + p['fp'])
    fp = pcbnew.FOOTPRINT(fp)          # FootprintLoad hands out the cached instance
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(p['ref']); fp.SetValue(p['val'])
    if p['lcsc']: fp.SetField('LCSC', p['lcsc'])
    b.Add(fp)
    for pad in fp.Pads():
        n = pad.GetNumber()
        if not n: continue
        nn = p['pins'].get(n)
        if nn is None and n not in ('SH', 'MP'):
            raise SystemExit(f'{p["ref"]}: pad {n} not in netlist')
        if nn: pad.SetNet(net(nn))
        else: pad.SetNet(net(f'unconnected-({p["ref"]}-Pad{n})'))
    if p['ref'] not in PLACE:
        missing.append(p['ref']); continue
    x, y, rot, side = PLACE[p['ref']]
    fp.SetPosition(V(x, y))
    if side == 'B': fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
if missing: print('not placed:', ' '.join(missing))

# ---- legalize: push movable parts out of overlaps (courtyard boxes per side, THT pads on the other side)
KO = [mm(ORIGIN[0] + KEEPOUT_B[0]), mm(ORIGIN[1] + KEEPOUT_B[1]), mm(ORIGIN[0] + KEEPOUT_B[2]), mm(ORIGIN[1] + KEEPOUT_B[3])]
FIXED = {'X101', 'X102', 'X103', 'X104', 'X105', 'X106', 'X107', 'SW101', 'IC114', 'IC101'}
GAP = mm(0.05)
outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
def boxes(fp):
    side = 'B' if fp.IsFlipped() else 'F'
    out = []
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)
    if cy.OutlineCount():
        bb = cy.BBox(); out.append((side, bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
    for p in fp.Pads():
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            bb = p.GetBoundingBox(); bb.Inflate(mm(0.2))
            out.append(('F' if side == 'B' else 'B', bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
    return out
def inside(fp):
    side = 'B' if fp.IsFlipped() else 'F'
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)
    bb = cy.BBox()
    return all(outline.Contains(pcbnew.VECTOR2I(x, y)) for x, y in
               ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetLeft(), bb.GetBottom()), (bb.GetRight(), bb.GetBottom())))
IGNORE = {frozenset(('X103', 'X102')), frozenset(('X105', 'SW101'))}   # bodies touch by design (as the original)
for it in range(400):
    moved = 0; lastm = []
    refs = sorted(fps)
    bx = {r: boxes(fps[r]) for r in refs}
    for i, ra in enumerate(refs):
        for rb in refs[i + 1:]:
            if frozenset((ra, rb)) in IGNORE: continue
            if ra in FIXED and rb in FIXED: continue
            for sa, ax0, ay0, ax1, ay1 in bx[ra]:
                for sb, bx0, by0, bx1, by1 in bx[rb]:
                    if sa != sb: continue
                    ox = min(ax1, bx1) - max(ax0, bx0) + GAP; oy = min(ay1, by1) - max(ay0, by0) + GAP
                    if ox <= 0 or oy <= 0: continue
                    mv = rb if ra in FIXED else ra if rb in FIXED else max(ra, rb)   # deterministic
                    other = ra if mv == rb else rb
                    sgnx = 1 if (fps[mv].GetPosition().x >= fps[other].GetPosition().x) else -1
                    sgny = 1 if (fps[mv].GetPosition().y >= fps[other].GetPosition().y) else -1
                    d = pcbnew.VECTOR2I(sgnx * (ox + 1), 0) if ox < oy else pcbnew.VECTOR2I(0, sgny * (oy + 1))
                    fps[mv].Move(d)
                    if not inside(fps[mv]):
                        fps[mv].Move(pcbnew.VECTOR2I(-d.x, -d.y))
                        d = pcbnew.VECTOR2I(0, sgny * (oy + 1)) if ox < oy else pcbnew.VECTOR2I(sgnx * (ox + 1), 0)
                        fps[mv].Move(d)
                        if not inside(fps[mv]): fps[mv].Move(pcbnew.VECTOR2I(-d.x, -d.y)); continue
                    moved += 1; lastm.append(mv + '/' + other)
                    bx[mv] = boxes(fps[mv])
    if not moved: break
    last = lastm
print('legalize iterations', it, 'last moves', moved, sorted(set(lastm)))
for r in sorted(fps):
    if r in FIXED or r not in PLACE: continue
    p = fps[r].GetPosition(); x, y = pcbnew.ToMM(p.x) - ORIGIN[0], pcbnew.ToMM(p.y) - ORIGIN[1]
    if abs(x - PLACE[r][0]) > 0.05 or abs(y - PLACE[r][1]) > 0.05: print(f'  moved {r}: {PLACE[r][0]:.2f},{PLACE[r][1]:.2f} -> {x:.2f},{y:.2f}')

# ---- copper zones: In1 GND, In2 split (XMOS.1V0 core + band to the buck converter, XMOS.3V3 ring +
# band to the LDO, +3V3 elsewhere), GND on the outer layers
from placement import ZONES
def polyset(poly):
    ps = pcbnew.SHAPE_POLY_SET(); c = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in poly: c.Append(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))
    c.SetClosed(True); ps.AddOutline(c); return ps
# the zones of one layer are made disjoint (higher priority cut out of lower ones): the Specctra
# export for Freerouting knows no zone priorities
shapes = {}
for name, layer, prio, poly in ZONES:
    ps = polyset(poly)
    for n2, l2, p2, poly2 in ZONES:
        if l2 == layer and p2 > prio: ps.BooleanSubtract(polyset(poly2))
    for i in range(ps.OutlineCount()):
        if ps.HoleCount(i): raise SystemExit(f'zone {name} on {layer} has holes')
    shapes[(name, layer)] = (prio, ps)
for (name, layer), (prio, ps) in shapes.items():
    z = pcbnew.ZONE(b); z.SetLayer(getattr(pcbnew, layer)); z.SetNet(net(name)); z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(0.2)); z.SetMinThickness(mm(0.2)); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.3))
    z.SetOutline(ps)
    b.Add(z)
filler = pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
b.Save(f'{PROJ}.kicad_pcb')
# no model for the ASE oscillator footprint in the KiCad library: same 3225 package as the crystals
t = open(f'{PROJ}.kicad_pcb').read()
t = t.replace('Oscillator.3dshapes/Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm.step', 'Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.step')
# pin headers X101/X104: plastic body on the top side, pins through the board down to the
# base board (model turned over: rotate 180 about y, shifted by one pitch and the board thickness)
import re as _re
t = _re.sub(r'(\(model "[^"]*PinHeader_2x0[26]_P2\.54mm_Vertical\.step"\s*\(offset\s*\(xyz )[^)]*(\)\s*\)\s*\(scale\s*\(xyz [^)]*\)\s*\)\s*\(rotate\s*\(xyz )[^)]*',
            r'\g<1>2.54 0 -1.6\g<2>0 -180 0', t)
open(f'{PROJ}.kicad_pcb', 'w').write(t)
print('saved', len(P), 'footprints')
