import sys; sys.path.insert(0,'.')
from load import *
import matplotlib.image as mi
from scipy import signal
S=__import__('os').environ.get('SDIR', 'es/')
def ec(i):
    a=(mi.imread(S+'ec-%03d.png'%i)[...,:3]*255).astype(np.int16); return a
E=mask('BOTTOM').astype(float)
a=ec(4); cu=(a.sum(-1)<200).astype(float)  # black=copper
crop=cu[80:860,80:880]
best=[]
for k in range(4):
  for fl in (0,1):
    t=np.rot90(crop,k); t=t[:, ::-1] if fl else t
    c=signal.fftconvolve(t-t.mean(), (E-E.mean())[::-1,::-1], mode='full')
    i=np.unravel_index(c.argmax(),c.shape); best.append((c.max()/E.sum(),k,fl,i))
for b in sorted(best,reverse=True)[:3]: print(b)
