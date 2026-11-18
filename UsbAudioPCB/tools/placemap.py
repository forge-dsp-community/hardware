# Draw a placement map (courtyard boxes with references) of one side into a PNG.
#   /usr/bin/python3 tools/placemap.py B out.json  (dump), then venv python tools/placemap.py draw out.json out.png
import sys, json
if sys.argv[1] != 'draw':
    import pcbnew
    side = sys.argv[1]; b = pcbnew.LoadBoard('UsbAudioPCB.kicad_pcb'); T = lambda v: pcbnew.ToMM(v) - 100
    out = {'boxes': [], 'tht': [], 'edge': []}
    for fp in b.GetFootprints():
        s = 'B' if fp.IsFlipped() else 'F'
        for p in fp.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                bb = p.GetBoundingBox(); out['tht'].append([T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())])
        if s != side: continue
        bb = fp.GetCourtyard(pcbnew.B_CrtYd if s == 'B' else pcbnew.F_CrtYd).BBox()
        out['boxes'].append([fp.GetReference(), T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())])
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            out['edge'].append([T(d.GetStart().x), T(d.GetStart().y), T(d.GetEnd().x), T(d.GetEnd().y)])
    json.dump(out, open(sys.argv[2], 'w'))
else:
    from PIL import Image, ImageDraw, ImageFont
    d = json.load(open(sys.argv[2])); K = 24
    im = Image.new('RGB', (int(66 * K), int(40 * K)), 'white'); g = ImageDraw.Draw(im)
    f = ImageFont.load_default(size=11)
    for x in range(0, 66): g.line([(x * K, 0), (x * K, 40 * K)], fill=(235, 235, 235) if x % 5 else (200, 200, 200))
    for y in range(0, 40): g.line([(0, y * K), (66 * K, y * K)], fill=(235, 235, 235) if y % 5 else (200, 200, 200))
    for x1, y1, x2, y2 in d['edge']: g.line([(x1 * K, y1 * K), (x2 * K, y2 * K)], fill='black', width=2)
    for x0, y0, x1, y1 in d['tht']: g.ellipse([x0 * K, y0 * K, x1 * K, y1 * K], outline='orange', width=2)
    for r, x0, y0, x1, y1 in d['boxes']:
        g.rectangle([x0 * K, y0 * K, x1 * K, y1 * K], outline='blue')
        g.text(((x0 + x1) / 2 * K, (y0 + y1) / 2 * K), r, fill='red', font=f, anchor='mm')
    for v in range(0, 66, 5): g.text((v * K + 2, 2), str(v), fill='gray', font=f)
    for v in range(0, 40, 5): g.text((2, v * K + 2), str(v), fill='gray', font=f)
    im.save(sys.argv[3])
