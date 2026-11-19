"""polys_raw (roots) -> polys.json (Netznamen) für pcb.py"""
import json, sys, os
D = sys.argv[1]
M = json.load(open(os.path.join(D, 'model.json'))); P = json.load(open(os.path.join(D, 'polys_raw.json')))
NN = M['netnames']
for L, items in P['copper'].items():
    for it in items: it['net'] = NN.get(it.pop('root'), '')
json.dump(P, open(os.path.join(D, 'polys.json'), 'w'))
print('H', M['H'])
