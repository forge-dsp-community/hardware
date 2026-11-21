import sys, json, subprocess, os
S=__import__('os').environ.get('SDIR', 'es/')
M=json.load(open(S+'model.json'))
pads=[(c['ref'],p['num'],p['side'],p['x'],p['y'],p['th']) for c in M['comps'] for p in c['pads']]
json.dump(pads,open(S+'padlist.json','w'))
code=r'''
import sys,json,os; NAME=sys.argv[1]; sys.path.insert(0,__import__('os').environ.get('REK_TOOLS', 'tools'))
from common import *
pads=json.load(open(S+"padlist.json"))
out=[]
for ref,num,side,x,y,th in pads:
    s="B" if side in ("B","FB") else "F"
    r=net_at(s,x,y,th)
    out.append(repr(r))
json.dump(out,open(S+"part_"+NAME+".json","w"))
'''
for name,env in (('EC',{'SRC':'EC'}),('EAGLE',{'SRC':'EAGLE'}),('FIN',{})):
    e=dict(os.environ); e.update(env)
    subprocess.run(['/usr/bin/python3','-I','-c',code,name],env=e,capture_output=True)
P={k:json.load(open(S+'part_%s.json'%k)) for k in ('EC','EAGLE','FIN')}
from collections import defaultdict
def groups(lst):
    g=defaultdict(set)
    for i,r in enumerate(lst):
        if r!='None': g[r].add(i)
    return {i:frozenset(g[r]) if r!='None' else frozenset([i]) for i,r in enumerate(lst)}
G={k:groups(v) for k,v in P.items()}
lab=lambda i:'%s.%s'%pads[i][:2]
seen=set()
for i in range(len(pads)):
    for j in G['EC'][i]&G['EAGLE'][i]:
        if j>i and j not in G['FIN'][i] and (i,j) not in seen:
            print('OPEN (beide Quellen verbunden):',lab(i),lab(j)); seen.add((i,j))
            break
    for j in G['FIN'][i]:
        if j>i and j not in G['EC'][i] and j not in G['EAGLE'][i]:
            print('SHORT (keine Quelle verbunden):',lab(i),lab(j)); break
