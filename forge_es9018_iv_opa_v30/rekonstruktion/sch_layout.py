"""Schaltplan lesbar anordnen: Bauteilgruppen mit echten Drähten, Labels nur zwischen Gruppen.

Aufruf:  /usr/bin/python3 rekonstruktion/sch_layout.py <projektordner> [--png bild.png]
        /usr/bin/python3 rekonstruktion/sch_layout.py <projektordner> --pcb   (Platinen-Netze auf /NAME umbenennen)

Liest den vorhandenen Schaltplan (aus sch.py, ein Label an jedem Pin) samt Netzliste (kicad-cli) und
schreibt ihn neu:
  * OpAmps als Dreiecke je Sektion plus eigene Versorgungs-Unit (Symbol in der Projektbibliothek ersetzt)
  * Bauteile schaltungsgerecht angeordnet (I/V-Platinen: je Kanal I/V-Stufen, Filter, Differenzverstärker;
    Trägerplatine: je IC ein Block mit seinen Kondensatoren), Verbindungen innerhalb einer Gruppe als Drähte
    (A*-Router auf 1,27-mm-Raster)
  * Versorgung (GND, AGND, +12V, 3V3 ...) als Power-Symbole, globale Labels nur für Netze zwischen Gruppen;
    verdrahtete Netze tragen ihren Namen als ein Label, damit die Netznamen zur Platine passen
Symbol- und Pin-UUIDs bleiben erhalten (Verknüpfung zur Platine). Am Ende wird die Netzliste mit der alten
verglichen; jede Abweichung wird gemeldet.
"""
import sys, os, re, math, heapq, subprocess, uuid, collections, tempfile, shutil
import xml.etree.ElementTree as ET

G = 1.27
NS = uuid.UUID('7c3f1a52-1d2e-4b9a-8f00-5c1e0a9b7d21')
def U(s): return str(uuid.uuid5(NS, s))
def q(s): return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'
def mm(v): return round(v * G, 4)
HIDE = '(effects (font (size 1.27 1.27)) (hide yes))'
F127 = '(effects (font (size 1.27 1.27)))'

# ------------------------------------------------------------------ S-Ausdrücke
def tokens(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in '()': yield c; i += 1
        elif c.isspace(): i += 1
        elif c == '"':
            j = i + 1; buf = []
            while s[j] != '"':
                if s[j] == '\\': buf.append(s[j + 1]); j += 2
                else: buf.append(s[j]); j += 1
            yield ('S', ''.join(buf)); i = j + 1
        else:
            j = i
            while j < n and not s[j].isspace() and s[j] not in '()': j += 1
            yield s[i:j]; i = j

def parse(s):
    st = [[]]
    for t in tokens(s):
        if t == '(': st.append([])
        elif t == ')': x = st.pop(); st[-1].append(x)
        else: st[-1].append(t)
    return st[0][0]

def val(t): return t[1] if isinstance(t, tuple) else t
def kids(node, name): return [x for x in node if isinstance(x, list) and x and x[0] == name]
def kid(node, name):
    k = kids(node, name); return k[0] if k else None

def block_end(s, i):
    d = 0; qq = False; k = i
    while True:
        c = s[k]
        if c == '"' and s[k - 1] != '\\': qq = not qq
        elif not qq:
            if c == '(': d += 1
            elif c == ')':
                d -= 1
                if d == 0: return k + 1
        k += 1

def sym_blocks(text):
    """Top-Level-(symbol ...)-Blöcke eines lib_symbols- oder kicad_symbol_lib-Texts: {name: (start, end)}"""
    out = {}; i = 0
    depth0 = text.index('(') + 1
    k = depth0
    while True:
        m = re.compile(r'\(symbol "([^"]+)"').search(text, k)
        if not m: break
        e = block_end(text, m.start()); out[m.group(1)] = (m.start(), e); k = e
    return out

# ------------------------------------------------------------------ Geometrie (Rastereinheiten 1,27 mm, y nach unten)
DIRS = {'R': (1, 0), 'L': (-1, 0), 'D': (0, 1), 'U': (0, -1)}
def rot_vec(v, r):        # r in Grad, Drehung gegen den Uhrzeigersinn auf dem Bildschirm (KiCad-Konvention)
    x, y = v
    for _ in range((r // 90) % 4): x, y = y, -x
    return (x, y)
def xform(v, r, mirror):
    x, y = rot_vec(v, r)
    if mirror == 'x': y = -y
    elif mirror == 'y': x = -x
    return (x, y)

class LibSym:
    def __init__(self, node):
        self.name = val(node[1]); self.power = bool(kid(node, 'power'))
        self.units = collections.defaultdict(dict)        # unit -> {num: (x, y, out)}
        self.ubody = collections.defaultdict(lambda: [1e9, 1e9, -1e9, -1e9])
        for sub in kids(node, 'symbol'):
            m = re.match(r'.*_(\d+)_(\d+)$', val(sub[1])); unit = int(m.group(1))
            for it in sub:
                if not isinstance(it, list): continue
                if it[0] == 'pin':
                    at = kid(it, 'at'); x, y, a = float(at[1]), float(at[2]), int(float(at[3]))
                    num = val(kid(it, 'number')[1])
                    out = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[a]
                    self.units[unit][num] = (round(x / G), round(-y / G), out)
                    continue
                pts = []
                for pt in it:
                    if isinstance(pt, list) and pt and pt[0] in ('start', 'end', 'mid', 'center'): pts.append((float(pt[1]), -float(pt[2])))
                    if isinstance(pt, list) and pt and pt[0] == 'pts':
                        for p in kids(pt, 'xy'): pts.append((float(p[1]), -float(p[2])))
                b = self.ubody[unit]
                for x, y in pts:
                    b[0] = min(b[0], x / G); b[1] = min(b[1], y / G); b[2] = max(b[2], x / G); b[3] = max(b[3], y / G)
        nu = [u for u in self.units if u > 0] or [1]
        self.nunits = max(nu)
        for u in range(1, self.nunits + 1):
            self.units[u].update(self.units.get(0, {}))
            b0 = self.ubody.get(0); b = self.ubody[u]
            if b0:
                b[0] = min(b[0], b0[0]); b[1] = min(b[1], b0[1]); b[2] = max(b[2], b0[2]); b[3] = max(b[3], b0[3])
            if b[0] > b[2]: self.ubody[u] = [0, 0, 0, 0]
        self.pins = {}
        for u in range(1, self.nunits + 1):
            for n in self.units[u]: self.pins.setdefault(n, u)

class Part:
    def __init__(self, node, libs):
        self.lib_id = val(kid(node, 'lib_id')[1]); self.lib = libs[self.lib_id]
        self.uuid = val(kid(node, 'uuid')[1])
        self.props = collections.OrderedDict((val(p[1]), val(p[2])) for p in kids(node, 'property'))
        self.ref = self.props['Reference']; self.value = self.props.get('Value', '')
        self.pin_uuid = {val(p[1]): val(kid(p, 'uuid')[1]) for p in kids(node, 'pin')}
        inst = kid(node, 'instances'); pr = kid(inst, 'project'); path = kid(pr, 'path')
        self.project = val(pr[1]); self.path = val(path[1])
        self.flags = collections.OrderedDict((k, kid(node, k)[1]) for k in ('exclude_from_sim', 'in_bom', 'on_board', 'dnp') if kid(node, k))
        self.two = len(self.lib.pins) <= 2

class Inst:
    """platzierte Unit eines Bauteils"""
    def __init__(self, part, unit, pos, rot=0, mirror=None, region=None):
        self.part = part; self.unit = unit; self.pos = pos; self.rot = rot; self.mirror = mirror; self.region = region
    @property
    def pins(self): return self.part.lib.units[self.unit]
    def pin_end(self, num):
        x, y, out = self.pins[num]; dx, dy = xform((x, y), self.rot, self.mirror)
        return (self.pos[0] + dx, self.pos[1] + dy), xform(out, self.rot, self.mirror)
    def bbox(self):
        b = self.part.lib.ubody[self.unit]
        pts = [xform((b[0], b[1]), self.rot, self.mirror), xform((b[2], b[3]), self.rot, self.mirror)]
        x0 = math.floor(min(p[0] for p in pts) + 1e-6); x1 = math.ceil(max(p[0] for p in pts) - 1e-6)
        y0 = math.floor(min(p[1] for p in pts) + 1e-6); y1 = math.ceil(max(p[1] for p in pts) - 1e-6)
        return (self.pos[0] + x0, self.pos[1] + y0, self.pos[0] + x1, self.pos[1] + y1)
    def horiz(self): return self.part.two and self.rot % 180 == 90

POWER_RE = re.compile(r'^([AD]?GND\w*|GND.*|[+-]?\d+V\d*.*|VCC.*|VDD.*|VEE.*|VSS.*|AVCC.*|DVCC.*)$', re.I)
def is_power(n): return bool(n) and bool(POWER_RE.match(n)) and not n.startswith(('unconnected', 'Net-('))
def is_gnd(n): return 'GND' in n.upper() or n.upper().startswith('VSS')

# ------------------------------------------------------------------ Belegungsraster und Router
class Grid:
    def __init__(self):
        self.block = {}     # Zelle -> None (gesperrt) oder Zusatzkosten
        self.node = {}      # Zelle -> Netz (Pin-Ende, Knick, Endpunkt, Label-/Symbolanschluss)
        self.wire = {}      # Zelle -> {'H'|'V': Netz}
    def rect(self, b, cost=None):
        for x in range(b[0], b[2] + 1):
            for y in range(b[1], b[3] + 1):
                if cost is None: self.block[(x, y)] = None
                elif self.block.get((x, y), 0) is not None: self.block[(x, y)] = max(self.block.get((x, y), 0), cost)

def route(grid, net, srcs, tgts, bounds, limit=1500000):
    x0, y0, x1, y1 = bounds
    tg = {}
    for c, d in tgts: tg.setdefault(c, set()).add(d)
    tl = list(tg)
    def hcost(c): return min(abs(c[0] - t[0]) + abs(c[1] - t[1]) for t in tl) if len(tl) < 60 else 0
    pq = []; best = {}; prev = {}
    for c, d in srcs:
        for k in ([d] if d else list(DIRS)):
            st = (c, k); best[st] = 0; prev[st] = None
            heapq.heappush(pq, (hcost(c), 0, c, k))
    n_exp = 0
    while pq:
        f, g_, c, k = heapq.heappop(pq)
        if best.get((c, k), 1e18) < g_: continue
        n_exp += 1
        if n_exp > limit: return None
        for k2, (dx, dy) in DIRS.items():
            if DIRS[k2] == (-DIRS[k][0], -DIRS[k][1]): continue
            n2 = (c[0] + dx, c[1] + dy)
            if not (x0 <= n2[0] <= x1 and y0 <= n2[1] <= y1): continue
            bend = k2 != k
            if bend:
                if prev[(c, k)] is None and srcs and any(c == s and d is not None for s, d in srcs): continue
                w = grid.wire.get(c, {})
                if any(nn != net for nn in w.values()): continue
                if grid.block.get(c, 0) is None and prev[(c, k)] is not None: continue
            ori = 'H' if dx else 'V'
            cost = 1 + (5 if bend else 0)
            w2 = grid.wire.get(n2, {})
            arrive = n2 in tg and (None in tg[n2] or k2 in tg[n2]) and w2.get(ori) in (None, net)
            nd = grid.node.get(n2)
            if nd is not None and nd != net: continue
            if nd == net and not arrive: continue
            if not arrive:
                bl = grid.block.get(n2, 0)
                if bl is None: continue
                cost += bl
                if w2.get(ori) is not None: continue
                if w2: cost += 3
            st = (n2, k2); ng = g_ + cost
            if ng < best.get(st, 1e18):
                best[st] = ng; prev[st] = (c, k)
                if arrive:
                    path = [n2]; s_ = (c, k)
                    while s_ is not None: path.append(s_[0]); s_ = prev[s_]
                    return path[::-1]
                heapq.heappush(pq, (ng + hcost(n2), ng, n2, k2))
    return None

def segments(path):
    segs = []; s = path[0]
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1], path[i], path[i + 1]
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]): segs.append((s, b)); s = b
    segs.append((s, path[-1]))
    return [sg for sg in segs if sg[0] != sg[1]]

def cells(a, b):
    if a[0] == b[0]:
        s = 1 if b[1] >= a[1] else -1; return [(a[0], y) for y in range(a[1], b[1] + s, s)]
    s = 1 if b[0] >= a[0] else -1; return [(x, a[1]) for x in range(a[0], b[0] + s, s)]

# ------------------------------------------------------------------ Schaltplan-Kontext
class Sheet:
    def __init__(self, proj):
        self.proj = os.path.abspath(proj); self.name = os.path.basename(self.proj)
        self.schf = os.path.join(self.proj, self.name + '.kicad_sch')
        self.src = open(self.schf).read()
        tree = parse(self.src)
        li = self.src.index('(lib_symbols'); self.lib_span = (li, block_end(self.src, li))
        self.libs = {val(s[1]): LibSym(s) for s in kids(kid(tree, 'lib_symbols'), 'symbol')}
        seen = {}
        for s in kids(tree, 'symbol'):
            lid = val(kid(s, 'lib_id')[1])
            if self.libs[lid].power: continue
            p = Part(s, self.libs)
            if p.ref in seen:     # weitere Unit: UUIDs merken
                seen[p.ref].pin_uuid.update(p.pin_uuid); continue
            seen[p.ref] = p
        self.P = seen
        self.netof, self.members = self.netlist()
        self.orig = {n: frozenset(m) for n, m in self.members.items()}
        self.insts = []; self.labels = []; self.pwr = []; self.wires = []; self.junc = set(); self.nc = []
        self.texts = []; self.grid = Grid(); self.lib_replace = {}
        self.conn = []          # (Netz, Region, Liste Knoten) -> zu verdrahten
        self.vnodes = collections.defaultdict(list)    # (Netz, Region) -> [(Zelle, Ankunftsrichtung)]
        self.failed = []; self.ptasks = []

    def netlist(self, f=None):
        tmp = tempfile.mkdtemp()
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', tmp + '/n.xml', f or self.schf], check=True, capture_output=True)
        X = ET.parse(tmp + '/n.xml'); shutil.rmtree(tmp)
        netof = {}; members = collections.defaultdict(list)
        for n in X.getroot().iter('net'):
            nm = n.get('name').lstrip('/')
            if nm.startswith('unconnected-'): continue
            for nd in n.iter('node'):
                if nd.get('ref', '').startswith('#'): continue
                netof[(nd.get('ref'), nd.get('pin'))] = nm; members[nm].append((nd.get('ref'), nd.get('pin')))
        return netof, members

    # ---------- Abfragen
    def net(self, ref, pin): return self.netof.get((ref, pin))
    def nets_of(self, ref): return {self.net(ref, n) for n in self.P[ref].lib.pins} - {None}
    def between(self, a, b):
        """Zweipoler zwischen Netz a und Netz b (b darf 'PWR' für irgendein Versorgungsnetz sein)"""
        res = []
        for ref, p in self.P.items():
            if not p.two: continue
            ns = [self.net(ref, n) for n in sorted(p.lib.pins)]
            if a in ns:
                o = [x for x in ns if x != a] or [a]
                if (b == 'PWR' and is_power(o[0])) or o[0] == b: res.append(ref)
        return sorted(res, key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0)))
    def placed(self, ref): return any(i.part.ref == ref for i in self.insts)

    # ---------- Platzieren (Rastereinheiten)
    def place(self, ref, pos, rot=0, mirror=None, unit=1, region='main'):
        p = self.P[ref]; it = Inst(p, unit, pos, rot, mirror, region); self.insts.append(it)
        b = it.bbox()
        if p.two:
            self.grid.rect((b[0] + (1 if it.horiz() else 0), b[1] + (0 if it.horiz() else 1), b[2] - (1 if it.horiz() else 0), b[3] - (0 if it.horiz() else 1)))
        else:
            self.grid.rect(b)
            if len(it.pins) > 3:     # Randstreifen um IC-Körper: Drähte nicht dicht an fremden Pin-Enden entlang
                for x in range(b[0] - 3, b[2] + 4):
                    for y in range(b[1] - 3, b[3] + 4):
                        if b[0] <= x <= b[2] and b[1] <= y <= b[3]: continue
                        if self.grid.block.get((x, y), 0) is not None: self.grid.block[(x, y)] = max(self.grid.block.get((x, y), 0), 4)
        for num in it.pins:
            e, d = it.pin_end(num)
            self.grid.block.pop(e, None)
            # Pinlinie zwischen Körper und Pin-Ende sperren
            x, y, _ = it.pins[num]
            n = self.net(ref, num)
            self.grid.node[e] = n or ('NC', ref, num)
        self.text_reserve(it)
        return it
    def text_reserve(self, it):
        x0, y0, x1, y1 = it.bbox(); p = it.part
        if p.two:
            L = max(len(p.ref), len(p.value)) * 0.8
            if it.horiz():
                cx = (x0 + x1) // 2; hw = int(L / 2) + 1
                self.grid.rect((cx - hw, y0 - 2, cx + hw, y0 - 1), 2); self.grid.rect((cx - hw, y1 + 1, cx + hw, y1 + 2), 2)
            else: self.grid.rect((x1 + 1, y0, x1 + 1 + int(L), y1), 2)
        elif len(it.pins) == 3:
            self.grid.rect((x0, y1 + 1, x0 + 10, y1 + 4), 2)
        else:
            self.grid.rect((x0, y0 - 2, x1, y0 - 1), 2); self.grid.rect((x0, y1 + 1, x1, y1 + 2), 2)

    def h(self, ref, pos, left_net=None, region='main'):
        """Zweipoler waagerecht; der Pin auf left_net zeigt nach links"""
        p = self.P[ref]; pins = sorted(p.lib.pins)
        rot = 90
        if left_net is not None and self.net(ref, pins[0]) != left_net: rot = 270
        return self.place(ref, pos, rot, region=region)
    def v(self, ref, pos, top_net=None, region='main'):
        p = self.P[ref]; pins = sorted(p.lib.pins)
        rot = 0
        if top_net is not None and self.net(ref, pins[0]) != top_net: rot = 180
        return self.place(ref, pos, rot, region=region)

    def label(self, net, cell, d, region='main'):
        """globales Label an cell, Text läuft in Richtung d"""
        self.labels.append((net, cell, d)); self.grid.node[cell] = net
        L = int(len(net) * 0.85) + 3
        for i in range(1, L + 1):
            for s in (-1, 0, 1):
                c = (cell[0] + d[0] * i + s * abs(d[1]), cell[1] + d[1] * i + s * abs(d[0]))
                self.grid.block[c] = None
        self.vnodes[(net, region)].append((cell, vname(d)))
    def power(self, net, cell, d, region='main', connect=True):
        """Power-Symbol: Anschluss an cell, Symbol zeigt in Richtung d"""
        self.pwr.append((net, cell, d)); self.grid.node[cell] = net
        for i in range(1, 4):
            for s in (-1, 0, 1):
                self.grid.block[(cell[0] + d[0] * i + s * abs(d[1]), cell[1] + d[1] * i + s * abs(d[0]))] = None
        if connect: self.vnodes[(net, region)].append((cell, vname(d)))
    def wire(self, a, b, net):
        self.wires.append((a, b, net))
        cs = cells(a, b)
        o = 'H' if a[1] == b[1] else 'V'
        for c in cs: self.grid.wire.setdefault(c, {})[o] = net
        self.grid.node[a] = net; self.grid.node[b] = net
    def pin_power(self, it, num, stub=None, d=None):
        """Versorgungs-Pin: kurze Stichleitung und Power-Symbol in Pinrichtung"""
        n = self.net(it.part.ref, num); e, out = it.pin_end(num)
        d = d or out
        stub = (1 if it.part.two else 2) if stub is None else stub
        a = (e[0] + d[0] * stub, e[1] + d[1] * stub)
        if a != e: self.wire(e, a, n)
        self.pwr.append((n, a, d)); self.grid.node[a] = n
        for i in range(1, 4):
            for s in (-1, 0, 1):
                self.grid.block[(a[0] + d[0] * i + s * abs(d[1]), a[1] + d[1] * i + s * abs(d[0]))] = None
    def pin_label(self, it, num, stub=2):
        n = self.net(it.part.ref, num); e, d = it.pin_end(num)
        a = (e[0] + d[0] * stub, e[1] + d[1] * stub)
        self.wire(e, a, n)
        self.labels.append((n, a, d))
        L = int(len(n) * 0.85) + 3
        for i in range(1, L + 1):
            for s in (-1, 0, 1):
                self.grid.block[(a[0] + d[0] * i + s * abs(d[1]), a[1] + d[1] * i + s * abs(d[0]))] = None
    def auto_power_nc(self):
        """alle noch freien Versorgungs-Pins mit Symbol, unbeschaltete mit NC"""
        used = {(a, n) for n, a, _ in self.pwr}
        for it in self.insts:
            for num in it.pins:
                n = self.net(it.part.ref, num); e, d = it.pin_end(num)
                if not n: self.nc.append(e); continue
                if is_power(n) and not self.has_wire(e) and not any(a == e for _, a, _ in self.pwr): self.pin_power(it, num)
    def has_wire(self, c):
        return any(c in (a, b) for a, b, _ in self.wires)

    # ---------- Verdrahten
    def route_all(self, margin=25, insts=None, wire_from=0, vkeys=None):
        insts = self.insts if insts is None else insts
        allc = list(self.grid.block) + list(self.grid.node)
        bounds = (min(c[0] for c in allc) - margin, min(c[1] for c in allc) - margin, max(c[0] for c in allc) + margin, max(c[1] for c in allc) + margin)
        tasks = collections.defaultdict(list)
        for it in insts:
            for num in it.pins:
                n = self.net(it.part.ref, num)
                if not n or is_power(n): continue
                e, d = it.pin_end(num)
                tasks[(n, it.region)].append((e, d))
        for key, vn in self.vnodes.items():
            if is_power(key[0]) or (vkeys is not None and key not in vkeys): continue
            for c, dn in vn: tasks[key].append((c, ('V', dn)))
        for k, (n, nodes) in enumerate(getattr(self, 'ptasks', [])):
            tasks[(n, ('P', k, id(self.grid)))] = list(nodes)
        self.ptasks = []
        exist = collections.defaultdict(list)
        for a, b, n in self.wires[wire_from:]: exist[n].append((a, b))
        def spread(v):
            xs = [c[0] for c, _ in v]; ys = [c[1] for c, _ in v]; return max(xs) - min(xs) + max(ys) - min(ys)
        for key in sorted(tasks, key=lambda k: (len(tasks[k]), spread(tasks[k]))):
            n = key[0]; pts = tasks[key]
            # Komponenten: zusammenhängende vorhandene Drähte samt Pins darauf, sonst Einzelpins
            comps = []
            for a, b in exist.get(n, []):
                cs = set(cells(a, b)); hit = [c for c in comps if (a in c['cells'] or b in c['cells'] or c['ends'] & cs)]
                new = {'cells': cs, 'ends': {a, b}}
                for h in hit: new['cells'] |= h['cells']; new['ends'] |= h['ends']; comps.remove(h)
                comps.append(new)
            pset = {c for c, _ in pts}
            items = [{'cells': c['cells'], 'pin': None} for c in comps if c['cells'] & pset]
            for c0, d0 in pts:
                hit = [it for it in items if c0 in it['cells']]
                if hit: continue
                items.append({'cells': {c0}, 'pin': (c0, d0)})
            if len(items) < 2: continue
            items.sort(key=lambda it: -len(it['cells']))
            first = items.pop(0)
            tree = {c: ('w' if first['pin'] is None else first['pin'][1]) for c in first['cells']}
            paths = []
            while items:
                items.sort(key=lambda it: min(abs(c[0] - t[0]) + abs(c[1] - t[1]) for c in list(it['cells'])[:50] for t in list(tree)[:400]))
                it = items.pop(0)
                if it['pin']: srcs = [(it['pin'][0], depart(it['pin'][1]))]
                else: srcs = [(c, None) for c in it['cells']]
                tg = [(c, arrival(d)) for c, d in tree.items()]
                pth = route(self.grid, n, srcs, tg, bounds)
                if pth is None:
                    self.failed.append((n, next(iter(it['cells'])))); continue
                for a, b in segments(pth): self.wire(a, b, n)
                paths.append(pth)
                for c in pth[1:-1]: tree.setdefault(c, 'w')
                for c in it['cells']: tree.setdefault(c, 'w' if it['pin'] is None else it['pin'][1])
            deg = collections.Counter()
            for a, b in exist.get(n, []):
                cs = cells(a, b)
                for i, c in enumerate(cs): deg[c] += 1 if i in (0, len(cs) - 1) else 2
            for pth in paths:
                for i, c in enumerate(pth): deg[c] += 1 if i in (0, len(pth) - 1) else 2
            for c, d in pts: deg[c] += 1
            for c, k in deg.items():
                if k >= 3: self.junc.add(c)

    def name_labels(self):
        """verdrahtete Netze ohne globales Label bekommen ihren Namen als lokales Label auf dem Draht"""
        named = {n for n, _, _ in self.labels} | {n for n, _, _ in self.pwr}
        by = collections.defaultdict(list)
        for a, b, n in self.wires[getattr(self, 'name_from', 0):]: by[n].append((a, b))
        g = self.grid
        def free(c): return g.block.get(c, 0) is not None and g.block.get(c, 0) < 2 and c not in g.node and c not in g.wire
        self.nlabels = getattr(self, 'nlabels', [])
        for n, segs in sorted(by.items()):
            if n in named or is_power(n): continue
            L = int(len(n) * 0.8) + 2; best = None
            for a, b in sorted(segs, key=lambda s: -(abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))):
                if a[1] == b[1]:
                    y = a[1]
                    for x in range(min(a[0], b[0]) + 1, max(a[0], b[0])):
                        need = [(x + i, y - j) for i in range(L) for j in (1, 2)]
                        if all(free(c) for c in need): best = (n, (x, y), 0, need); break
                else:
                    x = a[0]
                    for y in range(max(a[1], b[1]) - 1, min(a[1], b[1]), -1):
                        need = [(x - j, y - i) for i in range(L) for j in (1, 2)]
                        if all(free(c) for c in need): best = (n, (x, y), 90, need); break
                if best: break
            if not best:
                a, b = segs[0]; best = (n, a, 0 if a[1] == b[1] else 90, []); print('  Namenslabel ohne Platz:', n)
            for c in best[3]: g.block[c] = None
            self.nlabels.append(best[:3])

    # ---------- Ausgabe
    def write(self, paper, title_texts):
        src = self.src; li, lj = self.lib_span
        lib = src[li:lj]
        blocks = sym_blocks(lib)
        for nm, txt in self.lib_replace.items():
            s, e = blocks[nm]; lib = lib[:s] + txt + lib[e:]; blocks = sym_blocks(lib)
        kinds = sorted({k for k in (pwr_symbol(n, d)[0] for n, _, d in self.pwr)} | ({'PWR_FLAG'} if self.pwr else set()))
        pl = open('/usr/share/kicad/symbols/power.kicad_sym').read(); pb = sym_blocks(pl)
        add = []
        for k in kinds:
            if 'power:' + k in blocks: continue
            s, e = pb[k]; add.append('    ' + pl[s:e].replace('(symbol "%s"' % k, '(symbol "power:%s"' % k, 1))
        if add:
            k = lib.rindex(')'); lib = lib[:k].rstrip() + '\n' + '\n'.join(add) + '\n  )'
        hdr = re.sub(r'\(paper "[^"]*"\)', '(paper %s)' % q(paper), src[:li])
        L = [hdr.rstrip() + '\n  ' + lib]
        A = L.append
        proj = next(iter(self.P.values())).project
        for it in self.insts:
            p = it.part; X_, Y_ = mm(it.pos[0]), mm(it.pos[1])
            uid = p.uuid if it.unit == min(i.unit for i in self.insts if i.part is p) else U('unit%s%d' % (p.ref, it.unit))
            mir = ' (mirror %s)' % it.mirror if it.mirror else ''
            A('  (symbol (lib_id %s) (at %s %s %d)%s (unit %d) %s (uuid %s)' % (q(p.lib_id), X_, Y_, it.rot, mir, it.unit,
              ' '.join('(%s %s)' % (k, v) for k, v in p.flags.items()), q(uid)))
            b = it.bbox()
            for k, v in p.props.items():
                if k in ('Reference', 'Value'):
                    if p.two and not it.horiz():
                        px, py = mm(b[2] + 1), Y_ + (-1.27 if k == 'Reference' else 1.27)
                        just = ' (justify %s)' % ('right' if it.rot == 180 else 'left')     # KiCad spiegelt die Ausrichtung mit
                    elif p.two:
                        px, py = X_, mm(b[1] - 1) if k == 'Reference' else mm(b[3] + 1); just = ''
                    else:
                        px, py = X_, mm(b[1] - 1) if k == 'Reference' else mm(b[3] + 1); just = ''
                    sz = '1.27 1.27' if (k == 'Reference' or not p.two) else '1.0 1.0'
                    fa = 90 if (p.two and it.horiz()) else 0
                    if not p.two and len(it.pins) == 3:      # OpAmp-Sektion: Texte unter das Dreieck
                        px = mm(b[0]); py = mm(b[3] + (1.5 if k == 'Reference' else 3)); just = ' (justify left)'
                    elif not p.two and len(it.pins) == 2:    # Versorgungs-Unit: Texte rechts
                        px = mm(b[2] + 1); py = Y_ + (-1.27 if k == 'Reference' else 1.27); just = ' (justify left)'
                    A('    (property %s %s (at %s %s %d) (effects (font (size %s))%s))' % (q(k), q(v), px, py, fa, sz, just))
                else:
                    A('    (property %s %s (at %s %s 0) %s)' % (q(k), q(v), X_, Y_, HIDE))
            for num in it.pins:
                A('    (pin %s (uuid %s))' % (q(num), q(p.pin_uuid.get(num) or U('pin%s%s' % (p.ref, num)))))
            A('    (instances (project %s (path %s (reference %s) (unit %d)))))' % (q(p.project), q(p.path), q(p.ref), it.unit))
        for a, b, n in self.wires:
            A('  (wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))' % (mm(a[0]), mm(a[1]), mm(b[0]), mm(b[1]), q(U('w%s%s%s' % (a, b, n)))))
        for c in sorted(self.junc):
            A('  (junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid %s))' % (mm(c[0]), mm(c[1]), q(U('j%s' % (c,)))))
        for c in self.nc:
            A('  (no_connect (at %s %s) (uuid %s))' % (mm(c[0]), mm(c[1]), q(U('nc%s' % (c,)))))
        for n, a, d in self.labels:
            ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]
            just = 'left' if ang in (0, 90) else 'right'
            A('  (global_label %s (shape passive) (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify %s)) (uuid %s)'
              % (q(n), mm(a[0]), mm(a[1]), ang, just, q(U('gl%s%s' % (a, n)))))
            A('    (property "Intersheetrefs" "${INTERSHEET_REFS}" (at %s %s 0) %s))' % (mm(a[0]), mm(a[1]), HIDE))
        for n, a, ang in getattr(self, 'nlabels', []):
            A('  (label %s (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid %s))'
              % (q(n), mm(a[0]), mm(a[1]), ang, q(U('nl%s%s' % (a, n)))))
        # je Versorgungsnetz ein PWR_FLAG (ERC: Netz wird von außen gespeist), seitlich am Anschluss eines Power-Symbols
        flags = {}
        for n, a, d in sorted(self.pwr, key=lambda x: (x[2][0] != 0, -x[1][1], x[1][0])):
            flags.setdefault(n, (a, d))
        for k, (n, (a, d)) in enumerate(sorted(flags.items())):
            r = 90 if d[0] == 0 else 0
            x_, y_ = mm(a[0]), mm(a[1]); uid = U('flag%s' % n); ref = '#FLG%02d' % (k + 1)
            A('  (symbol (lib_id "power:PWR_FLAG") (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid %s)' % (x_, y_, r, q(uid)))
            A('    (property "Reference" %s (at %s %s 0) %s)' % (q(ref), x_, y_, HIDE))
            A('    (property "Value" "PWR_FLAG" (at %s %s 0) %s)' % (x_, y_, HIDE))
            A('    (property "Footprint" "" (at %s %s 0) %s)' % (x_, y_, HIDE))
            A('    (property "Datasheet" "" (at %s %s 0) %s)' % (x_, y_, HIDE))
            A('    (pin "1" (uuid %s))' % q(U(uid + 'p')))
            A('    (instances (project %s (path %s (reference %s) (unit 1)))))' % (q(proj), q('/' + re.search(r'\(uuid "([^"]+)"\)', src).group(1)), q(ref)))
        for k, (n, a, d) in enumerate(sorted(self.pwr, key=lambda x: (x[1][1], x[1][0]))):
            kind, r = pwr_symbol(n, d)
            x_, y_ = mm(a[0]), mm(a[1]); ref = '#PWR%03d' % (k + 1); uid = U('pwr%s%s' % (a, n))
            tv = xform((0, 4 if kind == 'GND' else (-4 if kind == 'VCC' else 4)), r, None)
            A('  (symbol (lib_id %s) (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid %s)'
              % (q('power:' + kind), x_, y_, r, q(uid)))
            A('    (property "Reference" %s (at %s %s 0) %s)' % (q(ref), x_, y_, HIDE))
            crowd = d[0] == 0 and any(b_ != a and b_[1] == a[1] and abs(b_[0] - a[0]) <= 3 for _, b_, _ in self.pwr)
            if crowd:     # dicht nebeneinander (IC-Ober-/Unterseite): Wert senkrecht, damit sich die Texte nicht überlagern
                A('    (property "Value" %s (at %s %s %d) (effects (font (size 1.0 1.0)) (justify %s)))' % (q(n), mm(a[0]), mm(a[1] + d[1] * 4), 90 if r % 180 == 0 else 0, 'left' if d[1] < 0 else 'right'))
            else:
                A('    (property "Value" %s (at %s %s %d) (effects (font (size 1.0 1.0))))' % (q(n), mm(a[0] + tv[0]), mm(a[1] + tv[1]), 90 if r % 180 else 0))
            A('    (property "Footprint" "" (at %s %s 0) %s)' % (x_, y_, HIDE))
            A('    (property "Datasheet" "" (at %s %s 0) %s)' % (x_, y_, HIDE))
            A('    (pin "1" (uuid %s))' % q(U(uid + 'p')))
            A('    (instances (project %s (path %s (reference %s) (unit 1)))))' % (q(proj), q('/' + re.search(r'\(uuid "([^"]+)"\)', src).group(1)), q(ref)))
        for k, (txt, size, at) in enumerate(title_texts):
            A('  (text %s (at %s %s 0) (effects (font (size %s %s)) (justify left)) (uuid %s))' % (q(txt), at[0], at[1], size, size, q(U('t%d' % k))))
        A('  (sheet_instances (path "/" (page "1")))')
        A(')')
        self.out = '\n'.join(L) + '\n'

    def check_and_save(self):
        tmpd = tempfile.mkdtemp(); f = os.path.join(tmpd, self.name + '.kicad_sch')
        open(f, 'w').write(self.out)
        for x in ('sym-lib-table', 'fp-lib-table', self.name + '.kicad_pro'):
            if os.path.exists(os.path.join(self.proj, x)): shutil.copy(os.path.join(self.proj, x), tmpd)
        for x in os.listdir(self.proj):
            if x.endswith('.kicad_sym'): shutil.copy(os.path.join(self.proj, x), tmpd)
        _, mem = self.netlist(f); shutil.rmtree(tmpd)
        new = {n: frozenset(m) for n, m in mem.items()}
        bad = [(k, sorted(v - new.get(k, frozenset())), sorted(new.get(k, frozenset()) - v)) for k, v in self.orig.items() if new.get(k) != v]
        extra = [(k, sorted(v)) for k, v in new.items() if k not in self.orig]
        return bad, extra

def vname(d): return [k for k, v in DIRS.items() if v == d][0]
def depart(d):
    if isinstance(d, tuple) and d and d[0] == 'V': return {'R': 'L', 'L': 'R', 'U': 'D', 'D': 'U'}[d[1]]   # Label: Draht kommt von hinten
    return vname(d)
def arrival(d):
    if d == 'w': return None
    if isinstance(d, tuple) and d and d[0] == 'V': return d[1]
    return {'R': 'L', 'L': 'R', 'U': 'D', 'D': 'U'}[vname(d)]
def pwr_symbol(n, d):
    """(Symbolname, Drehung) so, dass das Symbol in Richtung d zeigt"""
    if is_gnd(n): kind, nat = 'GND', (0, 1)
    elif d == (0, 1) and n.startswith('-'): kind, nat = 'VEE', (0, 1)
    else: kind, nat = 'VCC', (0, -1)
    r = [r for r in (0, 90, 180, 270) if rot_vec(nat, r) == d][0]
    return kind, r

# ------------------------------------------------------------------ OpAmp-Symbole (Dreieck je Sektion)
OPA = {'OPA_DUAL': {1: 'OUTA', 2: '-INA', 3: '+INA', 4: 'V-', 5: '+INB', 6: '-INB', 7: 'OUTB', 8: 'V+'},
       'OPA_QUAD': {1: 'OUTA', 2: '-INA', 3: '+INA', 4: 'V+', 5: '+INB', 6: '-INB', 7: 'OUTB',
                    8: 'OUTC', 9: '-INC', 10: '+INC', 11: 'V-', 12: '+IND', 13: '-IND', 14: 'OUTD'}}

def ic_lib(libname, name, pins, desc):
    """IC-Kasten in Gehäuse-Pinfolge: links 1..n/2 von oben, rechts n..n/2+1 von oben (wie SOIC/DIP)"""
    n = len(pins); h = n // 2
    top = (h - 1) * 2.54 / 2; half = top + 2.54; w = 7.62
    o = ['  (symbol %s (pin_names (offset 0.762)) (exclude_from_sim no) (in_bom yes) (on_board yes)' % q(libname + name)]
    o.append('    (property "Reference" "U" (at 0 %s 0) %s)' % (round(half + 1.27, 3), F127))
    o.append('    (property "Value" %s (at 0 %s 0) %s)' % (q(name), round(-half - 1.27, 3), F127))
    o.append('    (property "Footprint" "" (at 0 0 0) %s)' % HIDE)
    o.append('    (property "Datasheet" "" (at 0 0 0) %s)' % HIDE)
    o.append('    (property "Description" %s (at 0 0 0) %s)' % (q(desc), HIDE))
    o.append('    (symbol %s' % q(name + '_0_1'))
    o.append('      (rectangle (start %s %s) (end %s %s) (stroke (width 0.254) (type default)) (fill (type background)))' % (-w, round(half, 3), w, round(-half, 3)))
    o.append('    )')
    o.append('    (symbol %s' % q(name + '_1_1'))
    for k in range(1, n + 1):
        if k <= h: x, y, a = -w - 2.54, top - (k - 1) * 2.54, 0
        else: x, y, a = w + 2.54, top - (n - k) * 2.54, 180
        o.append('      (pin passive line (at %s %s %d) (length 2.54) (name %s %s) (number %s %s))' % (round(x, 3), round(y, 3), a, q(pins[k]), F127, q(str(k)), F127))
    o.append('    )')
    o.append('  )')
    return '\n'.join(o)

def convert_opamps(S):
    """OpAmps als IC-Kasten mit allen Pins in Gehäusefolge; Bibliotheksdatei des Projekts mitziehen"""
    for lid, lib in list(S.libs.items()):
        nm = lid.split(':')[-1]
        if nm not in OPA: continue
        libname = lid.split(':')[0]
        desc = '%s-OpAmp im %d-poligen Gehäuse (Pinfolge wie SOIC/DIP)' % ('Dual' if nm == 'OPA_DUAL' else 'Quad', len(OPA[nm]))
        txt = ic_lib(libname + ':', nm, OPA[nm], desc)
        S.lib_replace[lid] = txt.strip()
        S.libs[lid] = LibSym(parse(txt))
        for p in S.P.values():
            if p.lib_id == lid: p.lib = S.libs[lid]
        lf = os.path.join(S.proj, libname + '.kicad_sym')
        S.libfile_new = getattr(S, 'libfile_new', {})
        if os.path.exists(lf):
            t = S.libfile_new.get(lf) or open(lf).read(); bl = sym_blocks(t)
            if nm in bl:
                a_, e_ = bl[nm]; t = t[:a_] + ic_lib('', nm, OPA[nm], desc).strip() + t[e_:]
                S.libfile_new[lf] = t

def hide_twopin(S):
    for lid, lib in S.libs.items():
        if lib.power or len(lib.pins) != 2: continue
        li, lj = S.lib_span; lt = S.src[li:lj]; bl = sym_blocks(lt)
        if lid not in bl: continue
        t = lt[bl[lid][0]:bl[lid][1]]
        PAT = r'\(pin_names \(offset [\d.]+\)\)'; NEW = '(pin_names (offset 0.254) (hide yes))'
        if not re.search(PAT, t[:300]): continue
        t2 = re.sub(PAT, NEW, t, count=1)
        S.lib_replace[lid] = t2
        libname, nm = lid.split(':')
        lf = os.path.join(S.proj, libname + '.kicad_sym')
        S.libfile_new = getattr(S, 'libfile_new', {})
        tt = S.libfile_new.get(lf) or (open(lf).read() if os.path.exists(lf) else None)
        if tt and nm in sym_blocks(tt):
            a, b = sym_blocks(tt)[nm]
            S.libfile_new[lf] = tt[:a] + re.sub(PAT, NEW, tt[a:b], count=1) + tt[b:]

def board_pads(S):
    """Pad-Positionen (mm) und Netze je Bauteil aus rekonstruktion/model.json"""
    import json
    f = os.path.join(S.proj, 'rekonstruktion', 'model.json')
    if not os.path.exists(f): return {}
    M = json.load(open(f))
    return {c['ref']: [(p['net'], (p['x'], p['y'])) for p in c['pads']] for c in M['comps']}

def board_pads_num(S):
    import json
    f = os.path.join(S.proj, 'rekonstruktion', 'model.json')
    if not os.path.exists(f): return {}
    M = json.load(open(f))
    return {c['ref']: [(str(p['num']), p['net'], (p['x'], p['y'])) for p in c['pads']] for c in M['comps']}

# ------------------------------------------------------------------ Hauptprogramm
def main(proj, png=None):
    S = Sheet(proj)
    convert_opamps(S)
    paper = layout_carrier(S)
    tt = re.findall(r'\(text "((?:[^"\\]|\\.)*)" \(at [^)]*\) \(effects \(font \(size ([\d.]+)', S.src)
    texts = []; y = 15.0
    for t, sz in tt:
        t = t.replace('\\"', '"').replace('Verbindungen ueber globale Netzlabels.', 'Bauteilgruppen verdrahtet, globale Labels nur zwischen Gruppen.')
        texts.append((t, sz, (15.24, round(y, 2)))); y += float(sz) * 2.2
    S.write(paper, texts)
    bad, extra = S.check_and_save()
    print('%s: Bauteile %d, Drähte %d, Labels %d, Power-Symbole %d, Papier %s, nicht geroutet %d'
          % (S.name, len(S.P), len(S.wires), len(S.labels), len(S.pwr), paper, len(S.failed)))
    for f in S.failed: print('   nicht geroutet:', f)
    print('Netzliste: %d Netze abweichend, %d zusätzlich' % (len(bad), len(extra)))
    for b in bad[:30]: print('  ', b)
    for e in extra[:30]: print('   extra', e)
    if bad or extra or S.failed:
        if '--force' not in sys.argv:
            print('NICHT gespeichert');
            if png: save_png(S, png, S.out)
            return 1
    open(S.schf, 'w').write(S.out)
    for f, t in getattr(S, 'libfile_new', {}).items(): open(f, 'w').write(t)
    if png: save_png(S, png, None)
    return 0

def rename_pcb_nets(proj):
    """Platinen-Netze an die Schaltplannamen angleichen: lokal benannte Netze heißen im Schaltplan /NAME.
    Ändert <name>.kicad_pcb und (falls vorhanden) rekonstruktion/<name>_zonen.kicad_pcb, nur (net "...")-Einträge."""
    proj = os.path.abspath(proj); name = os.path.basename(proj)
    tmp = tempfile.mkdtemp()
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', tmp + '/n.xml',
                    os.path.join(proj, name + '.kicad_sch')], check=True, capture_output=True)
    names = {n.get('name') for n in ET.parse(tmp + '/n.xml').getroot().iter('net')}; shutil.rmtree(tmp)
    sch = {n.lstrip('/'): n for n in names}          # Grundname -> Name im Schaltplan (mit oder ohne '/')
    for f in (os.path.join(proj, name + '.kicad_pcb'), os.path.join(proj, 'rekonstruktion', name + '_zonen.kicad_pcb')):
        if not os.path.exists(f): continue
        t = open(f).read(); cnt = 0
        def sub(m):
            nonlocal cnt
            old = m.group(1).replace('\\"', '"').replace('\\\\', '\\')
            new = sch.get(old.lstrip('/'))
            if new and new != old: cnt += 1; return '(net %s)' % q(new)
            return m.group(0)
        t2 = re.sub(r'\(net "((?:[^"\\]|\\.)*)"\)', sub, t)
        if t2 != t: open(f, 'w').write(t2)
        print('  %s: %d Netzbezüge umbenannt' % (os.path.basename(f), cnt))

def save_png(S, png, text):
    tmp = tempfile.mkdtemp(); f = S.schf
    if text is not None:
        for x in os.listdir(S.proj):
            if x.endswith(('.kicad_sym', '-lib-table', '.kicad_pro')): shutil.copy(os.path.join(S.proj, x), tmp)
        f = os.path.join(tmp, S.name + '.kicad_sch'); open(f, 'w').write(text)
    subprocess.run(['kicad-cli', 'sch', 'export', 'pdf', '-o', tmp + '/s.pdf', f], check=True, capture_output=True)
    subprocess.run(['pdftoppm', '-png', '-r', os.environ.get('DPI', '110'), '-singlefile', tmp + '/s.pdf', png[:-4]], check=True)
    shutil.rmtree(tmp)

# ------------------------------------------------------------------ Layout Trägerplatine (IC-Blöcke)
def make_groups(S):
    P = S.P
    def is_conn(r): return re.match(r'^(X|J|CN)\d', r) is not None
    anchors = [r for r, p in P.items() if (len(p.lib.pins) >= 3 and not r.startswith('TP')) or is_conn(r)]
    absorbing = [r for r in anchors if not is_conn(r)]
    pads = board_pads(S)
    cen = {r: (sum(x for _, (x, y) in v) / len(v), sum(y for _, (x, y) in v) / len(v)) for r, v in pads.items() if v}
    def bd(a, b): return math.dist(cen[a], cen[b]) if a in cen and b in cen else 1e9
    adj = collections.defaultdict(set)
    for n, m in S.members.items():
        if is_power(n) or len(m) > 6: continue
        refs = {r for r, _ in m}
        for r in refs: adj[r] |= refs - {r}
    dist = {}
    for a in absorbing:
        d = {a: 0}; fr = [a]
        while fr:
            nf = []
            for r in fr:
                for nb in adj[r]:
                    if nb in d or nb in anchors: continue
                    d[nb] = d[r] + 1; nf.append(nb)
            fr = nf
        dist[a] = d
    grp = {a: a for a in anchors}
    for r in P:
        if r in grp: continue
        cand = [(dist[a][r], bd(r, a), a) for a in absorbing if r in dist[a]]
        if cand: grp[r] = min(cand)[2]
    for r in P:
        if r in grp: continue
        ns = S.nets_of(r)
        if ns and all(is_power(n) for n in ns):
            cand = [a for a in absorbing if ns & set(S.nets_of(a))]
            big = [a for a in cand if len(P[a].lib.pins) >= 5]
            cand = big or cand
            if cand: grp[r] = min(cand, key=lambda a: bd(r, a))
    for r in P:
        if r in grp: continue
        st = [r]; grp[r] = 'G_' + r
        while st:
            x = st.pop()
            for nb in adj[x]:
                if nb not in grp and nb not in anchors: grp[nb] = grp[r]; st.append(nb)
    groups = collections.OrderedDict()
    for r in P: groups.setdefault(grp[r], []).append(r)
    return groups

def twidth(p): return int(max(len(p.ref) * 1.0, len(p.value) * 0.8)) + 3

def build_block(S, gname, members):
    g = S.grid = Grid(); reg = gname
    anchor = gname if gname in S.P else None
    gset = set(members) | ({gname} if gname in S.P else set())
    def other_net(r, n):
        ns = [S.net(r, k) for k in sorted(S.P[r].lib.pins)]
        o = [x for x in ns if x != n]; return o[0] if o else None
    def local_parts(n):
        out = []
        for r, _ in S.members.get(n, []):
            if r in gset and r != anchor and not S.placed(r) and r not in out: out.append(r)
        return out
    def spanning(n): return any(r not in gset for r, _ in S.members.get(n, [])) or len(S.members.get(n, [])) == 1
    def free(c, allow_wire=False):
        return g.block.get(c, 0) is not None and c not in g.node and (allow_wire or c not in g.wire)
    def box_free(x0, y0, x1, y1):
        return all(free((x, y)) for x in range(min(x0, x1), max(x0, x1) + 1) for y in range(min(y0, y1), max(y0, y1) + 1))
    LS = {}
    def small2(p):    # echter Zweipoler (R/C), keine Box mit zwei Pins (Testpunkte)
        b = p.lib.ubody[1]; return len(p.lib.pins) == 2 and b[2] - b[0] <= 4
    labeled = set()
    def branches(n):
        """Ketten von Zweipolern ab Netz n (über Netze mit genau zwei Teilnehmern): [(Kette, Endnetz)]"""
        out = []
        for r in local_parts(n):
            if len(S.P[r].lib.pins) != 2: continue
            chain = [r]; cur = other_net(r, n)
            while cur and not is_power(cur) and len(S.members.get(cur, [])) == 2:
                nxt = [x for x, _ in S.members[cur] if x not in chain and x in gset and x != anchor and not S.placed(x)]
                if len(nxt) != 1 or len(S.P[nxt[0]].lib.pins) != 2: break
                chain.append(nxt[0]); cur = other_net(nxt[0], cur)
            out.append((chain, cur))
        return out
    def hplace(r, cx, y, near, d):
        return S.h(r, (cx, y), near if d[0] > 0 else other_net(r, near), reg)
    def put_chain(chain, n, xs, y, d):
        """Kette waagerecht ab Spalte xs nach außen; liefert (letzte Instanz, deren Endpin, Endspalte)"""
        near = n; inst = None
        for r in chain:
            p = S.P[r]
            hw = max(4, twidth(p) // 2 + 1)
            for k in range(0, 40):
                cx = xs + d[0] * (3 + 2 * k)
                if box_free(cx - hw, y - 3, cx + hw, y + 3): break
            inst = hplace(r, cx, y, near, d)
            near = other_net(r, near); xs = cx + d[0] * 3 + d[0] * 7
        endpin = [k for k in inst.pins if S.net(inst.part.ref, k) == near]
        return inst, (endpin[0] if endpin else None), xs - d[0] * 7
    def node(n, x, y, d, sdir, depth=0):
        """alles, was an Netz n hängt, ab Punkt (x, y) nach außen (d) bzw. in Zeilen Richtung sdir anordnen;
        liefert die belegte Ausdehnung in sdir-Richtung"""
        br = branches(n)
        shunts = [b for b in br if len(b[0]) == 1 and b[1] and is_power(b[1]) and small2(S.P[b[0][0]])]
        series = [b for b in br if b not in shunts]
        ext = 0; cx = x + d[0] * 3
        for (c, m) in shunts:
            r = c[0]; tw = twidth(S.P[r]); down = is_gnd(m) or m.startswith('-')
            for k in range(0, 60):
                xx = cx + d[0] * 2 * k
                rows = (y + 1, y + 11) if down else (y - 11, y - 1)
                if box_free(xx - 1, rows[0], xx + tw, rows[1]): break
            ci = S.v(r, (xx, y + 3) if down else (xx, y - 3), n if down else m, reg)
            for k2 in ci.pins:
                if S.net(r, k2) == m: S.pin_power(ci, k2)
            cx = xx + (tw + 3 if d[0] > 0 else -(tw + 3))
            if (down and sdir > 0) or (not down and sdir < 0): ext = max(ext, 11)
        row = 0
        for j, (c, m) in enumerate(series):
            if j == 0: yy, xs = y, cx
            else:
                row += 1; yy = y + sdir * (max(ext, 2) + 4 * row); xs = x + d[0] * 2
            inst, ep, xe = put_chain(c, n, xs, yy, d)
            if m is None or ep is None: continue
            if is_power(m): S.pin_power(inst, ep)
            elif spanning(m) and m not in labeled and not branches(m): S.pin_label(inst, ep); labeled.add(m)
            elif depth < 3:
                e2, _ = inst.pin_end(ep)
                sub = node(m, e2[0], yy, d, sdir, depth + 1)
                if sub: row += sub // 4 + 1
            ext = max(ext, abs(yy - y) + 2)
        if spanning(n) and n not in labeled:
            L = int(len(n) * 0.85) + 3
            cands = ([(cx + d[0], y)] if not series else []) + [(x + d[0] * 3, y + sdir * (max(ext, 2) + 2 * k)) for k in range(2, 40)]
            for a in cands:
                if box_free(min(a[0], a[0] + d[0] * L), a[1] - 1, max(a[0], a[0] + d[0] * L), a[1] + 1): break
            S.label(n, a, d, reg); ext = max(ext, abs(a[1] - y) + 2)
            labeled.add(n)
        return ext
    def fb_paths(i, o):
        res = []
        for r in local_parts(i):
            if len(S.P[r].lib.pins) != 2: continue
            m = other_net(r, i)
            if m == o: res.append([r]); continue
            if m and not is_power(m) and len(S.members.get(m, [])) == 2:
                r2 = [x for x, _ in S.members[m] if x != r][0]
                if r2 in gset and not S.placed(r2) and other_net(r2, m) == o: res.append([r, r2])
        return sorted(res, key=len)
    def opamp_sections(it):
        names = OPA[it.part.lib_id.split(':')[-1]]; secs = {}
        for k, pn in names.items():
            mt = re.match(r'(OUT|-IN|\+IN)([A-D])$', pn)
            if mt: secs.setdefault(mt.group(2), {})[mt.group(1)] = str(k)
        handled = set(); todo = []
        for sname, pins in sorted(secs.items()):     # 1. Durchgang: Rückkopplungen (feste Lage an den Pins)
            po = pins['OUT']; o = S.net(anchor, po)
            if not o: continue
            ins = [pins['-IN'], pins['+IN']]
            pf = [k for k in ins if fb_paths(S.net(anchor, k), o)]
            pfb = pf[0] if pf else pins['-IN']; pot = [k for k in ins if k != pfb][0]
            i = S.net(anchor, pfb); p = S.net(anchor, pot)
            eo, d = it.pin_end(po); ei, _ = it.pin_end(pfb); ep, _ = it.pin_end(pot)
            s = -1 if eo[1] < ei[1] else 1
            paths = fb_paths(i, o) if i else []
            width = max([10 * len(pth) for pth in paths] + [12])
            fbset = {r for pth in paths for r in pth}
            # Eingang ohne eigene Beschaltung (nur Label von der Steckzunge): Label direkt am Pin, Rückkopplung zweigt dort ab
            i_lbl = i and spanning(i) and i not in labeled and not [b for b in branches(i) if b[0][0] not in fbset]
            xN = ei[0] + d[0] * (2 if i_lbl else 4); xO = ei[0] + d[0] * (4 + width + 4)
            if i_lbl:
                S.wire(ei, (xN, ei[1]), i); S.labels.append((i, (xN, ei[1]), d)); labeled.add(i)
                L = int(len(i) * 0.85) + 3
                for q_ in range(1, L + 1):
                    for s_ in (-1, 0, 1): g.block[(xN + d[0] * q_, ei[1] + s_)] = None
            if p and not is_power(p) and spanning(p) and p not in labeled and not branches(p):
                S.pin_label(it, pot); labeled.add(p); p = None
            for k, pth in enumerate(paths):
                yy = eo[1] + s * (5 + 6 * k); near = i; xs = xN + d[0] * 2
                for r in pth:
                    hplace(r, xs + d[0] * 3, yy, near, d); near = other_net(r, near); xs += d[0] * 10
            handled |= {po, pfb, pot}
            todo.append((o, i, p, pot, eo, ei, ep, d, s, xN, xO))
        for o, i, p, pot, eo, ei, ep, d, s, xN, xO in todo:     # 2. Durchgang: Ausgänge, dann Eingänge
            node(o, xO, eo[1], d, -s)
        for o, i, p, pot, eo, ei, ep, d, s, xN, xO in todo:
            far = max(ei[1], ep[1]) if s < 0 else min(ei[1], ep[1])
            y_in = far - s * 3
            ext = node(i, xN, y_in, d, -s) if i else 0
            if p and not is_power(p): node(p, ei[0] + d[0] * 2, y_in - s * (ext + 5), d, -s)
            elif p: S.pin_power(it, pot)
        return handled
    def lane(e, d, n, with_label, phase=0, parts=None):
        if phase == 2:
            if (n, e) not in LS: return
            end, cur, tps, rest = LS.pop((n, e)); return lane_rest(e, d, n, with_label, end, cur, tps, rest)
        parts = local_parts(n) if parts is None else parts
        shunts = [r for r in parts if small2(S.P[r]) and other_net(r, n) and is_power(other_net(r, n))]
        tps = [r for r in parts if r not in shunts and (len(S.P[r].lib.pins) == 1 or set(S.nets_of(r)) == {n})]
        rest = [r for r in parts if r not in shunts and r not in tps]
        col = 3; xs = []; lane_ok = True
        for r in shunts:
            o = other_net(r, n); down = is_gnd(o) or o.startswith('-'); tw = twidth(S.P[r])
            found = None
            for c in range(col, col + 120):
                x = e[0] + d[0] * c
                rows = (e[1] + 1, e[1] + 11) if down else (e[1] - 11, e[1] - 1)
                if not box_free(x - 1, rows[0], x + tw, rows[1]): continue
                path = [(e[0] + d[0] * i, e[1]) for i in range(1, c + 1)]
                bad = [p for p in path if not (g.block.get(p, 0) is not None and g.node.get(p) in (None, n) and g.wire.get(p, {}).get('H') in (None, n)
                                               and all(v == n for v in g.wire.get(p, {}).values() if g.node.get(p) == n))]
                if bad:
                    if os.environ.get('DBG'): print('   blockiert bei', bad[0], g.block.get(bad[0]), g.node.get(bad[0]), g.wire.get(bad[0]))
                    lane_ok = False; break
                found = x; break
            if not lane_ok or found is None:
                if os.environ.get('DBG'): print('  Bahn abgebrochen', n, r, lane_ok, found)
                break
            it2 = S.v(r, (found, e[1] + 3) if down else (found, e[1] - 3), n if down else o, reg)
            for k in it2.pins:
                if S.net(r, k) == o: S.pin_power(it2, k)
            xs.append(found); col = abs(found - e[0]) + tw + 3
        end = e
        if xs:
            far = max(xs, key=lambda x: abs(x - e[0])); end = (far, e[1])
            prev = e                                   # an jedem Abgriff ein eigenes Drahtstück (Pin mitten auf Draht verbindet nicht)
            for x in sorted(xs, key=lambda x: abs(x - e[0])):
                S.wire(prev, (x, e[1]), n); prev = (x, e[1])
                if x != far: S.junc.add((x, e[1]))
        cur = abs(end[0] - e[0]) + 4
        if phase == 1:
            LS[(n, e)] = (end, cur, tps, rest); return
        return lane_rest(e, d, n, with_label, end, cur, tps, rest)
    def lane_rest(e, d, n, with_label, end, cur, tps, rest):
        tps = [r for r in tps if not S.placed(r)]; rest = [r for r in rest if not S.placed(r)]
        for r in tps + rest:
            p = S.P[r]
            o = other_net(r, n) if (p.two and len(p.lib.pins) == 2) else None
            arow = None; other_side = False
            if o and anchor:
                ait = [i for i in S.insts if i.part.ref == anchor][0]
                for k in ait.pins:
                    if S.net(anchor, k) == o:
                        pe, pd = ait.pin_end(k)
                        if pd == d: arow = pe[1]
                        else: other_side = True
            if other_side and arow is None: continue        # Brücke zur anderen IC-Seite: unter den Block, Router verbindet
            if arow is not None and r in rest:
                # Brücke zwischen zwei IC-Pins derselben Seite: senkrecht, Mitte zwischen den beiden Zeilen
                yc = (e[1] + arow) // 2; top = n if e[1] < arow else o
                for c in range(cur, cur + 120):
                    cx = e[0] + d[0] * c
                    if box_free(cx - 1, yc - 4, cx + twidth(p), yc + 4): break
                S.v(r, (cx, yc), top, reg); cur = c + twidth(p) + 2
                continue
            if p.two and len(p.lib.pins) == 2 and r in rest:
                o = other_net(r, n)
                for c in range(cur, cur + 120):
                    cx = e[0] + d[0] * (c + 3)
                    if box_free(cx - 4, e[1] - 2, cx + 4, e[1] + 2): break
                it2 = S.h(r, (cx, e[1]), n if d[0] > 0 else o, reg)
                cur = c + 8
                if o and not is_power(o) and spanning(o):
                    k = [k for k in it2.pins if S.net(r, k) == o][0]; S.pin_label(it2, k)
                elif o and is_power(o):
                    k = [k for k in it2.pins if S.net(r, k) == o][0]; S.pin_power(it2, k)
            else:
                u0 = 1; pins_ = p.lib.units[u0]; num0 = sorted(pins_)[0]
                rot = [rr for rr in (0, 90, 180, 270) if rot_vec(pins_[num0][2], rr) == (-d[0], -d[1])]
                rot = rot[0] if rot else 0
                for dy in range(0, 60, 2):
                    for sgn in ((1, -1) if dy else (1,)):
                        tmp = Inst(p, u0, (0, 0), rot)
                        pe, _ = tmp.pin_end(num0)
                        pos = (e[0] + d[0] * (cur + 2) - pe[0], e[1] + sgn * dy - pe[1])
                        tmp.pos = pos; b = tmp.bbox()
                        if box_free(b[0] - 1, b[1] - 2, b[2] + 1, b[3] + 2): break
                    else: continue
                    break
                it2 = S.place(r, pos, rot, None, 1, reg)
                for k in it2.pins:
                    nn = S.net(r, k)
                    if nn != n and nn and is_power(nn): S.pin_power(it2, k)
                    elif nn != n and nn and spanning(nn): S.pin_label(it2, k)
                b = it2.bbox(); cur = max(cur, abs((b[2] if d[0] > 0 else b[0]) - e[0]) + 3)
        if with_label:
            if not tps and not rest:
                a = (end[0] + d[0] * 2, end[1]); S.wire(end, a, n)
                S.labels.append((n, a, d)); L = int(len(n) * 0.85) + 3
                for i in range(1, L + 1):
                    for s_ in (-1, 0, 1): g.block[(a[0] + d[0] * i, a[1] + s_)] = None
            else:
                for dy in (0, 2, -2, 4, -4, 6, -6):
                    a = (e[0] + d[0] * (cur + 1), e[1] + dy)
                    if box_free(a[0], a[1] - 1, a[0] + d[0] * (int(len(n) * 0.85) + 3), a[1] + 1): break
                S.label(n, a, d, reg)
    i0 = len(S.insts); w0 = len(S.wires); l0 = len(S.labels); p0 = len(S.pwr); n0 = len(S.nc); nl0 = len(getattr(S, 'nlabels', []))
    jold = S.junc; S.junc = set()
    vcaps = []                      # (Pin-Inst, Pin, [Kondensatoren]) -> in Pinnähe setzen, per Draht verbinden
    if anchor:
        it = S.place(anchor, (0, 0), 0, None, 1, reg)
        # Abblockkondensatoren dem nächstgelegenen Versorgungspin zuordnen (Abstand auf der Platine)
        bp = board_pads_num(S); assign = collections.defaultdict(list)
        apos = {num: xy for num, nn, xy in bp.get(anchor, [])}
        for r in members:
            p = S.P[r]; ns = S.nets_of(r)
            if r == anchor or len(p.lib.pins) != 2 or not ns or not all(is_power(x) for x in ns): continue
            sup = [x for x in ns if not is_gnd(x)]
            if len(sup) != 1: continue
            pins_ = [k for k in it.pins if S.net(anchor, k) == sup[0]]
            if not pins_: continue
            cxy = [xy for num, nn, xy in bp.get(r, []) if nn == sup[0]]
            best = min(pins_, key=lambda k: math.dist(cxy[0], apos[k]) if cxy and k in apos else 0)
            assign[best].append(r)
        lanes = []; plan = []
        handled = opamp_sections(it) if it.part.lib_id.split(':')[-1] in OPA else set()
        for num in it.pins:
            n = S.net(anchor, num); e, d = it.pin_end(num)
            if num in handled: continue
            if not n: S.nc.append(e); continue
            if is_power(n):
                if assign.get(num) and d[0] != 0: plan.append(num)
                else:
                    S.pin_power(it, num)
                    if assign.get(num): vcaps.append((it, num, assign[num]))
                continue
            lp = local_parts(n)
            if not lp or d[0] == 0:
                if spanning(n): S.pin_label(it, num, 2)
            else: lanes.append(num)
        lanes.sort(key=lambda k: -it.pin_end(k)[0][1])
        for num in sorted(plan, key=lambda k: -it.pin_end(k)[0][1]):
            n = S.net(anchor, num); e, d = it.pin_end(num)
            lane(e, d, n, False, 1, parts=assign[num])
            end, cur, tps_, rest_ = LS.pop((n, e))
            a = (end[0] + d[0] * 2, end[1]); S.wire(end, a, n); S.power(n, a, d, reg, connect=False)
            left = [r for r in assign[num] if not S.placed(r)]
            if left: vcaps.append((it, num, left))
        for ph in (1, 2):
            for num in lanes:
                n = S.net(anchor, num); e, d = it.pin_end(num)
                lane(e, d, n, spanning(n), ph)
    else:
        # Cluster ohne IC: am häufigsten gemeinsames Signalnetz als Sammelschiene
        cnt = collections.Counter(n for r in members for n in S.nets_of(r) if not is_power(n))
        n = cnt.most_common(1)[0][0] if cnt else None
        if n and (len(members) > 1 or spanning(n)):
            if spanning(n):
                S.label(n, (0, 0), (-1, 0), reg); g.node[(0, 0)] = n
                lane((0, 0), (1, 0), n, False)
            else:
                lane((0, 0), (1, 0), n, False)
    for it_, num, caps in vcaps:
        e, d = it_.pin_end(num); n = S.net(it_.part.ref, num); nodes = [(e, d)]
        allc = list(g.block) + list(g.node) + list(g.wire)
        if d[1] < 0: yc = min(c[1] for c in allc) - 7
        elif d[1] > 0: yc = max(c[1] for c in allc) + 7
        else: yc = e[1] + 7
        x = e[0]
        for r in caps:
            p = S.P[r]
            for dx in [0] + [v for k in range(1, 60) for v in (2 * k, -2 * k)]:
                if box_free(x + dx - 1, yc - 6, x + dx + twidth(p), yc + 6): break
            ci = S.v(r, (x + dx, yc), n, reg)
            for k in ci.pins:
                if S.net(r, k) == n: nodes.append(ci.pin_end(k))
                else: S.pin_power(ci, k)
            x = x + dx + twidth(p) + 3
        S.ptasks.append((n, nodes))
    if vcaps: S.route_all(insts=[], wire_from=w0, vkeys=set())
    # übrige Teile: Reihe unter dem Block (Entkopplung zuerst)
    rest = [r for r in members if not S.placed(r)]
    def rkey(r):
        ns = S.nets_of(r); return (not all(is_power(x) for x in ns), sorted(ns))
    allc = list(g.block) + list(g.node) + list(g.wire) or [(0, 0)]
    y = max(c[1] for c in allc) + 6; x = min(c[0] for c in allc) + 2; x0 = x
    for r in sorted(rest, key=rkey):
        p = S.P[r]
        if p.two and len(p.lib.pins) == 2:
            ns = S.nets_of(r); top = [n_ for n_ in ns if not is_gnd(n_) and not n_.startswith('-')]
            while not box_free(x - 1, y - 6, x + twidth(p), y + 6): x += 2
            it2 = S.v(r, (x, y), top[0] if top else None, reg); x += twidth(p) + 3
        else:
            for _ in range(200):
                tmp = Inst(p, 1, (x, y)); b = tmp.bbox()
                if box_free(b[0] - 2, b[1] - 3, b[2] + 2, b[3] + 3): break
                x += 2
            it2 = S.place(r, (x - (b[0] - x) if False else x, y), 0, None, 1, reg); b = it2.bbox(); x = b[2] + 12
        for k in it2.pins:
            nn = S.net(r, k)
            if nn and not is_power(nn) and spanning(nn): S.pin_label(it2, k)
        if x - x0 > 160: x = x0; y = max(c[1] for c in list(g.block) + list(g.node)) + 8
    # Versorgung/NC, verdrahten, Namen
    gi = S.insts[i0:]
    for it2 in gi:
        for k in it2.pins:
            nn = S.net(it2.part.ref, k); e, d = it2.pin_end(k)
            if not nn:
                if e not in S.nc[n0:]: S.nc.append(e)
            elif is_power(nn) and not any(e in (a, b) for a, b, _ in S.wires[w0:]) and not any(a == e for _, a, _ in S.pwr[p0:]): S.pin_power(it2, k)
    S.route_all(insts=gi, wire_from=w0, vkeys={k for k in S.vnodes if k[1] == reg})
    S.name_from = w0; S.name_labels()
    cs = list(g.block) + list(g.node) + list(g.wire)
    for it2 in gi:
        b = it2.bbox(); cs += [(b[0] - 1, b[1] - 3), (b[2] + twidth(it2.part), b[3] + 3)]
    bb = (min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs))
    jn = S.junc; S.junc = jold
    return dict(name=gname, rng=(i0, w0, l0, p0, n0, nl0), junc=jn, bb=bb)

def layout_carrier(S):
    hide_twopin(S)
    groups = make_groups(S)
    def okey(gname):
        m = re.match(r'([A-Z_]+?)(\d+)$', gname)
        pref = {'IC': 0, 'U': 1, 'JP': 2, 'X': 3, 'J': 4}
        if gname.startswith('G_'): return (9, gname)
        return (pref.get(m.group(1), 5) if m else 8, int(m.group(2)) if m else 0, gname)
    blocks = []
    for gname in sorted(groups, key=okey):
        blocks.append(build_block(S, gname, [r for r in groups[gname] if r != gname]))
    # Regalpacken in Leserichtung
    for paper, PW, PH in [('A3', 420, 297), ('A2', 594, 420), ('A1', 841, 594), ('A0', 1189, 841)]:
        W = int((PW - 30) / G); H = int((PH - 45) / G)
        x = 0; y = 0; rowh = 0; offs = []; ok = True
        for bl in blocks:
            w = bl['bb'][2] - bl['bb'][0]; h = bl['bb'][3] - bl['bb'][1]
            if x + w > W and x > 0: x = 0; y += rowh + 8; rowh = 0
            if w > W: ok = False; break
            offs.append((x - bl['bb'][0], y - bl['bb'][1])); x += w + 10; rowh = max(rowh, h)
        if ok and y + rowh <= H: break
    X0, Y0 = int(15 / G), int(40 / G)
    rng = [bl['rng'] for bl in blocks] + [(len(S.insts), len(S.wires), len(S.labels), len(S.pwr), len(S.nc), len(S.nlabels))]
    newj = set()
    for k, bl in enumerate(blocks):
        ox, oy = offs[k]; ox += X0 + (-(offs[k][0] + X0) % 2); oy += Y0 + (-(offs[k][1] + Y0) % 2)
        T = lambda c: (c[0] + ox, c[1] + oy)
        i0, w0, l0, p0, n0, nl0 = rng[k]; i1, w1, l1, p1, n1, nl1 = rng[k + 1]
        for it in S.insts[i0:i1]: it.pos = T(it.pos)
        S.wires[w0:w1] = [(T(a), T(b), n) for a, b, n in S.wires[w0:w1]]
        S.labels[l0:l1] = [(n, T(a), d) for n, a, d in S.labels[l0:l1]]
        S.pwr[p0:p1] = [(n, T(a), d) for n, a, d in S.pwr[p0:p1]]
        S.nc[n0:n1] = [T(c) for c in S.nc[n0:n1]]
        S.nlabels[nl0:nl1] = [(n, T(a), ang) for n, a, ang in S.nlabels[nl0:nl1]]
        newj |= {T(c) for c in bl['junc']}
    S.junc = newj
    return paper

if __name__ == '__main__':
    if '--pcb' in sys.argv:
        rename_pcb_nets([x for x in sys.argv[1:] if not x.startswith('--')][0]); sys.exit(0)
    a = [x for x in sys.argv[1:] if x != '--force']; png = None
    if '--png' in a: i = a.index('--png'); png = a[i + 1]; del a[i:i + 2]
    sys.exit(main(a[0], png))
