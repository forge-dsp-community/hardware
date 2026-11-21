import sys; sys.path.insert(0,'.')
import os; sys.argv=[sys.argv[0],os.environ.get('MODE','1')]
from conn import *
import json
X0,Y0,PPM=24.5,681.0,11.811
def px(x,y): return int(round(X0+x*PPM)), int(round(Y0-y*PPM))
ROOTS={}
def net_at(side,x,y,th=False):
    X,Y=px(x,y)
    if th or side=='TH':
        h=hl[Y,X]
        if h: return f(('H',h))
    L={'B':'B','F':'F','T':'F','TH':'B'}[side]
    l=labs[L][0]
    # search small neighbourhood
    for r in range(0,3):
        v=l[Y-r:Y+r+1,X-r:X+r+1]; v=v[v>0]
        if len(v): return f((L,int(np.bincount(v).argmax())))
    return None
GNDROOT=None
