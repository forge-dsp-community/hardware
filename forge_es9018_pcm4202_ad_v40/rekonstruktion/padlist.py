import sys; sys.path.insert(0,'.')
from load import *
from scipy import ndimage as nd
S=__import__('os').environ.get('SDIR', 'es/')
X0,Y0,PPM=24.5,681.0,11.811   # outline origin (lower-left) in px
def mm(x,y): return ((x-X0)/PPM, (Y0-y)/PPM)
vias=(rgb('VIAS')!=255).any(-1)&~(rgb('VIAS')==75).all(-1)
th=(rgb('PADS')!=255).any(-1)&~(rgb('PADS')==75).all(-1)
out=[]
for side,f in (('B','padB'),('T','padT')):
    m=np.load(S+f+'.npy')
    lab,n=nd.label(m)
    for i,sl in enumerate(nd.find_objects(lab),1):
        r=lab[sl]==i
        if r.sum()<6: continue
        ys,xs=np.nonzero(r); ys=ys+sl[0].start; xs=xs+sl[1].start
        kind='smd'
        if vias[ys,xs].any(): kind='via'
        if th[ys,xs].any(): kind='th'
        cx,cy=mm(xs.mean(),ys.mean())
        w=(xs.max()-xs.min()+1)/PPM; h=(ys.max()-ys.min()+1)/PPM
        fill=r.sum()/((xs.max()-xs.min()+1)*(ys.max()-ys.min()+1))
        out.append((side,kind,round(cx,2),round(cy,2),round(w,2),round(h,2),round(fill,2)))
import json; json.dump(out,open(S+'pads.json','w'))
from collections import Counter
print(Counter((o[0],o[1]) for o in out))
smd=[o for o in out if o[1]=='smd']
print(Counter((round(o[4],1),round(o[5],1)) for o in smd).most_common(40))
