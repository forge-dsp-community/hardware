import matplotlib.image as mi, numpy as np
D=__import__('os').environ.get('FORGE_PCBS', 'forge/pcbs') + '/ad_da/eln_ad_da/V40/ES9018-PCM4202_AD-'
def rgb(name):
    return (mi.imread(D+name+'.png')[...,:3]*255).round().astype(np.int16)
def mask(name):
    a=rgb(name)
    w=(a==255).all(-1); g=(a[...,0]==a[...,1])&(a[...,1]==a[...,2])
    return ~w & ~g   # colored = feature
def outline():
    a=rgb('MILLING'); return (a==75).all(-1)
