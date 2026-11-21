"""KiCad-Schaltplan + Symbolbibliothek aus model.json erzeugen (netzrichtig, Label-basiert)"""
import sys, json, uuid, os
S = __import__('os').environ.get('SDIR', 'es/')
OUT, NAME = sys.argv[1], sys.argv[2]
LIB = 'forge_ad_da'
M = json.load(open(S + 'model.json'))
FPN = json.load(open(S + 'fpnames.json'))
NS = uuid.UUID('5b0d3c1e-9f7a-4c55-9a3e-2f1c9d0e8a11')
def U(s): return str(uuid.uuid5(NS, s))
ROOT = U('root-sheet')
G = 1.27
def g(v): return round(round(v / G) * G, 2)
def q(s): return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'
FONT = '(effects (font (size 1.27 1.27)))'
HIDE = '(effects (font (size 1.27 1.27)) (hide yes))'

PCM = {1: 'VREFL', 2: 'AGNDL', 3: 'VCOML', 4: 'VINL+', 5: 'VINL-', 6: 'FMT0', 7: 'FMT1', 8: 'S/M', 9: 'FS0', 10: 'FS1',
       11: 'FS2', 12: 'HPFD', 13: 'DGND', 14: 'VDD', 15: 'SDOUT', 16: 'BCK', 17: 'LRCK', 18: 'SCKI', 19: '/RST',
       20: 'CLIPR', 21: 'CLIPL', 22: 'VCC', 23: 'AGND', 24: 'VINR-', 25: 'VINR+', 26: 'VCOMR', 27: 'AGNDR', 28: 'VREFR'}
ES = "VDD_L1 VOUT1+ VOUT1- VOUT3- VOUT3+ AGND_L2 AVCC_L2 RESET GND1 AVCC_L3 AGND_L3 VOUT5+ VOUT5- VOUT7- VOUT7+ VDD_L2 AVCC_L4 AGND_L4 GND2 VDD2 SDA SCL XO XI DVCC_B LOCK NC NC1 VDD3 GND3 AGND_R5 AVCC_R5 VDD_R2 VOUT8+ VOUT8- VOUT6- VOUT6+ AGND_R3 AVCC_R3 AUTOMUTE ADDR AVCC_R2 AGND_R2 VOUT4+ VOUT4- VOUT2- VOUT2+ VDD_R1 AVCC_R1 AGND_R1 GND4 DATA8 DATA7 DATA6 DATA5 DATA4 DATA3 DATA2 DATA1 DATA_CLK VDD1 DVCC_T AGND_L1 AVCC_L1".split()
PCA = {1: 'A2', 2: 'IO0', 3: 'IO1', 4: 'IO2', 5: 'IO3', 6: 'VSS', 7: 'IO4', 8: 'IO5', 9: 'IO6', 10: 'IO7', 11: '~{INT}',
       12: 'SCL', 13: 'SDA', 14: 'VDD', 15: 'A0', 16: 'A1', 17: 'EP'}

# ------------------------------------------------------------ Symbol-Definitionen
SYMS = {}
def box_symbol(name, left, right, top=(), bottom=(), w=None, refpfx='U', desc='', h=None):
    """left/right/top/bottom: Liste (num, name) in Reihenfolge oben->unten bzw. links->rechts"""
    n = max(len(left), len(right), 1)
    hmin = (n + 1) * 2.54
    h = max(h or 0, hmin)
    off = g((h - hmin) / 2)
    nt = max(len(top), len(bottom), 0)
    if w is None:
        w = max(15.24, (nt + 1) * 2.54, 10.16 + 2.54 * 2)
    w = g(w); h = g(max(h, 7.62))
    left=[(str(a),b) for a,b in left]; right=[(str(a),b) for a,b in right]; top=[(str(a),b) for a,b in top]; bottom=[(str(a),b) for a,b in bottom]
    pins = []   # (num, name, x, y, ang)
    def ys(k, cnt, H): return [g(H / 2 - 2.54 * (i + 1) + (H - (cnt + 1) * 2.54) / -2 + 0) for i in range(cnt)]
    for i, (num, nm) in enumerate(left):
        pins.append((num, nm, -w / 2 - 2.54, g(h / 2 - off - 2.54 * (i + 1)), 0))
    for i, (num, nm) in enumerate(right):
        pins.append((num, nm, w / 2 + 2.54, g(h / 2 - off - 2.54 * (i + 1)), 180))
    offx = g((w - (nt + 1) * 2.54) / 2) if nt else 0
    for i, (num, nm) in enumerate(top):
        pins.append((num, nm, g(-w / 2 + offx + 2.54 * (i + 1)), h / 2 + 2.54, 270))
    for i, (num, nm) in enumerate(bottom):
        pins.append((num, nm, g(-w / 2 + offx + 2.54 * (i + 1)), -h / 2 - 2.54, 90))
    SYMS[name] = dict(kind='box', w=w, h=h, pins=pins, ref=refpfx, desc=desc)

def two_symbol(name, ref, polar=False, desc=''):
    SYMS[name] = dict(kind='two', pins=[('1', '1', 0, 3.81, 270), ('2', '2', 0, -3.81, 90)], ref=ref, polar=polar, desc=desc)

box_symbol('PCM4202', [(i, PCM[i]) for i in range(1, 15)], [(i, PCM[i]) for i in range(28, 14, -1)], w=22.86, refpfx='IC',
           desc='TI PCM4202 Stereo-ADC 24 Bit, SSOP-28')
box_symbol('ES9018', [(i, ES[i - 1]) for i in range(1, 17)], [(i, ES[i - 1]) for i in range(48, 32, -1)],
           top=[(i, ES[i - 1]) for i in range(64, 48, -1)], bottom=[(i, ES[i - 1]) for i in range(17, 33)], w=71.12, h=71.12,
           refpfx='IC', desc='ESS ES9018 Sabre32 8-Kanal-DAC, TQFP-64')
box_symbol('PCA9554', [(14, 'VDD'), (12, 'SCL'), (13, 'SDA'), (15, 'A0'), (16, 'A1'), (1, 'A2'), (6, 'VSS'), (17, 'EP')],
           [(11, '~{INT}'), (2, 'IO0'), (3, 'IO1'), (4, 'IO2'), (5, 'IO3'), (7, 'IO4'), (8, 'IO5'), (9, 'IO6'), (10, 'IO7')],
           w=17.78, refpfx='IC', desc='NXP PCA9554 8-Bit I2C-Port-Expander, HVQFN-16')
two_symbol('C', 'C', desc='Kondensator (rekonstruiert)')
two_symbol('CP', 'C', polar=True, desc='Tantal-Elko (rekonstruiert)')
two_symbol('R', 'R', desc='Widerstand/Bruecke (rekonstruiert)')

def generic(c):
    """Symbol für Bauteile mit unbekannter Pinbelegung: Pins nach Nummer"""
    nums = [p['num'] for p in c['pads']]
    seen = []; [seen.append(n) for n in nums if n not in seen]
    nm = 'GEN_%s' % c['ref']
    half = (len(seen) + 1) // 2
    L = [(n, n) for n in seen[:half]]; R = [(n, n) for n in seen[half:]]
    box_symbol(nm, L, R, w=12.7, refpfx=c['ref'].rstrip('0123456789'), desc=c.get('value', ''))
    return nm

def conn_symbol(c, name):
    nums = []; [nums.append(p['num']) for p in c['pads'] if p['num'] not in nums]
    nums.sort(key=lambda s: int(s) if s.isdigit() else 999)
    box_symbol(name, [(n, n) for n in nums], [], w=7.62, refpfx=c['ref'].rstrip('0123456789'), desc=c.get('value', ''))

def sym_for(c):
    k = c['kind']
    if k in ('PCM4202', 'ES9018', 'PCA9554'): return k
    if k.startswith('TANT'): return 'CP'
    if k in ('0805', '0603', 'SMD2'): return 'R' if c['ref'].startswith('R') else 'C'
    if k in ('EDGE', 'HDR', 'OUTSLOT'): nm = 'CONN_%s' % c['ref']; conn_symbol(c, nm); return nm
    if k == 'SJ3':
        if 'SJ3' not in SYMS: box_symbol('SJ3', [('1', 'A'), ('2', 'C'), ('3', 'B')], [], w=7.62, refpfx='JP', desc='Loetbruecke 3-polig')
        return 'SJ3'
    return generic(c)

def sym_lib_text(name, d, full=True):
    pfx = (LIB + ':') if not full else ''
    out = ['  (symbol %s (pin_names (offset 0.762)) (exclude_from_sim no) (in_bom yes) (on_board yes)' % q(pfx + name)]
    out.append('    (property "Reference" %s (at 0 %s 0) %s)' % (q(d['ref']), g((d.get('h', 7.62) / 2) + 3.81) if d['kind'] == 'box' else 0, FONT))
    out.append('    (property "Value" %s (at 0 %s 0) %s)' % (q(name), -g((d.get('h', 7.62) / 2) + 3.81) if d['kind'] == 'box' else 0, FONT))
    out.append('    (property "Footprint" "" (at 0 0 0) %s)' % HIDE)
    out.append('    (property "Datasheet" "" (at 0 0 0) %s)' % HIDE)
    out.append('    (property "Description" %s (at 0 0 0) %s)' % (q(d.get('desc', '')), HIDE))
    out.append('    (symbol %s' % q(name + '_0_1'))
    if d['kind'] == 'box':
        out.append('      (rectangle (start %s %s) (end %s %s) (stroke (width 0.254) (type default)) (fill (type background)))'
                   % (-d['w'] / 2, d['h'] / 2, d['w'] / 2, -d['h'] / 2))
    else:
        if d.get('polar'):
            out.append('      (polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508) (type default)) (fill (type none)))')
            out.append('      (arc (start -2.032 -1.27) (mid 0 -0.508) (end 2.032 -1.27) (stroke (width 0.508) (type default)) (fill (type none)))')
            out.append('      (text "+" (at -1.524 1.778 0) %s)' % FONT)
        elif d['ref'] == 'R':
            out.append('      (rectangle (start -1.016 2.54) (end 1.016 -2.54) (stroke (width 0.254) (type default)) (fill (type none)))')
        else:
            out.append('      (polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508) (type default)) (fill (type none)))')
            out.append('      (polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.508) (type default)) (fill (type none)))')
    out.append('    )')
    out.append('    (symbol %s' % q(name + '_1_1'))
    for num, nm, x, y, a in d['pins']:
        ln = 2.54 if d['kind'] == 'box' else (3.81 - (0.762 if d['ref'] != 'R' else 2.54)) if False else (3.048 if d['ref'] != 'R' else 1.27)
        out.append('      (pin passive line (at %s %s %s) (length %s) (name %s %s) (number %s %s))' % (x, y, a, ln, q(nm), FONT, q(num), FONT))
    out.append('    )')
    if d['kind'] == 'two':
        out.insert(1, '    (pin_numbers (hide yes)) (pin_names (offset 0.254) (hide yes))'.replace('(pin_names (offset 0.254) (hide yes))', ''))
    out.append('  )')
    return '\n'.join(out)

# ------------------------------------------------------------ Platzierung
comps = {c['ref']: c for c in M['comps']}
for c in M['comps']: c['_sym'] = sym_for(c)
place = {}
def grp_of(c):
    nets = {p['net'] for p in c['pads']}
    for i in (1, 2, 3):
        if any(n.endswith('.%d' % i) and not n.startswith(('AD.OUT', 'SDA', 'SCL')) for n in nets): return 'IC10%d' % i
    if any(n.startswith(('VOUT', '1V2', '3V3_AVCC', '3V3.NOHF', 'ES_', 'MCLK.DA')) for n in nets): return 'IC105'
    return 'MISC'
anchor = {'IC103': (110.49, 88.9), 'IC102': (255.27, 88.9), 'IC101': (400.05, 88.9), 'IC105': (680.72, 139.7),
          'IC104': (118.11, 345.44)}
for r, xy in anchor.items(): place[r] = xy
place['X100'] = (40.64, 120.65); place['X101'] = (40.64, 220.98); place['X102'] = (40.64, 260.35)
for k in range(1, 5): place['J%d' % k] = (g(533.4 + (k - 1) * 50.8), 345.44)
place['JP1'] = (40.64, 300.99); place['JP2'] = (40.64, 325.12); place['JP3'] = (40.64, 349.25)
others = [c for c in M['comps'] if c['kind'] in ('SOT23-5', 'SOT89', 'SOIC8', 'SOT23')]
for i, c in enumerate(others): place[c['ref']] = (g(200 + i * 55), 345.44)
areas0 = {'IC103': (76.2, 152.4, 6), 'IC102': (220.98, 152.4, 6), 'IC101': (365.76, 152.4, 6), 'IC105': (566.42, 233.68, 10),
         'MISC': (180.34, 400.05, 14)}
areas = areas0
areas['MISC'] = (180.34, 400.05, 18)
cnt = {k: 0 for k in areas}
for c in M['comps']:
    if c['ref'] in place: continue
    if c['_sym'] in ('C', 'CP', 'R'):
        gk = grp_of(c); x0, y0, ncol = areas[gk]; k = cnt[gk]; cnt[gk] += 1
        place[c['ref']] = (g(x0 + (k % ncol) * 22.86), g(y0 + (k // ncol) * 33.02))
tps = [c for c in M['comps'] if c['ref'] not in place]
for i, c in enumerate(tps):
    place[c['ref']] = (g(60 + (i % 13) * 55.88), g(520 + (i // 13) * 30.48))

# ------------------------------------------------------------ Schaltplan schreiben
lines = []
A = lines.append
A('(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid %s) (paper "A1")' % q(ROOT))
A('  (title_block (title "Forge ES9018/PCM4202 AD/DA V4.0 - Rekonstruktion") (rev "V4.0-rek1") (company "nach Mark Duprau (CC BY-NC-SA 4.0)")')
A('    (comment 1 "Netzliste aus Kupferlagen (Eagle-Render + Eurocircuits-Gerberbilder, 300 dpi) rekonstruiert")')
A('    (comment 2 "Bauteilwerte nach Original-Schaltplan; mit ? markierte Werte sind unbekannt")')
A('    (comment 3 "Referenzen C2xx/R2xx/TPxx/U2xx neu vergeben (Original-Bestueckungsdruck ohne Namen)"))')
A('  (lib_symbols')
used_syms = []
for c in M['comps']:
    if c['_sym'] not in used_syms: used_syms.append(c['_sym'])
for s in used_syms: A(sym_lib_text(s, SYMS[s], full=False))
A('  )')

def glabel(net, x, y, ang):
    just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[ang]
    A('  (global_label %s (shape passive) (at %s %s %s) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify %s)) (uuid %s)'
      % (q(net), x, y, ang, just, q(U('gl%s%s%s' % (net, x, y)))))
    A('    (property "Intersheetrefs" "${INTERSHEET_REFS}" (at %s %s 0) %s))' % (x, y, HIDE))

nlabels = 0; nnc = 0
for c in M['comps']:
    sname = c['_sym']; d = SYMS[sname]; X, Y = place[c['ref']]
    uid = U('sym-' + c['ref'])
    fp = '%s:%s' % (LIB, FPN.get(c['ref'], ''))
    A('  (symbol (lib_id %s) (at %s %s 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid %s)'
      % (q(LIB + ':' + sname), X, Y, q(uid)))
    if d['kind'] == 'box':
        ry, vy = Y - d['h'] / 2 - 3.81, Y + d['h'] / 2 + 3.81
        if d['pins'] and any(p[4] == 270 for p in d['pins']): ry -= 15
        if any(p[4] == 90 for p in d['pins']): vy += 15
        A('    (property "Reference" %s (at %s %s 0) %s)' % (q(c['ref']), X, g(ry), FONT))
        A('    (property "Value" %s (at %s %s 0) %s)' % (q(c.get('value', sname)), X, g(vy), FONT))
    else:
        A('    (property "Reference" %s (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left)))' % (q(c['ref']), X + 2.54, Y - 1.27))
        A('    (property "Value" %s (at %s %s 0) (effects (font (size 1.0 1.0)) (justify left)))' % (q(c.get('value', '')), X + 2.54, Y + 1.27))
    A('    (property "Footprint" %s (at %s %s 0) %s)' % (q(fp), X, Y, HIDE))
    A('    (property "Datasheet" "" (at %s %s 0) %s)' % (X, Y, HIDE))
    A('    (property "Description" "" (at %s %s 0) %s)' % (X, Y, HIDE))
    for num, *_ in d['pins']: A('    (pin %s (uuid %s))' % (q(num), q(U('pin%s%s' % (c['ref'], num)))))
    A('    (instances (project %s (path %s (reference %s) (unit 1)))))' % (q(NAME), q('/' + ROOT), q(c['ref'])))
    # Netze an Pins
    netof = {}
    for p in c['pads']:
        if p['net'] and p['num'] not in netof: netof[p['num']] = p['net']
    for num, nm, px, py, a in d['pins']:
        ex, ey = g(X + px), g(Y - py)
        net = netof.get(num, '')
        if not net:
            A('  (no_connect (at %s %s) (uuid %s))' % (ex, ey, q(U('nc%s%s' % (c['ref'], num))))); nnc += 1; continue
        # Stichleitung nach außen
        dx, dy = {0: (-2.54, 0), 180: (2.54, 0), 270: (0, -2.54), 90: (0, 2.54)}[a]
        if d['kind'] == 'two': dx, dy = 0, (-1.27 if a == 270 else 1.27)
        lx, ly = g(ex + dx), g(ey + dy)
        A('  (wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))' % (ex, ey, lx, ly, q(U('w%s%s' % (c['ref'], num)))))
        lang = {0: 180, 180: 0, 270: 90, 90: 270}[a]
        glabel(net, lx, ly, lang); nlabels += 1

# Hinweistext
A('  (text %s (at 30 25 0) (effects (font (size 3 3)) (justify left)) (uuid %s))' % (
    q('Forge ES9018/PCM4202 AD/DA V4.0 - aus Kupferlagen rekonstruiert. Verbindungen ueber globale Netzlabels.'), q(U('t1'))))
A('  (text %s (at 30 32 0) (effects (font (size 2 2)) (justify left)) (uuid %s))' % (
    q('IC101..IC103 = PCM4202 (AD.OUT.1..3), IC105 = ES9018, IC104 = PCA9554 (CLIP/Reset-Steuerung), U201..U204 = Regler, nicht im Original-Schaltplanbild'), q(U('t2'))))
A('  (sheet_instances (path "/" (page "1")))')
A(')')
open(os.path.join(OUT, NAME + '.kicad_sch'), 'w').write('\n'.join(lines) + '\n')

# Symbolbibliothek
L = ['(kicad_symbol_lib (version 20241209) (generator "forge_rekonstruktion") (generator_version "9.0")']
for s in used_syms: L.append(sym_lib_text(s, SYMS[s], full=True))
L.append(')')
open(os.path.join(OUT, LIB + '.kicad_sym'), 'w').write('\n'.join(L) + '\n')
print('Schaltplan: Symbole', len(M['comps']), 'Labels', nlabels, 'NC', nnc, 'Symboltypen', len(used_syms))
