"""KiCad-Platine + Footprint-Bibliothek aus model.json / polys.json erzeugen"""
import sys, json, math, os, uuid
import pcbnew as K

S = os.environ.get('SDIR', '/tmp/claude-1000/-home-cronix--claude-spares-spare-C0uZXh/8ff8dc26-7d6e-41bb-9625-05510eb690c7/scratchpad/es/')
OUT = sys.argv[1]
NAME = sys.argv[2]
LIB = os.environ.get('LIBNAME', 'forge_ad_da')
M = json.load(open(S + 'model.json')); PL = json.load(open(S + 'polys.json'))
OX, OY, H = 100.0, 100.0, float(os.environ.get('BOARD_H', '56.39'))
mm = K.FromMM
def P(x, y): return K.VECTOR2I(int(round((OX + x) * 1e6 / 1000)) * 1000, int(round((OY + H - y) * 1e6 / 1000)) * 1000)

b = K.NewBoard(os.path.join(OUT, NAME + '.kicad_pcb'))
b.SetCopperLayerCount(4)
ds = b.GetDesignSettings()
ds.m_MinClearance = mm(0.08); ds.m_TrackMinWidth = mm(0.1); ds.m_ViasMinSize = mm(0.45)
ds.m_MinThroughDrill = mm(0.25); ds.m_ViasMinAnnularWidth = mm(0.1); ds.m_CopperEdgeClearance = mm(0.0)
ds.m_HoleClearance = mm(0.1); ds.m_HoleToHoleMin = mm(0.2)
nc = ds.m_NetSettings.GetDefaultNetclass() if hasattr(ds.m_NetSettings, 'GetDefaultNetclass') else None
if nc:
    nc.SetClearance(mm(0.08)); nc.SetTrackWidth(mm(0.15)); nc.SetViaDiameter(mm(0.6)); nc.SetViaDrill(mm(0.3))

# Netze
nets = {}
def net(name):
    if not name: return None
    if name not in nets:
        n = K.NETINFO_ITEM(b, name); b.Add(n); nets[name] = n
    return nets[name]
for c in M['comps']:
    for p in c['pads']: net(p['net'])
for v in M['vias']: net(v['net'])
for L in PL['copper'].values():
    for it in L: net(it['net'])

# Umriss
o = PL['outline']
for i in range(len(o)):
    s = K.PCB_SHAPE(b); s.SetShape(K.SHAPE_T_SEGMENT); s.SetLayer(K.Edge_Cuts); s.SetWidth(mm(0.1))
    s.SetStart(P(*o[i])); s.SetEnd(P(*o[(i + 1) % len(o)])); b.Add(s)

LAY = {'F.Cu': K.F_Cu, 'B.Cu': K.B_Cu, 'In1.Cu': K.In1_Cu, 'In2.Cu': K.In2_Cu, 'F.SilkS': K.F_SilkS, 'B.SilkS': K.B_SilkS}

def polyset(outer, holes, f=P):
    ps = K.SHAPE_POLY_SET(); ps.NewOutline()
    for x, y in outer:
        v = f(x, y); ps.Append(v.x, v.y)
    for h in holes:
        hi = ps.NewHole()
        for x, y in h:
            v = f(x, y); ps.Append(v.x, v.y, 0, hi)
    return ps

# Kupfer als gefüllte Zonen (netzrichtig, Originalgeometrie)
nz = 0
for lname, items in PL['copper'].items():
    for it in items:
        z = K.ZONE(b); z.SetLayer(LAY[lname])
        n = net(it['net'])
        if n: z.SetNet(n)
        ps = polyset(it['outer'], it['holes'])
        ps.Simplify()
        if ps.OutlineCount() == 0: continue
        zo = z.Outline(); zo.RemoveAllContours() if hasattr(zo, 'RemoveAllContours') else None
        zo.Append(ps)
        z.SetLocalClearance(mm(0.08)); z.SetMinThickness(mm(0.05))
        z.SetPadConnection(K.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(K.ISLAND_REMOVAL_MODE_NEVER)
        z.SetAssignedPriority(1 if n else 0)
        z.SetZoneName('orig_%s' % lname.split('.')[0])
        z.SetFilledPolysList(LAY[lname], ps)
        z.SetIsFilled(True); z.SetNeedRefill(False)
        b.Add(z); nz += 1

# Bestückungsdruck
for lname, items in PL['silk'].items():
    for it in items:
        s = K.PCB_SHAPE(b); s.SetShape(K.SHAPE_T_POLY); s.SetLayer(LAY[lname]); s.SetFilled(True); s.SetWidth(0)
        ps = polyset(it['outer'], it['holes']); s.SetPolyShape(ps); b.Add(s)

# Vias
for v in M['vias']:
    if v['drill'] >= 1.5:   # Montagebohrungen -> NPTH-Footprint
        continue
    vi = K.PCB_VIA(b); vi.SetPosition(P(v['x'], v['y'])); vi.SetDrill(mm(v['drill']))
    vi.SetWidth(mm(max(v['dia'], v['drill'] + 0.2))); vi.SetViaType(K.VIATYPE_THROUGH)
    n = net(v['net'])
    if n: vi.SetNet(n)
    b.Add(vi)

# --------------------------------------------------------------- Footprints
FPNAME = {'PCM4202': 'SSOP-28_PCM4202_Eagle', 'ES9018': 'TQFP-64_ES9018_Eagle', 'PCA9554': 'HVQFN-16_3x3_P0.5_EP',
          'SOT23-5': 'SOT-23-5_Eagle', 'SOT89': 'SOT-89-3_Eagle', 'SOIC8': 'SOIC-8_Eagle', 'SOT23': 'SOT-23-3_custom',
          'SJ3': 'SolderJumper-3_Top', 'EDGE': 'X100_Castellated_1x20_P2.0_Power', '0805': 'C_0805_Eagle',
          '0603': 'C_0603_Eagle', 'TANT_C': 'CP_Tantalum_Case-C_TPSC', 'TANT_B': 'CP_Tantalum_Case-B', 'SMD2': 'L_C_1206ish_Eagle', 'OUTSLOT': 'Slot_IV-Ausgang_1x06_P1.27_Rand', '1206': 'RC_1206_Eagle', '1210': 'RC_1210_Eagle', 'SOIC14': 'SOIC-14_Eagle', 'TAB': 'Steckzunge_13pol_Forge_IV', 'CP_TH': 'R_0R_auf_Elkoplatz_TH'}   # Elkoplatz, real mit 0-Ohm-1206 bestückt
if os.environ.get('OUTBOARD'):
    FPNAME['0603'] = 'RC_0603_Eagle'; FPNAME['0805'] = 'RC_0805_Eagle'
libdir = os.path.join(OUT, LIB + '.pretty'); os.makedirs(libdir, exist_ok=True)
io = K.PCB_IO_KICAD_SEXPR()
saved = set()
PADSIZE = {}
LIBGEO = {}

def mk_fp(c, board, for_lib=False):
    side = c['side']; bottom = side == 'B'
    cx, cy = round(c['cx'], 3), round(c['cy'], 3)
    pads = c['pads']; rot = 0; TWO = None
    name = FPNAME.get(c['kind']) or ('Pads_%s' % c['ref'] if c['kind'] == 'PADGRP' else '%s_%s' % (c['kind'], c['ref']))
    if c['kind'] in ('0805', '0603', 'TANT_C', 'TANT_B', 'SMD2', '1206', '1210', 'CP_TH'):
        a, bb = pads[0], pads[1]
        d = math.hypot(a['x'] - bb['x'], a['y'] - bb['y'])
        d = round(d / 0.05) * 0.05; TWO = d
        name += '_P%.2f' % d
    def loc(p, th):
        x, y = p['x'] - cx, -(p['y'] - cy)
        if bottom: x = -x
        t = math.radians(th); return x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t)
    if name in LIBGEO:
        ref_geo = LIBGEO[name]; bestd = None
        for th in (0, 90, 180, 270):
            d = 0
            for p in pads:
                lx_, ly_ = loc(p, th); gx, gy = ref_geo.get(p['num'], (1e3, 1e3)); d += abs(lx_ - gx) + abs(ly_ - gy)
            if bestd is None or d < bestd: bestd, rot = d, th
    elif c.get('rotv'):
        rot = 90
    elif len(pads) == 2 and c['kind'] not in ('PADGRP',):
        for th in (0, 90, 180, 270):
            a = loc(pads[0], th); bq = loc(pads[1], th)
            if a[0] < bq[0] and abs(a[1] - bq[1]) < 0.06: rot = th; break
    fp = K.FOOTPRINT(board)
    fp.SetFPID(K.LIB_ID(LIB, name))
    fp.SetReference(c['ref']); fp.SetValue(c.get('value', ''))
    if c.get('datasheet') and not for_lib:
        for fld in fp.GetFields():
            if fld.GetName() == 'Datasheet': fld.SetText(c['datasheet'])
    fp.Reference().SetLayer(K.F_Fab); fp.Value().SetLayer(K.F_Fab)
    for t in (fp.Reference(), fp.Value()):
        t.SetTextSize(K.VECTOR2I(mm(0.6), mm(0.6))); t.SetTextThickness(mm(0.09))
    fp.Value().SetPosition(K.VECTOR2I(0, mm(0.8))); fp.Value().SetVisible(False)
    xs, ys = [], []
    GEO = {}
    for p in pads:
        # lokale Koordinaten (Footprint-Frontansicht, y nach unten)
        lx, ly = loc(p, rot)           # Spiegelung (Unterseite) + Rückdrehung in Footprint-Achse
        if TWO and abs(ly) < 0.3:      # 2-polig: symmetrisch auf Normraster
            lx, ly = (-TWO / 2 if lx < 0 else TWO / 2), 0.0
        lx, ly = round(lx, 3), round(ly, 3)
        w, h = p['w'], p['h']
        if rot in (90, 270): w, h = h, w
        key = (name, p['num'])
        if key in PADSIZE: w, h = PADSIZE[key]
        else: PADSIZE[key] = (w, h)
        layers = []
        want = ['F', 'B'] if p['side'] == 'FB' else [p['side']]
        for wl in want:
            pre = wl if not bottom else {'F': 'B', 'B': 'F'}[wl]   # Lage vor dem Flip
            layers.append(pre)
        if p['th']:
            pd = K.PAD(fp); pd.SetAttribute(K.PAD_ATTRIB_PTH)
            pd.SetLayerSet(K.PAD.PTHMask())
            pd.SetDrillSize(K.VECTOR2I(mm(p['drill']), mm(p['drill'])))
            pd.SetShape(K.PAD_SHAPE_RECTANGLE if p['shape'] == 'rect' else K.PAD_SHAPE_CIRCLE)
            sz = max(min(w, h), p['drill'] + 0.3)
            pd.SetSize(K.VECTOR2I(mm(max(w, p['drill'] + 0.3)), mm(max(h, p['drill'] + 0.3))))
            pd.SetNumber(p['num']); pd.SetPosition(K.VECTOR2I(mm(lx), mm(ly))); pd.SetPos0(K.VECTOR2I(mm(lx), mm(ly))) if hasattr(pd, 'SetPos0') else None
            if not for_lib and p['net']: pd.SetNet(net(p['net']))
            fp.Add(pd)
        else:
            for pre in layers:
                pd = K.PAD(fp); pd.SetAttribute(K.PAD_ATTRIB_SMD)
                ls = K.LSET();
                for l in ((K.F_Cu, K.F_Paste, K.F_Mask) if pre == 'F' else (K.B_Cu, K.B_Paste, K.B_Mask)): ls.AddLayer(l)
                pd.SetLayerSet(ls); pd.SetShape(K.PAD_SHAPE_RECTANGLE)
                pd.SetSize(K.VECTOR2I(mm(max(w, 0.15)), mm(max(h, 0.15))))
                pd.SetNumber(p['num']); pd.SetPosition(K.VECTOR2I(mm(lx), mm(ly)))
                if not for_lib and p['net']: pd.SetNet(net(p['net']))
                fp.Add(pd)
        xs += [lx - w / 2, lx + w / 2]; ys += [ly - h / 2, ly + h / 2]
        GEO[p['num']] = (lx, ly)
    # Courtyard / Fab
    x0, x1, y0, y1 = min(xs) - 0.25, max(xs) + 0.25, min(ys) - 0.25, max(ys) + 0.25
    for lay, wid in ((K.F_CrtYd, 0.05), (K.F_Fab, 0.1)):
        r = K.PCB_SHAPE(fp); r.SetShape(K.SHAPE_T_RECT); r.SetLayer(lay); r.SetWidth(mm(wid))
        r.SetStart(K.VECTOR2I(mm(x0), mm(y0))); r.SetEnd(K.VECTOR2I(mm(x1), mm(y1))); fp.Add(r)
    fp.Reference().SetPosition(K.VECTOR2I(0, 0))
    if name not in LIBGEO: LIBGEO[name] = GEO
    return fp, name, rot

NS = uuid.UUID('5b0d3c1e-9f7a-4c55-9a3e-2f1c9d0e8a11')
FPN = {}
for c in M['comps']:
    if not c['pads']: continue
    fp, name, rot = mk_fp(c, b)
    FPN[c['ref']] = name
    fp.SetPath(K.KIID_PATH('/' + str(uuid.uuid5(NS, 'sym-' + c['ref']))))
    fp.SetSheetfile(NAME + '.kicad_sch'); fp.SetSheetname('')
    fp.SetPosition(P(round(c['cx'], 3), round(c['cy'], 3)))
    if rot: fp.SetOrientationDegrees(rot)
    if c['side'] == 'B': fp.Flip(fp.GetPosition(), K.FLIP_DIRECTION_LEFT_RIGHT)
    b.Add(fp)
    if name not in saved:
        lf, _, _ = mk_fp(c, None, True)
        lf.SetPosition(K.VECTOR2I(0, 0))
        io.FootprintSave(libdir, lf); saved.add(name)

# Montagebohrungen (2.0 mm)
mh = 0
for v in M['vias']:
    if v['drill'] < 1.5: continue
    mh += 1
    fp = K.FOOTPRINT(b); fp.SetFPID(K.LIB_ID(LIB, 'MountingHole_2.0mm_Pad2.5')); fp.SetReference('H%d' % mh)
    fp.SetValue('Bohrung 2.0'); fp.Reference().SetLayer(K.F_Fab); fp.Value().SetVisible(False)
    fp.SetAttributes(K.FP_EXCLUDE_FROM_POS_FILES | K.FP_EXCLUDE_FROM_BOM | K.FP_BOARD_ONLY)
    pd = K.PAD(fp); pd.SetAttribute(K.PAD_ATTRIB_PTH); pd.SetLayerSet(K.PAD.PTHMask()); pd.SetShape(K.PAD_SHAPE_CIRCLE)
    pd.SetDrillSize(K.VECTOR2I(mm(2.0), mm(2.0))); pd.SetSize(K.VECTOR2I(mm(2.5), mm(2.5))); pd.SetNumber('1')
    fp.Add(pd)
    if 'MH' not in saved:
        io.FootprintSave(libdir, fp); saved.add('MH')
    for pd in fp.Pads():
        n = net(v['net'])
        if n: pd.SetNet(n)
    fp.SetPosition(P(v['x'], v['y'])); b.Add(fp)

t = K.PCB_TEXT(b); t.SetText(os.environ.get('BOARD_NOTE', 'Rekonstruktion aus Eagle-/Gerber-Bildern (300 dpi) - Forge ES9018/PCM4202 AD/DA V4.0'))
t.SetLayer(K.Dwgs_User); t.SetPosition(P(0, -3)); t.SetTextSize(K.VECTOR2I(mm(1), mm(1))); t.SetHorizJustify(K.GR_TEXT_H_ALIGN_LEFT); b.Add(t)

json.dump(FPN, open(S + 'fpnames.json', 'w'))
path = os.path.join(OUT, NAME + '.kicad_pcb')
b.Save(path)
print('gespeichert', path, 'Zonen', nz, 'Footprints', len(M['comps']) + mh, 'Lib', len(saved), 'Netze', len(nets))
