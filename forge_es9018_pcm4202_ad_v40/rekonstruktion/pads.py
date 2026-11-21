import sys; sys.path.insert(0,'.')
from load import *
import matplotlib.image as mi
from scipy import ndimage as nd
S=__import__('os').environ.get('SDIR', 'es/')
def ec(i): return (mi.imread(S+'ec-%03d.png'%i)[...,:3]*255).astype(np.int16)
SH=(696,668)
def warp(img,k,fl,dy,dx):
    t=np.rot90(img,k); t=t[:, ::-1] if fl else t
    return t[dy:dy+SH[0], dx:dx+SH[1]]
def yellow(a): return ((a[...,0]>180)&(a[...,1]>150)&(a[...,2]<120))
padB=warp(yellow(ec(5)),3,1,127,118)
padT=warp(yellow(ec(0)),1,0,152,121)
np.save(S+'padB.npy',padB); np.save(S+'padT.npy',padT)
if __name__=='__main__':
    bp=rgb('BPLACE'); img=np.full(SH+(3,),255,np.uint8)
    img[(bp!=255).any(-1)]=(120,120,120)
    img[padB]=(220,160,0)
    img[(rgb('VIAS')[...,1]==165)&~padB]=(0,160,0)
    big=np.kron(img,np.ones((3,3,1),np.uint8))
    # grid every 5mm
    for mm in range(0,60,5):
        p=int((24+mm*11.811)*3); 
        if p<big.shape[1]: big[:,p,:]=(255,0,0)
        q=int((681-mm*11.811)*3)
        if 0<q<big.shape[0]: big[q,:,:]=(0,0,255)
    mi.imsave(S+'padB_overlay.png',big)
