"""Assign KiCad stock 3D models to the reconstructed footprints.

Usage: /usr/bin/python3 rekonstruktion/models3d.py <project dir> [...]
Edits as text (no pcbnew save, project rules stay untouched) and is idempotent:
  - every footprint in <project>/*.pretty
  - every footprint in <project>/<name>.kicad_pcb and rekonstruktion/<name>_zonen.kicad_pcb
Run after pcb.py, which regenerates library and board without models.
Board instances get R or C models by reference prefix; offsets/rotations were
checked against the pads with kicad-cli pcb render.
Footprints without a model are PCB copper only (edge fingers, castellations,
slots, solder jumpers, test pads, mounting holes)."""
import re, sys, glob, os
K = '${KICAD10_3DMODEL_DIR}/'
def m(path, off=(0,0,0), rot=0): return (K+path, off, rot)
CSMD = 'Capacitor_SMD.3dshapes/'; RSMD = 'Resistor_SMD.3dshapes/'
def model_for(name, ref=None):
    isR = (ref or '').startswith('R')
    if name.startswith('RC_0603'):
        return m((CSMD+'C_0603_1608Metric.step') if (ref and not isR) else RSMD+'R_0603_1608Metric.step')
    if name.startswith('C_0603_Eagle'):
        p = float(name.rsplit('P',1)[1])
        if p > 4.0: return m(CSMD+'C_1812_4532Metric.step')
        if p > 3.0: return m(CSMD+'C_1206_3216Metric.step')
        return m((RSMD+'R_0603_1608Metric.step') if isR else CSMD+'C_0603_1608Metric.step')
    if name.startswith('RC_1206') or name.startswith('L_C_1206ish'):
        return m((RSMD+'R_1206_3216Metric.step') if isR else CSMD+'C_1206_3216Metric.step')
    if name.startswith('C_0805'): return m(CSMD+'C_0805_2012Metric.step')
    if name.startswith('RC_1210'): return m(CSMD+'C_1210_3225Metric.step')
    if name.startswith('CP_Tantalum_Case-C'): return m('Capacitor_Tantalum_SMD.3dshapes/CP_EIA-6032-28_Kemet-C.step')
    if name.startswith('R_0R_auf_Elkoplatz'): return m(RSMD+'R_1206_3216Metric.step')   # V30: 0-Ohm-1206 auf dem Elkoplatz
    if name.startswith('CP_Radial_TH'): return m('Capacitor_THT.3dshapes/CP_Radial_D5.0mm_P2.50mm.step', (-1.27,0,0))
    if name == 'SOIC-8_Eagle': return m('Package_SO.3dshapes/SOIC-8_3.9x4.9mm_P1.27mm.step', rot=-90)
    if name == 'SOIC-14_Eagle': return m('Package_SO.3dshapes/SOIC-14_3.9x8.7mm_P1.27mm.step', rot=90)
    if name.startswith('SSOP-28'): return m('Package_SO.3dshapes/SSOP-28_5.3x10.2mm_P0.65mm.step')
    if name.startswith('TQFP-64'): return m('Package_QFP.3dshapes/TQFP-64_10x10mm_P0.5mm.step', rot=90)
    if name.startswith('HVQFN-16'): return m('Package_DFN_QFN.3dshapes/WQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm.step')
    if name == 'SOT-23-3_custom': return m('Package_TO_SOT_SMD.3dshapes/SOT-23.step', rot=-90)
    if name == 'SOT-23-5_Eagle': return m('Package_TO_SOT_SMD.3dshapes/SOT-23-5.step', rot=180)
    if name == 'SOT-89-3_Eagle': return m('Package_TO_SOT_SMD.3dshapes/SOT-89-3.step')
    if name == 'HDR_X101': return m('Connector_PinHeader_2.00mm.3dshapes/PinHeader_1x04_P2.00mm_Vertical.step', (0,3.03,0))
    if name == 'HDR_X102': return m('Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x04_P2.54mm_Vertical.step', (0,3.82,0))
    return None
def block(mod, ind):
    p,(x,y,z),r = mod
    t = '\t'*ind
    return (f'{t}(model "{p}"\n{t}\t(offset\n{t}\t\t(xyz {x:g} {y:g} {z:g})\n{t}\t)\n{t}\t(scale\n{t}\t\t(xyz 1 1 1)\n{t}\t)\n'
            f'{t}\t(rotate\n{t}\t\t(xyz 0 0 {r:g})\n{t}\t)\n{t})\n')
def strip_models(txt):
    return re.sub(r'\t+\(model "\$\{KICAD10_3DMODEL_DIR\}[^\n]*\n(?:\t+[^\n]*\n)*?\t+\)\n(?=\t*\))', '', txt)
def do_lib(lib):
    for p in glob.glob(lib+'/*.kicad_mod'):
        n = os.path.basename(p)[:-10]; txt = open(p).read()
        txt = re.sub(r'\t\(model "\$\{KICAD10_3DMODEL_DIR\}.*?\n\t\)\n', '', txt, flags=re.S)
        mod = model_for(n)
        if mod:
            assert txt.endswith(')\n'); txt = txt[:-2] + block(mod,1) + ')\n'
        open(p,'w').write(txt)
def do_pcb(pcb):
    lines = open(pcb).read().split('\n'); out=[]; i=0; cnt=0
    while i < len(lines):
        L = lines[i]
        if L.startswith('\t(footprint "'):
            j=i
            while lines[j] != '\t)': j+=1
            blk = '\n'.join(lines[i:j]) + '\n'
            blk = re.sub(r'\t\t\(model "\$\{KICAD10_3DMODEL_DIR\}.*?\n\t\t\)\n', '', blk, flags=re.S)
            name = L.split('"')[1].split(':')[1]
            ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
            mod = model_for(name, ref)
            if mod: blk += block(mod,2); cnt+=1
            out.extend(blk.rstrip('\n').split('\n')); out.append('\t)'); i=j+1; continue
        out.append(L); i+=1
    open(pcb,'w').write('\n'.join(out)); print(pcb, cnt, 'models')
for d in sys.argv[1:]:
    d = os.path.abspath(d); name = os.path.basename(d)
    do_lib(glob.glob(d+'/*.pretty')[0])
    for pcb in (os.path.join(d, name+'.kicad_pcb'), os.path.join(d, 'rekonstruktion', name+'_zonen.kicad_pcb')):
        if os.path.exists(pcb): do_pcb(pcb)
