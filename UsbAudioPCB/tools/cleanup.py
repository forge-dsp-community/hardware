# Clean-up after route_nc.py: KiCad DRC on the routed board, every signal net involved in a clearance,
# short, crossing or open connection is ripped up completely and routed again with all other copper as
# hard obstacle (route.py rules). Failed nets go to the front in the next pass; if a net still fails,
# the signal nets whose copper lies around its pads are ripped up as well and routed after it.
# Repeated up to 4 rounds, each from the original routed board with the grown rip-up set.
#   /usr/bin/python3 tools/cleanup.py routed.kicad_pcb [passes]   -> routed-clean.kicad_pcb
import sys, os, re, json, subprocess, tempfile, math
import pcbnew

CHILD = sys.argv[1] == '--route'
if CHILD: _, _, RIP, BADJ, OUTB, OUTJ, PASSES = sys.argv; PASSES = int(PASSES)
else: PATH = sys.argv[1]; PASSES = int(sys.argv[2]) if len(sys.argv) > 2 else 6
PLANE = {'GND', '+3V3', 'XMOS.3V3', 'XMOS.1V0'}

def drc_nets(path):
    out = tempfile.mktemp(suffix='.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-error', '--format', 'json', '-o', out, path], capture_output=True)
    d = json.load(open(out)); bad = set(); n_viol = 0
    for v in d['violations']:
        if v['type'] not in ('clearance', 'shorting_items', 'tracks_crossing', 'hole_clearance', 'items_not_allowed'): continue
        n_viol += 1
        nets = [m for it in v['items'] for m in re.findall(r'\[(.+?)\]', it['description'])]
        sig = [n for n in nets if n not in PLANE]
        bad |= set(sig[:1] if len(sig) > 1 else sig)    # one of two signal nets is enough
    for v in d['unconnected_items']:
        nets = [m for it in v['items'] for m in re.findall(r'\[(.+?)\]', it['description'])]
        bad |= {n for n in nets if n not in PLANE}
    return bad, n_viol, len(d['unconnected_items'])

if CHILD:
    sys.argv = [sys.argv[0], RIP]
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'route.py')).read()
    exec(src[:src.index('# ---- order')])
    import copy
    base = (copy.deepcopy(own_t), copy.deepcopy(own_v), copy.deepcopy(netof_t), copy.deepcopy(netof_v))
    ORDER = ['USB.1.DP', 'USB.1.DM', 'COM.D+', 'COM.D-']
    bad = set(json.load(open(BADJ)))
    order = [n for n in ORDER if n in bad] + sorted((n for n in bad if n not in ORDER),
             key=lambda n: sum(abs(a[1] - c[1]) + abs(a[2] - c[2]) for a in pads_of.get(n, []) for c in pads_of.get(n, [])[:1]))
    best_run = None
    for pass_no in range(PASSES):
        own_t[:], own_v[:] = copy.deepcopy(base[0]), copy.deepcopy(base[1])
        netof_t[:], netof_v[:] = copy.deepcopy(base[2]), copy.deepcopy(base[3])
        new_tracks.clear(); new_vias.clear(); failed = []; pair_cells = None
        for net in order:
            pads = pads_of.get(net, [])
            if len(pads) < 2: continue
            nid = NID[net]; w = width(net)
            extra = ring(max(0.0, (w - 0.15) / 2)) if w > 0.16 else []
            attract = pair_cells if net in ('USB.1.DM', 'COM.D-') and pair_cells else None
            remaining = pads[1:]; tree = pad_cells(pads[0][4], pads[0][3])
            while remaining:
                tl = list(tree)[:300]
                remaining.sort(key=lambda pd: min(abs(pd[1] - pos(i, j)[0]) + abs(pd[2] - pos(i, j)[1]) for i, j, L in tl))
                name, x, y, layers, rect, p = remaining.pop(0)
                tgt = pad_cells(rect, layers)
                path = astar(nid, tree | copper_cells(net), tgt, extra, attract)
                if path is None: failed.append(f'{net}:{name}'); continue
                commit(net, nid, path, w); tree |= tgt | copper_cells(net)
            if net in ('USB.1.DP', 'COM.D+'):
                k = int(round((w + 0.15) / G)); pair_cells = set()
                for i, j, L in copper_cells(net):
                    for di, dj in ring(k * G + 0.05):
                        if abs(math.hypot(di, dj) - k) < 0.75: pair_cells.add((i + di, j + dj, L))
        print(f'pass {pass_no}: failed {len(failed)} {failed}', flush=True)
        if best_run is None or len(failed) < len(best_run[2]): best_run = (list(new_tracks), list(new_vias), list(failed))
        if not failed: break
        fn = []
        for f_ in failed:
            n_ = f_.split(':')[0]
            if n_ not in fn: fn.append(n_)
        order = [n for n in ORDER if n in order and n not in fn] + fn + [n for n in order if n not in fn and n not in ORDER]

    for xa, ya, xb, yb, w, L, net in best_run[0]:
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(xa), mm(ya))); t.SetEnd(pcbnew.VECTOR2I(mm(xb), mm(yb)))
        t.SetWidth(mm(w)); t.SetLayer(pcbnew.F_Cu if L == F else pcbnew.B_Cu); t.SetNet(b.FindNet(net)); b.Add(t)
    for vx, vy, net in best_run[1]:
        v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
        v.SetNet(b.FindNet(net)); b.Add(v)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(OUTB)
    # signal nets with copper within 1.5 mm of a failed pad: they boxed it in
    neigh = set()
    for f_ in best_run[2]:
        net, name = f_.split(':')
        pd = [q for q in pads_of.get(net, []) if q[0] == name]
        if not pd: continue
        px_, py_ = pd[0][1], pd[0][2]
        for t in b.GetTracks():
            n2 = t.GetNetname()
            if n2 in PLANE or n2 == net: continue
            for q in ((t.GetStart(), t.GetEnd()) if t.Type() != pcbnew.PCB_VIA_T else (t.GetPosition(),)):
                if math.hypot(T(q.x) - px_, T(q.y) - py_) < 1.5: neigh.add(n2)
    json.dump({'failed': best_run[2], 'neigh': sorted(neigh)}, open(OUTJ, 'w'))
    sys.exit(0)

def aux(src_pcb, dst_pcb):
    for ext in ('.kicad_pro', '.kicad_dru'):
        a = src_pcb.replace('.kicad_pcb', ext)
        if os.path.exists(a): open(dst_pcb.replace('.kicad_pcb', ext), 'w').write(open(a).read())

bad, nv, nu = drc_nets(PATH)
print(f'DRC before: {nv} violations, {nu} unconnected', flush=True)
OUT = PATH.replace('.kicad_pcb', '-clean.kicad_pcb'); best = None
for rnd in range(4):
    print(f'round {rnd}: rip up {len(bad)} nets {sorted(bad)}', flush=True)
    rip = PATH.replace('.kicad_pcb', '-rip.kicad_pcb'); badj = rip + '.json'; tryb = PATH.replace('.kicad_pcb', '-try.kicad_pcb')
    json.dump(sorted(bad), open(badj, 'w'))
    # rip up in a child process: a second LoadBoard in the same process breaks the SWIG objects
    subprocess.run([sys.executable, '-c', 'import pcbnew,sys,json; b=pcbnew.LoadBoard(sys.argv[1]); bad=set(json.load(open(sys.argv[3])))\n'
                    'for t in list(b.GetTracks()):\n    if t.GetNetname() in bad: b.Remove(t)\nb.Save(sys.argv[2])',
                    PATH, rip, badj], check=True, capture_output=True)
    aux(PATH, rip)
    r = subprocess.run([sys.executable, os.path.abspath(__file__), '--route', rip, badj, tryb, tryb + '.json', str(PASSES)], capture_output=True, text=True)
    print('\n'.join(l for l in r.stdout.splitlines() if l.startswith('pass')), flush=True)
    if r.returncode: print(r.stderr[-2000:]); break
    aux(PATH, tryb)
    res = json.load(open(tryb + '.json'))
    bad2, nv2, nu2 = drc_nets(tryb)
    print(f'  DRC: {nv2} violations, {nu2} unconnected, failed {res["failed"]}', flush=True)
    if best is None or nv2 + nu2 < best:
        best = nv2 + nu2; os.replace(tryb, OUT); aux(PATH, OUT)
    if nv2 + nu2 == 0: break
    bad |= bad2 | set(res['neigh']) | {f.split(':')[0] for f in res['failed']}
print(f'best: {best} problems, written {OUT}')
