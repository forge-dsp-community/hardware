#!/bin/bash
# build_out.sh <variante V30|V40d|V40e>
set -e
T=/tmp/claude-1000/-home-cronix--claude-spares-spare-C0uZXh/8ff8dc26-7d6e-41bb-9625-05510eb690c7/scratchpad
O=/home/cronix/avinavant/forge/pcbs/output
V=$1
case $V in
  V30)  SRC=$O/eln/V30;    PFX=ES9018_IV_OPA; NAME=forge_es9018_iv_opa_v30;  TITLE="Forge ES9018 I/V-Ausgang V3.0 (96ELN)";;
  V40d) SRC=$O/eln-3/V40d; PFX=ES90x8_IV_OPA; NAME=forge_es90x8_iv_opa_v40d; TITLE="Forge ES90x8 I/V-Ausgang V4.0d (96ELN-3)";;
  V40e) SRC=$O/eln-3/V40e; PFX=ES90x8_IV_OPA; NAME=forge_es90x8_iv_opa_v40e; TITLE="Forge ES90x8 I/V-Ausgang V4.0e (96ELN-3)";;
esac
OPN="U = OpAmps (Typ im Original nicht angegeben)"; OPC="OpAmp-Typ im Original nicht angegeben"
[ "$V" = V30 ] && OPN="U1 = LME49720 (Dual, Differenzverstaerker), U2 = LME49740 (Quad, I/V-Wandler)" && OPC="OpAmps: U1 LME49720, U2 LME49740"
W=$T/out/$V; D=/home/cronix/avinavant/kicad/$NAME
mkdir -p $D
/usr/bin/python3 -I $T/tools/outboard.py $SRC $PFX $W | grep -v -e COLS -e "^VS"
/usr/bin/python3 -I $T/tools/outnaming.py $W $V
H=$(/usr/bin/python3 -I $T/tools/adapt_out.py $W | awk '{print $2}')
rm -rf $D/forge_iv_opa.pretty
export OPNOTE="$OPC" SDIR=$W/ LIBNAME=forge_iv_opa BOARD_H=$H OUTBOARD=1 TITLE="$TITLE" BOARD_NOTE="Rekonstruktion aus Eagle-Renderings (300 dpi) - $TITLE" NOTE2="$OPN, X1 = Steckzunge zur Traegerplatine/Basisplatine; Referenzen und Werte nach Original-Schaltplan"
/usr/bin/python3 -I $T/tools/pcb.py $D $NAME
/usr/bin/python3 -I $T/tools/sch.py $D $NAME
/usr/bin/python3 -I $D/rekonstruktion/sch_layout.py $D   # Schaltplan: Gruppen verdrahtet, Labels nur zwischen Gruppen
cat > $D/fp-lib-table <<EOT
(fp_lib_table
  (version 7)
  (lib (name "forge_iv_opa")(type "KiCad")(uri "\${KIPRJMOD}/forge_iv_opa.pretty")(options "")(descr "Rekonstruierte Footprints Forge I/V-Ausgangsplatine"))
)
EOT
cat > $D/sym-lib-table <<EOT
(sym_lib_table
  (version 7)
  (lib (name "forge_iv_opa")(type "KiCad")(uri "\${KIPRJMOD}/forge_iv_opa.kicad_sym")(options "")(descr "Rekonstruierte Symbole Forge I/V-Ausgangsplatine"))
)
EOT
cd $D
kicad-cli pcb drc --refill-zones --save-board --schematic-parity -o $W/drc.rpt $NAME.kicad_pcb 2>&1 | tail -1
grep -E "^\[" $W/drc.rpt | sed 's/\].*/]/' | sort | uniq -c | sort -rn | tr '\n' ' '; echo
kicad-cli sch erc -o $W/erc.rpt $NAME.kicad_sch 2>&1 | grep -i verst
grep -E "^\[" $W/erc.rpt | sed 's/\].*/]/' | sort | uniq -c | tr '\n' ' '; echo
rm -f "$D/~$NAME.kicad_pro.lck"
