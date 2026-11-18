# Generate UsbAudioPCB.kicad_sym (box symbols) and UsbAudioPCB.kicad_sch from parts.py.
# Every pin gets a net label at its end (no wires); unused pins get a no-connect flag.
# Groups follow the three sheets of the original. Run from the project directory:
#   python3 tools/gen_sch.py
import re, sys, uuid, os
sys.path.insert(0, os.path.dirname(__file__))
from parts import P, SYMBOLS

PROJ = 'UsbAudioPCB'
SYSLIB = '/usr/share/kicad/symbols/'
U = lambda: str(uuid.uuid4())
G = 2.54


def block(t, i):
    d, q = 0, False
    while True:
        c = t[i]
        if q:
            if c == '\\': i += 1
            elif c == '"': q = False
        elif c == '"': q = True
        elif c == '(': d += 1
        elif c == ')':
            d -= 1
            if d == 0: return i + 1
        i += 1


def find_sym(t, name):
    i = t.index(f'(symbol "{name}"\n')
    return t[i:block(t, i)]


def eff(size=1.27, hide=False, justify=None):
    j = f'\n\t\t\t\t(justify {justify})' if justify else ''
    h = '\n\t\t\t\t(hide yes)' if hide else ''
    return f'(effects\n\t\t\t\t(font\n\t\t\t\t\t(size {size} {size})\n\t\t\t\t){j}{h}\n\t\t\t)'


# ---------------- box symbols
def box_symbol(name, left, right, descr):
    wl = max([len(n) for _, n, _ in left] + [1]); wr = max([len(n) for _, n, _ in right] + [1])
    half = round(((wl + wr) * 1.1 + 6) / 2 / G + 0.5) * G   # half width, snapped to the grid
    rows = max(len(left), len(right))
    top = (rows - 1) / 2 * G
    top = round(top / G) * G
    out = [f'(symbol "{name}"\n\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)']
    props = [('Reference', 'U', 0, top + 2 * G, False), ('Value', name, 0, -top - 2 * G, False),
             ('Footprint', '', 0, 0, True), ('Datasheet', '', 0, 0, True), ('Description', descr, 0, 0, True)]
    for k, v, x, y, hide in props:
        out.append(f'\t\t(property "{k}" "{v}"\n\t\t\t(at {x} {y:.2f} 0)\n\t\t\t{eff(hide=hide)}\n\t\t)')
    out.append(f'\t\t(symbol "{name}_0_1"\n\t\t\t(rectangle\n\t\t\t\t(start {-half} {top + G:.2f})\n\t\t\t\t(end {half} {-top - G:.2f})'
               f'\n\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n\t\t)')
    pins = []
    for side, lst in ((0, left), (1, right)):
        for i, (num, pname, typ) in enumerate(lst):
            x = -half - G if side == 0 else half + G
            a = 0 if side == 0 else 180
            y = top - i * G
            pins.append(f'\t\t\t(pin {typ} line\n\t\t\t\t(at {x:.2f} {y:.2f} {a})\n\t\t\t\t(length {G})\n\t\t\t\t(name "{pname}"\n\t\t\t\t\t{eff()}\n\t\t\t\t)'
                        f'\n\t\t\t\t(number "{num}"\n\t\t\t\t\t{eff()}\n\t\t\t\t)\n\t\t\t)')
    out.append(f'\t\t(symbol "{name}_1_1"\n' + '\n'.join(pins) + '\n\t\t)')
    out.append('\t\t(embedded_fonts no)\n\t)')
    return '\n'.join(out)


lib_body = {name: box_symbol(name, l, r, d) for name, (l, r, d) in SYMBOLS.items()}
with open(f'{PROJ}.kicad_sym', 'w') as f:
    f.write('(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "kicad_symbol_editor")\n\t(generator_version "10.0")\n')
    for b in lib_body.values(): f.write('\t' + b + '\n')
    f.write(')\n')

# ---------------- lib_symbols of the schematic
cache = {}
def lib_sym(lib_id):
    if lib_id in cache: return cache[lib_id]
    lib, name = lib_id.split(':')
    if lib == 'UA':
        body = lib_body[name]
    else:
        body = find_sym(open(SYSLIB + lib + '.kicad_sym').read(), name)
        if '(extends ' in body: raise SystemExit('extends not handled: ' + lib_id)
    full = f'{PROJ}:{name}' if lib == 'UA' else lib_id
    body = body.replace(f'(symbol "{name}"', f'(symbol "{full}"', 1)
    cache[lib_id] = (full, body)
    return cache[lib_id]


def pins_of(body):
    """pin number -> (x, y, angle) of the connection point (symbol coordinates, y up)"""
    return {n: (float(x), float(y), int(a)) for x, y, a, n in
            re.findall(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(number "([^"]+)"', body, re.S)}


# ---------------- placement: groups in columns, shelf packing per group
ROOT = U()
items, nc_items, labels = [], [], []
GROUPS = [('USB-COM, microSD, X101', 'X105'), ('XMOS, Takt, QSPI-Flash', 'IC114'), ('USB-Audio-Buchse, Versorgung XMOS', 'X102')]
starts = {g[1]: i for i, g in enumerate(GROUPS)}
group_of, cur = {}, 0
for p in P:
    cur = starts.get(p['ref'], cur); group_of[p['ref']] = cur

def snap(v): return round(v / G) * G

texts = []
x0 = 20.32
for gi, (title, _) in enumerate(GROUPS):
    parts = [p for p in P if group_of[p['ref']] == gi]
    gx, y, col_w, x = x0, 30.48, 0, x0
    row_h, shelf_w = 0, 230
    texts.append((title, x0, 22.86))
    for p in parts:
        full, body = lib_sym(p['sym'])
        pins = pins_of(body)
        xs = [v[0] for v in pins.values()]; ys = [v[1] for v in pins.values()]
        w = (max(xs) - min(xs)) + 45; h = (max(ys) - min(ys)) + 15
        if x + w > gx + shelf_w:
            x = gx; y += row_h; row_h = 0
        X = snap(x - min(xs) + 20); Y = snap(y + max(ys) + 7)
        p['_at'] = (X, Y, full, body, pins)
        x += w; row_h = max(row_h, h)
    x0 += shelf_w + 20

W = snap(x0 + 10); H = snap(max(p['_at'][1] for p in P) + 60)

def prop(k, v, x, y, hide=False):
    return f'\t\t(property "{k}" "{v}"\n\t\t\t(at {x:.2f} {y:.2f} 0)\n\t\t\t{eff(hide=hide)}\n\t\t)'

for p in P:
    X, Y, full, body, pins = p['_at']
    ys = [v[1] for v in pins.values()]
    lines = [f'\t(symbol\n\t\t(lib_id "{full}")\n\t\t(at {X:.2f} {Y:.2f} 0)\n\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(uuid "{U()}")',
             prop('Reference', p['ref'], X, Y - max(ys) - 3.5), prop('Value', p['val'], X, Y - min(ys) + 3.5),
             prop('Footprint', p['fp'], X, Y, True), prop('Datasheet', '', X, Y, True), prop('Description', '', X, Y, True)]
    if p['lcsc']: lines.append(prop('LCSC', p['lcsc'], X, Y, True))
    for n in pins: lines.append(f'\t\t(pin "{n}"\n\t\t\t(uuid "{U()}")\n\t\t)')
    lines.append(f'\t\t(instances\n\t\t\t(project "{PROJ}"\n\t\t\t\t(path "/{ROOT}"\n\t\t\t\t\t(reference "{p["ref"]}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)')
    items.append('\n'.join(lines))
    missing = set(pins) - set(p['pins'])
    extra = set(p['pins']) - set(pins)
    if extra: raise SystemExit(f'{p["ref"]}: pins not in symbol {sorted(extra)}')
    for n, (px, py, a) in pins.items():
        net = p['pins'].get(n, '')
        x, y = round(X + px, 2), round(Y - py, 2)
        if not net:
            nc_items.append(f'\t(no_connect\n\t\t(at {x} {y})\n\t\t(uuid "{U()}")\n\t)')
            continue
        la, j = {0: (180, 'right bottom'), 180: (0, 'left bottom'), 90: (270, 'right bottom'), 270: (90, 'left bottom')}[a]
        labels.append(f'\t(label "{net}"\n\t\t(at {x} {y} {la})\n\t\t{eff(justify=j)}\n\t\t(uuid "{U()}")\n\t)')

# power flags on the supply nets fed from outside or through a ferrite
flag_full, flag_body = lib_sym('power:PWR_FLAG')
fx = 20.32
for k, net in enumerate(['GND', '+3V3', 'COM.VBUS', 'AUD.VBUS', 'XMOS.5V0', 'XMOS.1V0', 'XMOS.PLL.VDD']):
    x, y = fx + k * 30.48, H - 25.4
    items.append(f'\t(symbol\n\t\t(lib_id "{flag_full}")\n\t\t(at {x:.2f} {y:.2f} 0)\n\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(uuid "{U()}")\n'
                 + prop('Reference', f'#FLG{k + 1:02d}', x, y - 5, True) + '\n' + prop('Value', 'PWR_FLAG', x, y - 3) + '\n'
                 + prop('Footprint', '', x, y, True) + '\n' + prop('Datasheet', '', x, y, True) + '\n' + prop('Description', '', x, y, True)
                 + f'\n\t\t(pin "1"\n\t\t\t(uuid "{U()}")\n\t\t)\n\t\t(instances\n\t\t\t(project "{PROJ}"\n\t\t\t\t(path "/{ROOT}"\n\t\t\t\t\t(reference "#FLG{k + 1:02d}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)')
    labels.append(f'\t(label "{net}"\n\t\t(at {x} {y} 0)\n\t\t{eff(justify="left bottom")}\n\t\t(uuid "{U()}")\n\t)')

note = ('Nachbau der Forge-DSP-USB-Audio-Platine V4.0i (Original: Mark Duprau, pcbs/usb/com_audio/V40i, CC BY-NC-SA 4.0).\\n'
        'Verbindungen über Netzlabels. Abweichungen vom Original sind in tools/parts.py mit PORT markiert (hardware#3).')
texts.append((note, 20.32, H - 10.16))
txt = [f'\t(text "{s}"\n\t\t(exclude_from_sim no)\n\t\t(at {x} {y} 0)\n\t\t{eff(size=2.54 if i < 3 else 1.27, justify="left bottom")}\n\t\t(uuid "{U()}")\n\t)'
       for i, (s, x, y) in enumerate(texts)]

libs = '\n'.join('\t\t' + b.replace('\n', '\n\t') for _, b in sorted(cache.values()))
out = (f'(kicad_sch\n\t(version 20260306)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n\t(uuid "{ROOT}")\n'
       f'\t(paper "User" {W} {H})\n\t(title_block\n\t\t(title "Forge DSP USB-Audio V4.0i (Nachbau)")\n\t\t(comment 1 "Original: Mark Duprau, CC BY-NC-SA 4.0")\n\t)\n'
       f'\t(lib_symbols\n{libs}\n\t)\n' + '\n'.join(txt + items + nc_items + labels) +
       '\n\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')
open(f'{PROJ}.kicad_sch', 'w').write(out)
print('ok', len(P), 'parts', W, 'x', H)
