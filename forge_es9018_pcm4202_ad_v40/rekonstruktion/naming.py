"""Netznamen, Referenzen und Werte vergeben -> model.json"""
import json, math
from collections import defaultdict, Counter
S = __import__('os').environ.get('SDIR', 'es/')
M = json.load(open(S + 'model_raw.json'))
C = M['comps']

PCM = {1: 'VREFL', 2: 'AGNDL', 3: 'VCOML', 4: 'VINL+', 5: 'VINL-', 6: 'FMT0', 7: 'FMT1', 8: 'S/M', 9: 'FS0', 10: 'FS1',
       11: 'FS2', 12: 'HPFD', 13: 'DGND', 14: 'VDD', 15: 'SDOUT', 16: 'BCK', 17: 'LRCK', 18: 'SCKI', 19: '/RST',
       20: 'CLIPR', 21: 'CLIPL', 22: 'VCC', 23: 'AGND', 24: 'VINR-', 25: 'VINR+', 26: 'VCOMR', 27: 'AGNDR', 28: 'VREFR'}
ES = "VDD_L1 VOUT1+ VOUT1- VOUT3- VOUT3+ AGND_L2 AVCC_L2 RESET GND1 AVCC_L3 AGND_L3 VOUT5+ VOUT5- VOUT7- VOUT7+ VDD_L2 AVCC_L4 AGND_L4 GND2 VDD2 SDA SCL XO XI DVCC_B LOCK NC NC1 VDD3 GND3 AGND_R5 AVCC_R5 VDD_R2 VOUT8+ VOUT8- VOUT6- VOUT6+ AGND_R3 AVCC_R3 AUTOMUTE ADDR AVCC_R2 AGND_R2 VOUT4+ VOUT4- VOUT2- VOUT2+ VDD_R1 AVCC_R1 AGND_R1 GND4 DATA8 DATA7 DATA6 DATA5 DATA4 DATA3 DATA2 DATA1 DATA_CLK VDD1 DVCC_T AGND_L1 AVCC_L1".split()
ESP = {i + 1: n for i, n in enumerate(ES)}
PCA = {1: 'A2', 2: 'IO0', 3: 'IO1', 4: 'IO2', 5: 'IO3', 6: 'VSS', 7: 'IO4', 8: 'IO5', 9: 'IO6', 10: 'IO7', 11: '~INT',
       12: 'SCL', 13: 'SDA', 14: 'VDD', 15: 'A0', 16: 'A1', 17: 'EP'}

def P(ref):
    return next(c for c in C if c['ref'] == ref)
def root(ref, num):
    return next(p['root'] for p in P(ref)['pads'] if p['num'] == str(num))

# PCM4202-Referenzen nach Position (links->rechts): Zuordnung zu AD.OUT über X100 unten
pcm = sorted([c for c in C if c['kind'] == 'PCM4202'], key=lambda c: c['cx'])
x100 = {p['num']: p['root'] for p in P('X100')['pads']}
pinof = {v: k for k, v in x100.items()}
for c in pcm:
    sd = next(p['root'] for p in c['pads'] if p['num'] == '15')
    c['_xpin'] = pinof.get(sd)
print('SDOUT->X100', [(round(c['cx'], 1), c['_xpin']) for c in pcm])
# Schaltplan: X100.9=AD.OUT.1, .8=AD.OUT.2, .7=AD.OUT.3 ; IC101->1, IC102->2, IC103->3
order = {'9': 1, '8': 2, '7': 3, '1': 3}
for k, c in enumerate(pcm):
    idx = order.get(c['_xpin'], k + 1)
    c['ref'] = 'IC10%d' % idx; c['_idx'] = idx
    c['value'] = 'PCM4202'

names = {}   # root -> (prio, name)
def nm(r, name, prio):
    if r in (None, 'None'): return
    if r not in names or names[r][0] > prio: names[r] = (prio, name)

# globale Netze
nm(root('IC105', 9), 'GND', 0); nm(root('IC105', 6), 'AGND', 0)
nm(root('IC101', 14), '3V3', 0); nm(root('IC101', 22), '5V0', 0)
nm(root('IC105', 1), '1V2_AVCC', 0); nm(root('IC105', 20), '1V2_DVCC', 0)
nm(root('IC105', 64), '3V3_AVCC_L', 0); nm(root('IC105', 49), '3V3_AVCC_R', 0)
nm(root('IC105', 25), '3V3.NOHF', 0)
for c in pcm:
    i = c['_idx']
    for n in (1, 3, 4, 5, 20, 21, 24, 25, 26, 28):
        nm(root(c['ref'], n), PCM[n].replace('CLIPR', 'CLIPR').replace('CLIPL', 'CLIPL') + '.%d' % i, 2)
    nm(root(c['ref'], 15), 'AD.OUT.%d' % i, 1)
    nm(root(c['ref'], 9), 'FS0', 1); nm(root(c['ref'], 10), 'FS1', 1); nm(root(c['ref'], 12), 'HPFD', 1)
    nm(root(c['ref'], 18), 'MCLK', 1); nm(root(c['ref'], 17), 'LRCLK', 1); nm(root(c['ref'], 16), 'BCLK.IN', 1)
    nm(root(c['ref'], 19), '/RST.PCM4202', 1)
for n, s in ESP.items():
    if s.startswith('VOUT'): nm(root('IC105', n), s, 1)
nm(root('IC105', 8), 'RST.ES9018', 1); nm(root('IC105', 21), 'SDA.PIPE.2', 1); nm(root('IC105', 22), 'SCL.PIPE.2', 1)
nm(root('IC105', 24), 'MCLK.DA', 1); nm(root('IC105', 26), 'OVF-DA/LOCK', 1); nm(root('IC105', 60), 'BCLK.OUT', 1)
nm(root('IC105', 58), 'ES_DATA2', 2); nm(root('IC105', 57), 'ES_DATA3', 2); nm(root('IC105', 56), 'ES_DATA4', 2)
nm(root('IC105', 55), 'ES_DATA5', 2); nm(root('IC105', 40), 'ES_AUTOMUTE', 2); nm(root('IC105', 23), 'ES_XO', 3)
nm(root('IC104', 12), 'SCL.PIPE.1', 1); nm(root('IC104', 13), 'SDA.PIPE.1', 1); nm(root('IC104', 11), 'OVF-AD', 1)
x100n = {1: 'OVF-AD', 3: 'SDA.PIPE.1', 4: 'SCL.PIPE.1', 5: 'SCL.PIPE.2', 6: 'SDA.PIPE.2', 7: 'AD.OUT.3', 8: 'AD.OUT.2',
         9: 'AD.OUT.1', 11: 'OVF-DA/LOCK', 12: '/RST.2.DEVICES', 13: 'MCLK', 14: 'BCLK.IN', 15: 'BCLK.OUT', 16: 'LRCLK'}
for k, v in x100n.items(): nm(x100[str(k)], v, 4)
nm(root('J1', 2), 'I.2-VREF', 1); nm(root('J1', 5), 'I.1-VREF', 1)

# Restliche Netze: Net-(REF-Pad)
# zunächst Referenzen vergeben
seq = Counter()
KPFX = {'0805': 'C', '0603': 'C', 'TANT_C': 'C', 'TANT_B': 'C', 'SMD2': 'C', 'PADGRP': 'TP', 'SJ3': 'JP'}
def is_gnd(r): return names.get(r, (9, ''))[1] in ('GND', 'AGND')
start = {'C': 201, 'R': 201, 'TP': 1}
for c in C:
    k = c['kind']
    if k in ('0805', '0603', 'TANT_C', 'TANT_B', 'SMD2'):
        a, b = c['pads'][0]['root'], c['pads'][1]['root']
        na, nb = names.get(a, (9, '?'))[1], names.get(b, (9, '?'))[1]
        nets = {na, nb}
        if k.startswith('TANT'): val = '47uF 16V'
        elif any(n.startswith('VIN') for n in nets) and len([n for n in nets if n.startswith('VIN')]) == 2: val = '2.7nF C0G'
        elif any(n.startswith('VIN') for n in nets) and (nets & {'GND', 'AGND'}): val = '100pF C0G'
        elif nets & {'GND', 'AGND'}: val = '100nF'
        elif a == b: val = '0R / Bruecke?'
        elif nets & {'I.1-VREF', 'I.2-VREF'} and nets & {'3V3_AVCC_L', '3V3_AVCC_R'}: val = 'R? (VREF-Teiler)'
        else: val = '?'
        c['value'] = val
        pf = 'R' if val in ('0R / Bruecke?',) else 'C'
        c['ref'] = '%s%d' % (pf, start[pf] + seq[pf]); seq[pf] += 1
    elif k == 'PADGRP':
        c['ref'] = 'TP%d' % (1 + seq['TP']); seq['TP'] += 1; c['value'] = 'Anschluss/Pad'
P('JP1')['value'] = 'SJ FS0'; P('JP2')['value'] = 'SJ FS1'; P('JP3')['value'] = 'SJ HPFD'
P('IC104')['value'] = 'PCA9554ABS'; P('IC105')['value'] = 'ES9018S'
P('X100')['value'] = 'Randkontakt 1x20 + Versorgung'; P('X101')['value'] = '1x04'; P('X102')['value'] = '1x04'
for k in range(1, 5): P('J%d' % k)['value'] = 'Ausgangsplatine I/V (Steckplatz %d)' % k
P('U201')['value'] = 'LDO SOT-23-5 (1V2_AVCC)'; P('U202')['value'] = 'Regler SOT-89 (1V2_DVCC)'
P('U203')['value'] = 'SOIC-8 (3V3_AVCC_L/R?)'; P('U204')['value'] = 'SOT-23 ?'
# Netznamen der Rest-Netze
allroots = Counter(p['root'] for c in C for p in c['pads'])
for c in C:
    for p in c['pads']:
        r = p['root']
        if r in ('None', None): continue
        nm(r, 'Net-(%s-%s)' % (c['ref'], p['num']), 9)
for c in C:
    for p in c['pads']:
        p['net'] = names.get(p['root'], (9, ''))[1] if p['root'] not in ('None', None) else ''
for v in M['vias']:
    v['net'] = names.get(v['root'], (9, ''))[1] if v['root'] not in ('None', None) else ''
def _san(n): return n.replace('/RST', 'nRST').replace('/', '_')
names = {r: (pr, _san(n)) for r, (pr, n) in names.items()}
for c in C:
    for p in c['pads']: p['net'] = _san(p['net'])
for v in M['vias']: v['net'] = _san(v['net'])
M['netnames'] = {r: n for r, (pr, n) in names.items()}
M.setdefault('rootmap', {})
json.dump(M, open(S + 'model.json', 'w'), indent=0)
dup = Counter(n for _, n in names.values())
print('Netze', len(names), 'doppelte Namen', [k for k, v in dup.items() if v > 1])
for c in C:
    if c['kind'] in ('PCM4202',): print(c['ref'], round(c['cx'], 1))
print('X100', {p['num']: p['net'] for p in P('X100')['pads']})
for ref in ('U201', 'U202', 'U203', 'U204', 'X101', 'X102', 'JP1', 'JP2', 'JP3', 'IC104'):
    print(ref, {p['num']: p['net'] for p in P(ref)['pads']})
print('Vias ohne Netz', sum(1 for v in M['vias'] if not v['net']))
