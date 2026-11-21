import sys; sys.path.insert(0,__import__('os').environ.get('REK_TOOLS', 'tools'))
from load import *
import matplotlib.image as mi
from scipy import signal
S=__import__('os').environ.get('SDIR', 'es/')
def feat(name):
    a=rgb(name); return (a!=255).any(-1)&~(a==75).all(-1)&~((a[...,0]==a[...,1])&(a[...,1]==a[...,2]))
out={}
for i,L in ((1,'TOP'),(2,'ROUTE2'),(3,'ROUTE3'),(4,'BOTTOM')):
    a=(mi.imread(S+'ec-%03d.png'%i)[...,:3]*255).astype(np.int16)
    cu=(a.sum(-1)<200)
    crop=cu[80:860,80:880]; t=np.rot90(crop,1).astype(float)
    E=feat(L).astype(float)
    c=signal.fftconvolve(t-t.mean(),(E-E.mean())[::-1,::-1],mode='valid')
    dy,dx=np.unravel_index(c.argmax(),c.shape)
    w=t[dy:dy+E.shape[0],dx:dx+E.shape[1]]>0.5
    print(L,dy,dx,'agree',(w==(E>0.5)).mean(),'ec-only',(w&~(E>.5)).mean(),'eagle-only',(~w&(E>.5)).mean())
    out[L]=w
np.savez(S+'ec_cu.npz',**out)
