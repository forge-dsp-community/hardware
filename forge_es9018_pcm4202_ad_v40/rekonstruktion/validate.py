import sys; sys.path.insert(0,__import__('os').environ.get('REK_TOOLS', 'tools'))
from common import *
import json
pcm=[]
ss=[p for p in P if (round(p[4],1),round(p[5],1))==(1.4,0.5)]
def pcmpins(lo,hi):
    g=[p for p in ss if lo<p[2]<hi]
    L=sorted([p for p in g if p[2]<(lo+hi)/2],key=lambda p:-p[3]); R=sorted([p for p in g if p[2]>(lo+hi)/2],key=lambda p:-p[3])
    d={i+1:(p[2],p[3]) for i,p in enumerate(R)}; d.update({28-i:(p[2],p[3]) for i,p in enumerate(L)}); return d
chips=[pcmpins(10,19),pcmpins(25,34),pcmpins(41,50)]
es=qfp_pins(23.33,19.64,16,0.5,5.59,True,270)
r=lambda xy: net_at('B',*xy)
same=[ [es[i] for i in (9,19,30,51,41,52,53,54)], [es[i] for i in (6,11,18,31,38,43,50,63)],
       [es[i] for i in (7,10,17,64)],[es[i] for i in (32,39,42,49)],[es[i] for i in (1,16,33,48)],[es[i] for i in (20,29,61)],[es[i] for i in (25,62)]]
for pin in (9,10,12,14,16,17,18,19,22): same.append([c[pin] for c in chips])
same.append([c[p] for c in chips for p in (2,6,7,11,13,23,27)])
opens=0
for g in same:
    rs={r(x) for x in g}
    if len(rs)>1: opens+=1; print(' OPEN group',g[0],len(rs))
# distinct: every pin of a different "role" across chips and ES signals
distinct=[c[p] for c in chips for p in (1,3,4,5,15,20,21,24,25,26,28)]+[es[i] for i in list(range(2,6))+list(range(12,16))+list(range(34,38))+list(range(44,48))+[8,21,22,24,26,60,58,57,56,55]]
distinct+=[chips[0][14],chips[0][22],chips[0][2],es[6],es[1],es[20],es[64],es[49],es[25]]
rs=[r(x) for x in distinct]
from collections import Counter
cnt=Counter(rs); shorts=sum(v-1 for v in cnt.values() if v>1)
print('SRC',os.environ.get('SRC'),'opens',opens,'shorts',shorts)
