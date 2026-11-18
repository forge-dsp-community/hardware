# Courtyard overlaps per side (THT parts count on both sides) and parts outside the outline.
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1] if len(sys.argv) > 1 else 'UsbAudioPCB.kicad_pcb')
mm = pcbnew.ToMM
edge = b.GetBoardEdgesBoundingBox()
outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, False)
items = []
for fp in b.GetFootprints():
    tht = any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in fp.Pads())
    side = 'B' if fp.IsFlipped() else 'F'
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)
    if cy.OutlineCount() == 0: continue
    items.append((fp.GetReference(), side, tht, cy, cy.BBox()))
    if tht:   # on the other side only the through-hole pads count
        ps = pcbnew.SHAPE_POLY_SET()
        for p in fp.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                bb = p.GetBoundingBox(); bb.Inflate(pcbnew.FromMM(0.25))
                x0, y0, x1, y1 = bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()
                c = pcbnew.SHAPE_LINE_CHAIN()
                for xx, yy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): c.Append(xx, yy)
                c.SetClosed(True); ps.AddOutline(c)
        items.append((fp.GetReference() + '*', 'F' if side == 'B' else 'B', False, ps, ps.BBox()))
bad = 0
for i, (ra, sa, ta, ca, ba) in enumerate(items):
    for rb, sb, tb, cb, bb in items[i + 1:]:
        if sa != sb: continue
        if ra.rstrip('*') == rb.rstrip('*'): continue
        if not ba.Intersects(bb): continue
        inter = pcbnew.SHAPE_POLY_SET(ca); inter.BooleanIntersection(cb)
        if inter.Area() > 1e3:   # nm^2
            print(f'overlap {ra}({sa}) {rb}({sb}) {inter.Area() / 1e12:.2f} mm2'); bad += 1
    if not ra.endswith('*') and not outline.Contains(ba.GetCenter()):
        print('outside', ra); bad += 1
print(bad, 'problems')
