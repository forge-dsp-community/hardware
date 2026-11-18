# Placement: ref -> (x, y, rotation, side) in board mm (origin top left, y down).
# Mechanical parts from the original exports (gen_pcb.px), the rest grouped like the original.
from parts import P

def px(x, y): return ((x - 4) * 63.5 / 749, (y - 9) * 38.1 / 451)

PLACE = {}
def at(ref, x, y, rot=0, side='B'): PLACE[ref] = (round(x, 3), round(y, 3), rot, side)

# ---- mechanical, fixed by the base board and the rear panel
at('X101', *px(404, 292), 180, 'B')          # pin 1 (square pad) of X-COM
at('X104', *px(55, 424), 90, 'B')          # pin 1 of X-USBI2S
at('X102', *px(506, 184), 90, 'F')         # USB B, pin 1; mouth at the top edge
at('X105', px(547.5, 0)[0], 2.67, 180, 'B')   # micro USB, "PCB edge" line of the footprint on the board edge
at('X103', px(360.5, 0)[0], 8.225, 180, 'F')  # microSD, card slot at the top edge
at('SW101', px(470.5, 0)[0], 3.7, 180, 'B')   # side switch in the notch, actuator to the edge
at('X107', *px(113, 432), 0, 'B')          # U.FL 24.576 MHz (left, as in the silkscreen)
at('X106', *px(180, 432), 0, 'B')          # U.FL 22.5792 MHz

# ---- XMOS (pin 1 top left: I2S/MCLK top left, QSPI top right, USB right, S/PDIF bottom)
at('IC114', *px(167.5, 190), 270, 'B')
# decoupling on the top side around the chip (vias from the pins into the planes)
for ref, x, y, r in [('C1', 10.6, 6.6, 90), ('C7', 12.6, 6.6, 90), ('C12', 14.6, 6.6, 90), ('C2', 16.6, 6.6, 90), ('C13', 18.6, 6.6, 90),
                     ('C8', 22.0, 11.2, 0), ('C3', 22.0, 13.2, 0), ('C9', 22.0, 19.0, 0), ('C14', 22.0, 20.8, 0),
                     ('C10', 17.6, 23.6, 90), ('C4', 15.6, 23.6, 90), ('C11', 13.6, 23.6, 90), ('C5', 11.6, 23.6, 90),
                     ('C15', 5.6, 11.6, 0), ('C16', 5.6, 13.6, 0), ('C6', 5.6, 15.6, 0), ('C17', 5.6, 17.6, 0)]:
    at(ref, x, y, r, 'F')
at('R3', 5.6, 19.4, 0, 'F'); at('C20', 5.6, 21.0, 0, 'F')          # PLL supply
at('Q101', 4.4, 18.6, 90, 'B'); at('C21', 4.4, 22.0, 0, 'B'); at('R4', 4.4, 15.0, 90, 'B')
at('R2', 22.0, 15.4, 0, 'F')                                          # RTUNE
at('R6', 23.8, 14.6, 0, 'B'); at('R7', 26.4, 15.0, 90, 'B'); at('C34', 21.4, 13.2, 90, 'B')   # VBUS sense
at('RN102A', 17.0, 24.4, 90, 'B'); at('RN102B', 15.6, 24.4, 90, 'B')
at('LED1', 17.0, 27.4, 90, 'B'); at('LED2', 15.6, 27.4, 90, 'B')
at('R1', 19.2, 24.4, 90, 'B')                                         # bleeder XMOS.3V3

# ---- clock select and I2S output (bottom left)
at('RN103', 3.3, 28.6, 0, 'B')
at('IC113', 12.0, 31.0, 0, 'B'); at('C32', 12.6, 28.6, 0, 'B')
at('IC112', 8.0, 28.8, 0, 'B')

# ---- QSPI flash shared between XMOS and base board
at('IC103', 26.4, 8.2, 90, 'B'); at('C30', 23.0, 3.4, 0, 'B')
at('IC102', 26.6, 21.4, 90, 'B'); at('C29', 22.5, 21.4, 90, 'B'); at('R12', 29.9, 21.4, 90, 'B')
at('IC104', 26.0, 28.6, 0, 'B'); at('C31', 27.7, 34.6, 90, 'B'); at('R10', 19.8, 29.2, 90, 'B')
at('IC106', 38.2, 27.0, 0, 'B'); at('IC105', 38.2, 31.0, 0, 'B'); at('IC107', 38.2, 23.0, 0, 'B')
at('R14', 41.4, 23.0, 90, 'B'); at('C33', 41.4, 27.0, 90, 'B'); at('C35', 41.4, 31.0, 90, 'B')

# ---- USB audio input and supplies of the XMOS (under the USB B socket, like the original)
at('SC102', 43.0, 17.8, 0, 'F'); at('P1', 42.6, 17.6, 90, 'B'); at('C18', 40.6, 16.4, 90, 'B'); at('C19', 44.3, 19.0, 90, 'B')
at('IC109', 32.0, 2.1, 90, 'B'); at('C22', 28.4, 1.6, 0, 'B'); at('C23', 34.9, 2.4, 90, 'B')
at('R13', 31.6, 5.3, 0, 'B'); at('R5', 34.2, 7.2, 0, 'B')
at('IC110', 32.9, 14.3, 0, 'B'); at('L1', 36.6, 15.0, 0, 'B'); at('C25', 29.4, 14.3, 90, 'B'); at('C27', 37.0, 17.7, 0, 'B')
at('C26', 31.0, 10.9, 90, 'B'); at('RN104A', 32.7, 10.9, 90, 'B'); at('RN104B', 34.4, 10.9, 90, 'B'); at('R11', 33.6, 19.4, 0, 'B')
at('IC108', 38.2, 35.2, 0, 'B'); at('RN105A', 41.6, 34.6, 90, 'B'); at('C24', 43.4, 34.6, 90, 'B')
at('IC111', 20.6, 5.8, 0, 'B'); at('R8', 17.6, 5.4, 0, 'B'); at('R9', 17.6, 7.0, 0, 'B'); at('C28', 14.2, 6.0, 90, 'B')

# ---- USB-COM (CP2102) right top
at('IC101', 58.6, 10.4, 0, 'B')
at('SC101', 52.2, 5.6, 0, 'B'); at('C103', 55.4, 5.6, 0, 'B'); at('C101', 54.0, 8.6, 90, 'B'); at('C102', 62.7, 6.6, 90, 'B')
at('R102', 62.2, 11.4, 90, 'B'); at('R101', 62.2, 14.6, 90, 'B')
at('RN105B', 43.6, 6.6, 0, 'B')

# ---- microSD pull-ups and decoupling (top side, below the card holder)
at('RN101', 31.2, 19.6, 0, 'F'); at('C104', 26.6, 19.2, 0, 'F'); at('C105', 26.6, 21.0, 0, 'F')

# X-PDI of the base board (2x3, populated, pins point up into this board) lies under
# x 19.9/22.4/25.0, y 34.0/36.6 (from FORGE_BASE_II-PADS.png, X-COM pin 1 as reference):
# no parts on the bottom side there (rule area in gen_pcb.py)
KEEPOUT_B = (18.1, 32.5, 26.7, 38.1)   # = cut-out in the outline (gen_pcb.py)

# park the rest outside the board until placed
k = 0
for p in P:
    if p['ref'] not in PLACE:
        at(p['ref'], 70 + (k % 8) * 5, (k // 8) * 4, 0, 'B'); k += 1
