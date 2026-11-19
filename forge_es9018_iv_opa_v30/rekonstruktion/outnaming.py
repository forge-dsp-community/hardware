"""Rollen, Original-Referenzen, Werte und Netznamen der I/V-Ausgangsplatinen -> model.json
Aufruf: outnaming.py <outdir> <variante: V30|V40d|V40e>"""
import sys, json, os
OUT, VAR = sys.argv[1], sys.argv[2]
M = json.load(open(os.path.join(OUT, 'model_raw.json')))
C = M['comps']; names = {r: (1, n) for r, n in M['names'].items()}
def nm(r, s, prio=3):
    if r in (None, 'None'): return
    if r not in names or names[r][0] > prio: names[r] = (prio, s)
inv = {}
for r, (p, n) in names.items(): inv[n] = r
AG = inv['AGND']; VP = inv.get('+12V'); VN = inv.get('-12V')
two = [c for c in C if len(c['pads']) == 2 and c['kind'] in ('0603', '0805', '1206', '1210', 'CP_TH')]
def nets(c): return {c['pads'][0]['root'], c['pads'][1]['root']}
def other(c, r): return next(p['root'] for p in c['pads'] if p['root'] != r)
def between(a, b, pool=None):
    return [c for c in (pool or two) if nets(c) == {a, b}]
def touching(r): return [c for c in two if r in nets(c)]
def size(c): return max(max(p['w'], p['h']) for p in c['pads'])

assign = {}   # ref_alt -> (neue Ref, Wert)
def give(c, ref, val):
    if c is None or c['ref'] in assign: return
    assign[c['ref']] = (ref, val)

st1 = [s for s in M['sections'] if s['stage'] == 1]; st2 = [s for s in M['sections'] if s['stage'] == 2]
REFS = {2: dict(Rf=('R1', 'R2'), Rs=('R102', 'R103'), Cs=('C116', 'C117'), Ce=('C5', 'C6'), Ri=('R106', 'R107'),
                Cx=('C2', 'C1'), Rd=('R114', 'R115'), Rfb=('R110', 'R111'), Cc=('C122', 'C123'), Rc=('R3', 'R4'), Rl='R9', Cv='C10'),
        1: dict(Rf=('R5', 'R6'), Rs=('R104', 'R105'), Cs=('C118', 'C119'), Ce=('C7', 'C8'), Ri=('R108', 'R109'),
                Cx=('C4', 'C3'), Rd=('R116', 'R117'), Rfb=('R112', 'R113'), Cc=('C124', 'C125'), Rc=('R7', 'R8'), Rl='R10', Cv='C9')}
RF = {'V30': '2720R 0.1% 10ppm', 'V40d': '2720R 0.1% 10ppm', 'V40e': '1370R 0.1%'}[VAR]
RL = {'V30': None, 'V40d': '100K 1%', 'V40e': '2K2'}[VAR]
report = []
for ch in (1, 2):
    vref = inv.get('I.%d-VREF' % ch); ip = inv.get('I.%d+' % ch); im = inv.get('I.%d-' % ch); op = inv.get('O.%d+' % ch)
    R = REFS[ch]
    Sp = next((s for s in st1 if ip in (s['inv'], s['pos'])), None); Sm = next((s for s in st1 if im in (s['inv'], s['pos'])), None)
    for S in (Sp, Sm):
        if S and S.get('swapped'): report.append('Kanal %d: %s Pin %s/%s: Strom-Eingang am +, VREF am - (vertauscht)' % (ch, S['op'], S['pins'][1], S['pins'][2]))
    D = next((s for s in st2 if s['out'] == op), None)
    if not (Sp and Sm and D):
        report.append('Kanal %d: Stufen nicht vollständig erkannt' % ch); continue
    nm(Sp['out'], 'IV%d+' % ch, 2); nm(Sm['out'], 'IV%d-' % ch, 2); nm(D['inv'], 'DIFF%d-' % ch, 2); nm(D['pos'], 'DIFF%d+' % ch, 2)
    give(next(iter(between(vref, AG)), None), R['Cv'], '100nF?')
    X = {}
    for k, S in enumerate((Sp, Sm)):
        fbn = S['inv']
        if not between(fbn, S['out']) and between(S['pos'], S['out']): fbn = S['pos']
        S = dict(S, inv=fbn)
        rf = between(S['inv'], S['out'])
        give(rf[0] if rf else None, R['Rf'][k], RF)
        # Serienglied R+C über der Rückkopplung
        for c in touching(S['inv']):
            if c['ref'] in assign: continue
            mid = other(c, S['inv'])
            c2 = between(mid, S['out'])
            if c2:
                give(c, R['Rs'][k], '100R 0.1%'); give(c2[0], R['Cs'][k], '100pF C0G'); nm(mid, 'IV%d%s_RC' % (ch, '+-'[k]), 4)
        # Ausgang -> (Elko) -> 470R -> Knoten X
        cand = [c for c in touching(S['out']) if c['ref'] not in assign]
        node = S['out']
        el = [c for c in cand if c['kind'] == 'CP_TH']
        if el:
            give(el[0], R['Ce'][k], '0R (Brücke)')   # auf realen V30-Platinen 0-Ohm-SMD statt Elko; node = other(el[0], S['out']); nm(node, 'IV%d%s_AC' % (ch, '+-'[k]), 4)
            cand = [c for c in touching(node) if c['ref'] not in assign]
        tgt = D['inv'] if k == 0 else D['pos']
        for c in cand:
            x = other(c, node)
            if between(x, tgt):
                give(c, R['Ri'][k], '470R 0.1%'); X[k] = x; nm(x, 'FLT%d%s' % (ch, '+-'[k]), 3)
                give(between(x, tgt)[0], R['Rd'][k], '20R 1%')
                break
    if 0 in X:
        give(next(iter(between(X[0], D['out'])), None), R['Rfb'][0], '360R 0.1%')
        g = sorted(between(X[0], AG), key=size, reverse=True)
        if g: give(g[0], R['Cx'][0], '100nF C0G')
    if 1 in X:
        g = sorted(between(X[1], AG), key=size, reverse=True)   # größeres Gehäuse = C, kleineres = R
        if g: give(g[0], R['Cx'][1], '100nF C0G')
        if len(g) > 1: give(g[1], R['Rfb'][1], '360R 0.1%')
    for c in touching(D['inv']):
        if c['ref'] in assign: continue
        mid = other(c, D['inv'])
        c2 = between(mid, D['out'])
        if c2: give(c, R['Cc'][0], '3.9nF C0G'); give(c2[0], R['Rc'][0], '100R 0.1%'); nm(mid, 'DIFF%d-_RC' % ch, 4)
    for c in touching(D['pos']):
        if c['ref'] in assign: continue
        mid = other(c, D['pos'])
        c2 = [x for x in between(mid, AG) if x['ref'] not in assign]
        if c2: give(c, R['Cc'][1], '3.9nF C0G'); give(c2[0], R['Rc'][1], '100R 0.1%'); nm(mid, 'DIFF%d+_RC' % ch, 4)
    if RL:
        rl = [c for c in between(D['out'], AG) if c['ref'] not in assign]
        if rl: give(rl[0], R['Rl'], RL)
# Abblockkondensatoren
k = 0
for c in sorted(two, key=lambda c: (c['cx'], c['cy'])):
    if c['ref'] in assign: continue
    if nets(c) == {VP, AG} or nets(c) == {VN, AG}:
        pos = nets(c) == {VP, AG}
        refs = ['C110', 'C112', 'C114', 'C5'] if pos else ['C111', 'C113', 'C115', 'C6']
        used_ = {v[0] for v in assign.values()}
        free = [r for r in refs if r not in used_]
        give(c, free[0] if free else 'C2%02d' % k, '100nF 16V' if free and free[0] not in ('C5', 'C6') else '?'); k += 1
# Umbenennen
cnt = 0
for c in C:
    if c['ref'] in assign:
        c['ref'], c['value'] = assign[c['ref']]
    elif c['kind'].startswith('SOIC'):
        c['value'] = {'SOIC8': 'Dual-OpAmp (Summierer)', 'SOIC14': 'Quad-OpAmp (I/V)'}[c['kind']]
        if VAR != 'V30': c['value'] = 'Dual-OpAmp'
        else:   # Typen laut Angabe Nutzer / Datenblatt TI
            c['value'], c['datasheet'] = {'SOIC8': ('LME49720', 'https://www.ti.com/lit/ds/symlink/lme49720.pdf'),
                                          'SOIC14': ('LME49740', 'https://www.ti.com/lit/ds/symlink/lme49740.pdf')}[c['kind']]
    elif c['ref'] == 'X1': c['value'] = 'Steckzunge 13-polig'
    elif c['kind'] == 'PADGRP': c['value'] = 'Pad'
    else:
        cnt += 1; c['ref'] = 'X%d' % (100 + cnt) if False else 'Q%d' % cnt; c['value'] = '?'
# Opamps: Erststufe/Zweitstufe benennen (V40: U1..U3)
for c in C:
    for p in c['pads']:
        r = p['root']
        if r in ('None', None): p['net'] = ''; continue
        if r not in names: nm(r, 'Net-(%s-%s)' % (c['ref'], p['num']), 9)
        p['net'] = names[r][1]
for v in M['vias']:
    v['net'] = names[v['root']][1] if v['root'] in names else ''
M['netnames'] = {r: n for r, (p, n) in names.items()}
M['rootmap'] = {}
json.dump(M, open(os.path.join(OUT, 'model.json'), 'w'), indent=0)
from collections import Counter
dup = [n for n, v in Counter(n for p, n in names.values()).items() if v > 1]
print(VAR, 'Teile', len(C), 'zugeordnet', len(assign), 'unbekannt', cnt, 'Netze', len(names), 'doppelt', dup)
for r in report: print(' ', r)
print(' Refs:', sorted(c['ref'] for c in C))
