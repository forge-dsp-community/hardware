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
at('X105', px(547.5, 0)[0], 2.67, 0, 'B')   # micro USB, "PCB edge" line of the footprint on the board edge
at('X103', px(360.5, 0)[0], 8.225, 180, 'F')  # microSD, card slot at the top edge
at('SW101', px(470.5, 0)[0], 3.7, 0, 'B')   # side switch in the notch, actuator to the edge
at('X107', *px(113, 432), 0, 'B')          # U.FL 24.576 MHz (left, as in the silkscreen)
at('X106', *px(180, 432), 0, 'B')          # U.FL 22.5792 MHz

# ---- XMOS (pin 1 top left: I2S/MCLK top left, QSPI top right, USB right, S/PDIF bottom)
at('IC114', *px(167.5, 190), 270, 'B')
# decoupling: ring on B around the chip like the original (side F faces the base board and stays
# free of parts); ~2.4 mm outside the pad tips, signals escape between pads and ring
for ref, x, y, r in [('C1', 11.0, 6.4, 0), ('C7', 14.0, 6.4, 0), ('C2', 17.0, 6.4, 0), ('C3', 20.1, 6.4, 0),  # top: 3, 9/10, 13; C3 for pin 22
                     ('C8', 21.4, 10.4, 90), ('C9', 21.4, 18.1, 90), ('C10', 21.4, 21.15, 90),           # right: 20, 27, 31 (USB/VBUS/RTUNE in between)
                     ('C12', 8.6, 23.4, 0), ('C5', 11.6, 23.4, 0), ('C11', 14.6, 23.4, 0), ('C4', 17.6, 23.4, 0), ('C13', 20.65, 23.4, 0),  # bottom
                     ('C17', 5.6, 11.4, 90), ('C16', 5.6, 14.45, 90), ('C6', 5.6, 17.5, 90), ('C15', 5.6, 20.55, 90)]:   # left: 59, 56, 55, 52
    at(ref, x, y, r, 'B')
at('R3', 3.4, 14.4, 90, 'B'); at('C20', 3.4, 17.4, 90, 'B')          # PLL supply (pin 53)
at('Q101', 4.4, 6.4, 90, 'B'); at('C21', 3.4, 10.0, 90, 'B'); at('R4', 7.0, 6.8, 90, 'B')
at('R2', 23.4, 14.0, 90, 'B')                                         # RTUNE
at('R6', 26.0, 12.9, 0, 'B'); at('R7', 26.0, 16.3, 0, 'B'); at('C34', 26.0, 14.6, 0, 'B')   # VBUS sense
at('RN102A', 17.2, 29.45, 90, 'B'); at('RN102B', 15.6, 29.45, 90, 'B')
at('LED1', 17.2, 26.4, 90, 'B'); at('LED2', 15.6, 26.4, 90, 'B')
at('R1', 20.2, 26.6, 90, 'B')                                         # bleeder XMOS.3V3

# ---- clock select and I2S output (bottom left)
at('RN103', 3.3, 28.9, 0, 'B')
at('IC113', 12.0, 31.0, 0, 'B'); at('C32', 12.6, 28.6, 0, 'B')
at('IC112', 7.6, 28.8, 0, 'B')

# ---- QSPI flash shared between XMOS and base board
at('IC103', 26.4, 8.2, 90, 'B'); at('C30', 24.4, 3.4, 0, 'B')
at('IC102', 26.6, 20.6, 90, 'B'); at('C29', 22.9, 18.5, 90, 'B'); at('R12', 22.9, 21.6, 90, 'B')
at('IC104', 25.6, 28.6, 0, 'B'); at('C31', 27.7, 34.6, 90, 'B'); at('R10', 20.2, 29.65, 90, 'B')
at('IC106', 38.2, 26.6, 0, 'B'); at('IC105', 38.2, 30.2, 0, 'B'); at('IC107', 38.2, 23.0, 0, 'B')
at('R14', 41.4, 23.0, 90, 'B'); at('C33', 41.4, 26.6, 90, 'B'); at('C35', 41.4, 30.2, 90, 'B')

# ---- USB audio input and supplies of the XMOS (under the USB B socket, like the original)
at('SC102', 40.2, 16.6, 0, 'B'); at('P1', 42.9, 17.6, 90, 'B'); at('C18', 40.5, 13.4, 90, 'B'); at('C19', 39.2, 19.7, 0, 'B')
at('IC109', 32.0, 2.1, 90, 'B'); at('C22', 28.4, 1.6, 0, 'B'); at('C23', 34.9, 2.4, 90, 'B')
at('R13', 31.6, 5.3, 0, 'B'); at('R5', 34.2, 7.2, 0, 'B')
at('IC110', 32.9, 14.3, 0, 'B'); at('L1', 37.0, 15.0, 0, 'B'); at('C25', 29.4, 14.3, 90, 'B'); at('C27', 37.0, 17.7, 0, 'B')
at('C26', 31.0, 10.9, 90, 'B'); at('RN104A', 32.7, 10.9, 90, 'B'); at('RN104B', 34.4, 10.9, 90, 'B'); at('R11', 36.2, 20.2, 0, 'B')
at('IC108', 38.2, 33.8, 0, 'B'); at('RN105A', 41.4, 33.8, 90, 'B'); at('C24', 43.6, 33.2, 90, 'B')
at('IC111', 43.7, 21.0, 90, 'B'); at('R8', 43.6, 24.2, 90, 'B'); at('R9', 43.6, 27.2, 90, 'B'); at('C28', 43.6, 30.2, 90, 'B')

# ---- USB-COM (CP2102) right top
at('IC101', 58.2, 10.4, 0, 'B')
at('SC101', 52.2, 5.6, 0, 'B'); at('C103', 55.4, 5.6, 0, 'B'); at('C101', 54.0, 8.6, 90, 'B'); at('C102', 62.6, 6.6, 90, 'B')
at('R102', 62.2, 11.4, 90, 'B'); at('R101', 62.2, 14.6, 90, 'B')
at('RN105B', 43.6, 6.6, 0, 'B')

# ---- microSD pull-ups and decoupling (top side, below the card holder)
at('RN101', 31.6, 19.6, 0, 'B'); at('C104', 30.9, 17.4, 0, 'B'); at('C105', 33.4, 18.2, 90, 'B')

# X-PDI of the base board (2x3, populated, pins point up towards side F of this board) lies under
# x 19.9/22.4/25.0, y 34.0/36.6 (from FORGE_BASE_II-PADS.png, X-COM pin 1 as reference):
# no parts on side F there (rule area in gen_pcb.py), cut-out through the board
KEEPOUT_B = (18.1, 32.5, 26.7, 38.1)   # = cut-out in the outline (gen_pcb.py)

at('C14', 5.6, 23.4, 0, 'B')
# park the rest outside the board until placed
k = 0
for p in P:
    if p['ref'] not in PLACE:
        at(p['ref'], 70 + (k % 8) * 5, (k // 8) * 4, 0, 'B'); k += 1

# ---- copper zones (net, layer, priority, polygon in board mm); higher priority wins
BOARD = [(-1, -1), (65, -1), (65, 40), (-1, 40)]
ZONES = [
    ('GND', 'In1_Cu', 0, BOARD),
    ('+3V3', 'In2_Cu', 0, BOARD),
    # XMOS.3V3: around the XMOS (vias of the 3.3 V pins sit outside the pad rows), the clock section bottom
    # left (IC112/IC113) and along the top edge to the LDO IC109/C23 (x 30-36)
    ('XMOS.3V3', 'In2_Cu', 1, [(-1, -1), (37.4, -1), (37.4, 6.2), (22.9, 6.2), (22.9, 27.0), (18.0, 27.0), (18.0, 40), (-1, 40)]),
    # XMOS.1V0: under the chip up to between the pad rows (1.0 V vias inside, 3.3 V vias outside) and a
    # band at the height of pins 17-20 under IC103 to the buck converter (C26/RN104, L1/C27/R11)
    ('XMOS.1V0', 'In2_Cu', 2, [(7.9, 9.3), (39.6, 9.3), (39.6, 21.2), (34.6, 21.2), (34.6, 13.4), (19.8, 13.4), (19.8, 21.3), (7.9, 21.3)]),
]
