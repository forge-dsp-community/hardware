import json
S=__import__('os').environ.get('SDIR', 'es/')
M=json.load(open(S+'model_raw.json'))
P={k:json.load(open(S+'part_%s.json'%k)) for k in ('EC','EAGLE','FIN')}
flat=[p for c in M['comps'] for p in c['pads']]
assert len(flat)==len(P['FIN'])
par={}
def f(a):
    par.setdefault(a,a)
    while par[a]!=a: a=par[a]
    return a
for p in flat: f(p['root'])
for v in M['vias']: f(v['root'])
n=0
for i in range(len(flat)):
    for j in range(i+1,len(flat)):
        if P['EC'][i]!='None' and P['EC'][i]==P['EC'][j] and P['EAGLE'][i]!='None' and P['EAGLE'][i]==P['EAGLE'][j]:
            a,b=f(flat[i]['root']),f(flat[j]['root'])
            if a!=b and 'None' not in (a,b): par[a]=b; n+=1
M['rootmap']={k:f(k) for k in list(par)}
for p in flat: p['root']=f(p['root'])
for v in M['vias']: v['root']=f(v['root'])
json.dump(M,open(S+'model_raw.json','w'),indent=0)
print('merged',n)
