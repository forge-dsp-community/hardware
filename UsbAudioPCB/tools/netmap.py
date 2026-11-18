# Review image of the routing: pads, tracks (F red, B blue), vias, net names along the tracks.
#   /usr/bin/python3 tools/netmap.py board.kicad_pcb dump.json   (system python with pcbnew)
#   <venv python with PIL> tools/netmap.py draw dump.json out.png [x0 y0 x1 y1]
import sys, json
if sys.argv[1] != 'draw':
    import pcbnew
    b = pcbnew.LoadBoard(sys.argv[1]); T = lambda v: pcbnew.ToMM(v) - 100
    out = {'pads': [], 'tracks': [], 'vias': [], 'edge': []}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            out['pads'].append([T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()),
                                'F' if p.IsOnLayer(pcbnew.F_Cu) and not p.IsOnLayer(pcbnew.B_Cu) else 'B' if not p.IsOnLayer(pcbnew.F_Cu) else 'FB',
                                f'{fp.GetReference()}.{p.GetNumber()}'])
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            out['vias'].append([T(t.GetPosition().x), T(t.GetPosition().y), t.GetNetname()])
        else:
            out['tracks'].append([T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y),
                                  pcbnew.ToMM(t.GetWidth()), 'F' if t.GetLayer() == pcbnew.F_Cu else 'B', t.GetNetname()])
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            out['edge'].append([T(d.GetStart().x), T(d.GetStart().y), T(d.GetEnd().x), T(d.GetEnd().y)])
    json.dump(out, open(sys.argv[2], 'w'))
else:
    from PIL import Image, ImageDraw, ImageFont
    d = json.load(open(sys.argv[2]))
    x0, y0, x1, y1 = map(float, sys.argv[4:8]) if len(sys.argv) > 7 else (-0.5, -0.5, 64, 38.6)
    K = 2600 / (x1 - x0)
    W, H = int((x1 - x0) * K), int((y1 - y0) * K)
    im = Image.new('RGB', (W, H), 'white'); g = ImageDraw.Draw(im)
    f = ImageFont.load_default(size=max(9, int(K * 0.32)))
    P = lambda x, y: ((x - x0) * K, (y - y0) * K)
    for xa, ya, xb, yb in d['edge']: g.line([P(xa, ya), P(xb, yb)], fill='black', width=2)
    for a, b_, c, e, side, name in d['pads']:
        col = (250, 200, 200) if side == 'F' else (200, 210, 250) if side == 'B' else (230, 200, 120)
        g.rectangle([P(a, b_), P(c, e)], fill=col)
    for xa, ya, xb, yb, w, L, n in d['tracks']:
        col = (210, 40, 40) if L == 'F' else (40, 70, 210)
        g.line([P(xa, ya), P(xb, yb)], fill=col, width=max(1, int(w * K)))
    for x, y, n in d['vias']:
        r = 0.25 * K; g.ellipse([P(x, y)[0] - r, P(x, y)[1] - r, P(x, y)[0] + r, P(x, y)[1] + r], fill=(60, 160, 60))
    # net names at the middle of the longest segment of each net and layer
    best = {}
    for xa, ya, xb, yb, w, L, n in d['tracks']:
        ln = ((xb - xa) ** 2 + (yb - ya) ** 2) ** .5
        if n in ('GND',) or ln < 1.5: continue
        if ln > best.get((n, L), (0,))[0]: best[(n, L)] = (ln, (xa + xb) / 2, (ya + yb) / 2)
    for (n, L), (ln, x, y) in best.items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            g.text(P(x, y), n, fill=(150, 0, 0) if L == 'F' else (0, 0, 120), font=f, anchor='mm', stroke_width=2, stroke_fill='white')
    im.save(sys.argv[3])
