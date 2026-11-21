import sys
sys.path.insert(0,__import__('os').environ.get('REK_TOOLS', 'tools'))
MODE=int(sys.argv[1]) if len(sys.argv)>1 else 1
from load import *
from scipy import ndimage as nd
S=__import__('os').environ.get('SDIR', 'es/')
def feat(name):
    a=rgb(name); return (a!=255).any(-1)&~(a==75).all(-1)&~((a[...,0]==a[...,1])&(a[...,1]==a[...,2]))
d=np.load(S+'ec_cu.npz')
import os
SRC=os.environ.get('SRC','AND')
EG={'TOP':feat('TOP'),'ROUTE2':feat('ROUTE2'),'ROUTE3':feat('ROUTE3'),'BOTTOM':feat('BOTTOM')}
NODIL=[('ROUTE2',10.4,35.0,1.6)]   # SDOUT IC101 / GND-Flaeche
def comb(k):
    if SRC=='EC': return d[k]
    if SRC=='EAGLE': return EG[k]
    e=EG[k]
    if k in ('TOP','BOTTOM'): e=e|nd.binary_erosion(d[k],iterations=1)   # Pads/Vias stehen in Eagle-Kupferlagen nicht drin
    DIL=int(os.environ.get('DIL','1'))
    if DIL:
        e0=e; e=nd.binary_dilation(e,iterations=DIL)
        # lokal ohne Dilatation (sonst Kurzschluss durch 1-px-Spalt)
        for (lk,x,y,r) in NODIL:
            if lk==k:
                X,Y=int(24.5+x*11.811),int(681-y*11.811); R=int(r*11.811)
                e[Y-R:Y+R,X-R:X+R]=e0[Y-R:Y+R,X-R:X+R]
    return d[k]&(e|nd.binary_fill_holes(feat('VIAS')|feat('PADS')))
LAY={'F':comb('TOP'),'In1':comb('ROUTE2'),'In2':comb('ROUTE3'),'B':comb('BOTTOM')}
holes=nd.binary_fill_holes(feat('VIAS')|feat('PADS'))
hl,hn=nd.label(holes)
labs={k:nd.label(v) for k,v in LAY.items()}
par={}
def f(a):
    par.setdefault(a,a)
    while par[a]!=a: par[a]=par[par[a]]; a=par[a]
    return a
def u(a,b): par[f(a)]=f(b)
for k,(l,n) in labs.items():
    for i in range(1,n+1): f((k,i))
CENT=nd.center_of_mass(holes,hl,range(1,hn+1))
EDGES=[]
for i,(cy,cx) in enumerate(CENT,1):
    f(('H',i)); Y,X=int(round(cy)),int(round(cx))
    for k,(l,n) in labs.items():
        v=l[Y-MODE:Y+MODE+1,X-MODE:X+MODE+1]; v=v[v>0]
        if len(v):
            b=int(np.bincount(v).argmax()); u(('H',i),(k,b)); EDGES.append((('H',i),(k,b)))
roots={f(a) for a in par}
print('holes',hn,{k:v[1] for k,v in labs.items()},'nets',len(roots))
# Reparaturen: im Schaltplan gemeinsame Netze, die bei 300 dpi im UND-Bild aufgetrennt sind
X0_,Y0_,PPM_=24.5,681.0,11.811
def _node(L,x,y):
    X,Y=int(round(X0_+x*PPM_)),int(round(Y0_-y*PPM_)); v=labs[L][0][Y-1:Y+2,X-1:X+2]; v=v[v>0]
    return (L,int(np.bincount(v).argmax())) if len(v) else None
REPAIRS=[(('B',41.70,35.59),('B',26.46,35.59)), (('B',11.22,34.93),('B',0.43,37.64))]   # BCLK IC rechts <-> IC Mitte (Pin 16)
for a,b in REPAIRS:
    na,nb=_node(*a),_node(*b)
    if na and nb: u(na,nb); EDGES.append((na,nb))
