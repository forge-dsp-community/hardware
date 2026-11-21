import sys; sys.path.insert(0,__import__('os').environ.get('REK_TOOLS', 'tools'))
from net import *
from collections import Counter
P=[p for p in json.load(open(S+'pads.json')) if p[1]!='via']
_c=Counter()
for p in P: _c[net_at(p[0],p[2],p[3],p[1]=='th')]+=1
NAMES={n:'N%d'%i for i,(n,_) in enumerate(_c.most_common())}
def nn(side,x,y,th=False):
    n=net_at(side,x,y,th)
    if n not in NAMES: NAMES[n]='X%d'%len(NAMES)
    return NAMES[n]
def qfp_pins(cx,cy,n_side,pitch,row,mirror=True,rot=0):
    """standard numbering (component top view), returns {pin:(x,y)} in board top view"""
    pts={}
    half=(n_side-1)/2*pitch
    k=1
    for i in range(n_side): pts[k]=(-row, half-i*pitch); k+=1     # left, top->bottom
    for i in range(n_side): pts[k]=(-half+i*pitch,-row); k+=1     # bottom, left->right
    for i in range(n_side): pts[k]=(row,-half+i*pitch); k+=1      # right, bottom->top
    for i in range(n_side): pts[k]=(half-i*pitch,row); k+=1       # top, right->left
    out={}
    import math
    c,s=round(math.cos(math.radians(rot))),round(math.sin(math.radians(rot)))
    for p,(x,y) in pts.items():
        x,y=c*x-s*y, s*x+c*y
        if mirror: x=-x
        out[p]=(cx+x,cy+y)
    return out
