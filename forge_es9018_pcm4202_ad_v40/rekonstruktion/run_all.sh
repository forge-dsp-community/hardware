set -e
cd "${REK_TOOLS:-tools}"
/usr/bin/python3 -I extract.py | tail -2
/usr/bin/python3 -I naming.py > /dev/null
/usr/bin/python3 -I cmp.py > /dev/null
/usr/bin/python3 -I merge.py
/usr/bin/python3 -I naming.py | grep -e Netze -e Vias
