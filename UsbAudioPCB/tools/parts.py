# Netlist of the Forge DSP USB audio / COM board, rebuilt from the Eagle exports of the original
# (pcbs/usb/com_audio/V40i, USB_AUDIO-SCHEMA1..3.png, Mark Duprau, CC BY-NC-SA 4.0).
# One entry per part: ref, symbol, value, footprint, LCSC, side, {pin: net}.
# symbol "Device:R" etc. = KiCad library; "UA:<name>" = generated box symbol (see SYMBOLS).
# Deviations from the original are marked "PORT:".

GND, V33, X33, X10, X50 = 'GND', '+3V3', 'XMOS.3V3', 'XMOS.1V0', 'XMOS.5V0'

R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'

# generated symbols: name -> (left pins, right pins) as [(number, name, type)], description
SYMBOLS = {
    'XU208-128-TQ64': (
        [('22', 'USB.VDD.33', 'power_in'), ('3', 'VDD.IO.1', 'power_in'), ('13', 'VDD.IO.2', 'power_in'),
         ('34', 'VDD.IO.3', 'power_in'), ('44', 'VDD.IO.4', 'power_in'), ('55', 'VDD.IO.5', 'power_in'),
         ('27', 'USB.VDD', 'power_in'), ('9', 'VDD.1', 'power_in'), ('10', 'VDD.2', 'power_in'),
         ('20', 'VDD.3', 'power_in'), ('31', 'VDD.4', 'power_in'), ('39', 'VDD.5', 'power_in'),
         ('40', 'VDD.6', 'power_in'), ('41', 'VDD.7', 'power_in'), ('52', 'VDD.8', 'power_in'),
         ('56', 'VDD.9', 'power_in'), ('59', 'VDD.10', 'power_in'), ('53', 'PLL.VDD', 'power_in'),
         ('54', 'PLL.GND', 'power_in'), ('58', 'CLK', 'input'), ('57', 'RESET', 'input'),
         ('25', 'USB.DP', 'bidirectional'), ('26', 'USB.DM', 'bidirectional'), ('23', 'USB.VBUS', 'input'),
         ('24', 'USB.RTUNE', 'passive'),
         ('14', 'NC.1', 'no_connect'), ('16', 'NC.2', 'no_connect'), ('21', 'NC.3', 'no_connect'),
         ('30', 'NC.4', 'no_connect'), ('32', 'NC.5', 'no_connect'), ('33', 'NC.6', 'no_connect'),
         ('60', 'NC.7', 'no_connect'), ('61', 'NC.8', 'no_connect'), ('62', 'NC.9', 'no_connect'),
         ('63', 'NC.10', 'no_connect')],
        [('2', 'DOUT/DSD_R', 'output'), ('4', 'BCLK/DSD_CLK', 'output'), ('1', 'LRCK/DSD_L', 'output'),
         ('42', 'SPDIF', 'output'), ('64', 'MCLK', 'input'), ('28', 'SDA', 'bidirectional'),
         ('29', 'SCL', 'bidirectional'), ('43', 'GPI.0', 'input'), ('45', 'GPI.1', 'input'),
         ('47', 'GPI.2', 'input'), ('49', 'GPI.3', 'input'), ('50', 'GPI.4', 'input'), ('51', 'GPI.5', 'input'),
         ('46', 'GPI.6', 'input'), ('48', 'GPI.7', 'input'), ('35', 'GPIO.0/S_AUD_STRM', 'output'),
         ('36', 'GPIO.1/S_USB_HOST', 'output'), ('37', 'GPIO.2/S_DSD_MODE', 'output'),
         ('38', 'GPIO.3/MCLK_SEL', 'output'), ('5', 'GPIO.4/S_DSD_128', 'bidirectional'),
         ('6', 'GPIO.5/S_SP_1', 'bidirectional'), ('7', 'GPIO.6', 'bidirectional'), ('8', 'GPIO.7', 'bidirectional'),
         ('11', 'SPI.CS.N', 'output'), ('12', 'SPI.CLK', 'output'), ('15', 'QSPI.D0/SELF.PWR', 'bidirectional'),
         ('17', 'QSPI.D1/UAC1_SEL', 'bidirectional'), ('18', 'QSPI.D2/384K_EN', 'bidirectional'),
         ('19', 'QSPI.D3/HID_EN', 'bidirectional'), ('65', 'PAD', 'power_in')],
        'XMOS xCORE-200 XU208-128-TQ64, USB 2.0 audio (pin names as in the original schematic)'),
    'CP2102': (
        [('7', 'REGIN', 'power_in'), ('8', 'VBUS', 'input'), ('6', 'VDD', 'power_in'), ('4', 'D+', 'bidirectional'),
         ('5', 'D-', 'bidirectional'), ('3', 'GND', 'power_in'), ('29', 'EP', 'power_in')],
        [('9', 'RST', 'input'), ('12', 'SUSPEND', 'output'), ('11', '~{SUSPEND}', 'output'), ('2', 'RI', 'input'),
         ('1', 'DCD', 'input'), ('28', 'DTR', 'output'), ('27', 'DSR', 'input'), ('26', 'TXD', 'output'),
         ('25', 'RXD', 'input'), ('24', 'RTS', 'output'), ('23', 'CTS', 'input')]
        + [(str(n), 'NC', 'no_connect') for n in [10] + list(range(13, 23))],
        'Silicon Labs CP2102 USB to UART bridge, QFN-28'),
    'SN74CB3Q3245PW': (
        [(str(n + 1), f'A{n}', 'bidirectional') for n in range(1, 9)] + [('1', 'NC', 'no_connect'), ('10', 'GND', 'power_in')],
        [(str(19 - n), f'B{n}', 'bidirectional') for n in range(1, 9)] + [('19', '~{OE}', 'input'), ('20', 'VCC', 'power_in')],
        'TI SN74CB3Q3245 8-bit FET bus switch, TSSOP-20'),
    'SN74CB3Q3305': (
        [('2', 'A1', 'bidirectional'), ('5', 'A2', 'bidirectional'), ('1', 'OE1', 'input'), ('7', 'OE2', 'input'), ('4', 'GND', 'power_in')],
        [('3', 'B1', 'bidirectional'), ('6', 'B2', 'bidirectional'), ('8', 'VCC', 'power_in')],
        'TI SN74CB3Q3305 dual FET bus switch, active-high OE'),
    'IS25LQ016B': (
        [('1', '~{CS}', 'input'), ('6', 'SCK', 'input'), ('5', 'SI/IO0', 'bidirectional'), ('2', 'SO/IO1', 'bidirectional'), ('4', 'GND', 'power_in')],
        [('3', '~{WP}/IO2', 'bidirectional'), ('7', '~{HOLD}/IO3', 'bidirectional'), ('8', 'VCC', 'power_in')],
        'ISSI IS25LQ016B 16 Mbit QSPI flash, SOIC-8 150 mil'),
    'TPD2E001': (
        [('1', 'VCC', 'passive'), ('4', 'GND', 'passive'), ('2', 'NC', 'no_connect')],
        [('3', 'IO1', 'passive'), ('5', 'IO2', 'passive')],
        'TI TPD2E001 2-channel ESD protection, SOT-553 (DRL)'),
    'LM3674-ADJ': (
        [('1', 'VIN', 'power_in'), ('3', 'EN', 'input'), ('2', 'GND', 'power_in')],
        [('5', 'SW', 'power_out'), ('4', 'FB', 'input')],
        'TI LM3674 2 MHz 600 mA step-down, adjustable, SOT-23-5'),
    'TLV70233': (
        [('1', 'IN', 'power_in'), ('3', 'EN', 'input'), ('2', 'GND', 'power_in')],
        [('5', 'OUT', 'power_out'), ('4', 'NC', 'no_connect')],
        'TI TLV70233 300 mA LDO 3.3 V, SOT-23-5'),
    'STM1061': (
        [('3', 'VCC', 'power_in'), ('2', 'GND', 'power_in')],
        [('1', '~{OUT}', 'open_collector')],
        'ST STM1061 voltage detector, open drain, SOT-23-3 (threshold for 3.3 V rail)'),
    'ADM1085': (
        [('6', 'VCC', 'power_in'), ('3', 'VIN', 'input'), ('1', 'ENIN', 'input'), ('5', 'CEXT', 'passive'), ('2', 'GND', 'power_in')],
        [('4', 'ENOUT', 'output')],
        'ADI ADM1085 simple sequencer, active-high, SC70-6'),
    'SN74LVC1G04': (
        [('2', 'A', 'input'), ('3', 'GND', 'power_in'), ('1', 'NC', 'no_connect')],
        [('4', 'Y', 'output'), ('5', 'VCC', 'power_in')],
        'Single inverter, SOT-23-5'),
    'SN74LVC1G08': (
        [('1', 'A', 'input'), ('2', 'B', 'input'), ('3', 'GND', 'power_in')],
        [('4', 'Y', 'output'), ('5', 'VCC', 'power_in')],
        'Single AND gate, SOT-23-5'),
    'OSC_4PIN': (
        [('4', 'VDD', 'power_in'), ('1', 'EN', 'input'), ('2', 'GND', 'power_in')],
        [('3', 'OUT', 'output')],
        'Crystal oscillator 3.2x2.5 mm'),
    'USB_MICRO_B': (
        [('1', 'VBUS', 'passive'), ('2', 'D-', 'passive'), ('3', 'D+', 'passive'), ('4', 'ID', 'passive'), ('5', 'GND', 'passive')],
        [('SH', 'SHIELD', 'passive')],
        'Molex 47346-1001 micro USB B, bottom mount with flange'),
    'USB_B': (
        [('1', 'VBUS', 'passive'), ('2', 'D-', 'passive'), ('3', 'D+', 'passive'), ('4', 'GND', 'passive')],
        [('SH', 'SHIELD', 'passive')],
        'USB B receptacle, through hole (original: FCI/Berg 61729-0010BLF)'),
    'MICROSD_DM3BT': (
        [('1', 'DAT2', 'passive'), ('2', 'CD/DAT3', 'passive'), ('3', 'CMD/DI', 'passive'), ('4', 'VDD', 'passive'),
         ('5', 'CLK', 'passive'), ('6', 'VSS', 'passive'), ('7', 'DAT0/DO', 'passive'), ('8', 'DAT1/RSV', 'passive')],
        [('9', 'COMMON', 'passive'), ('10', 'CARD_SWITCH', 'passive'), ('SH', 'SHIELD', 'passive')],
        'Hirose DM3BT-DSF-PEJS microSD push-push with card detect'),
    'UFL': (
        [('1', 'SIG', 'passive')], [('2', 'GND', 'passive')], 'Hirose U.FL-R-SMT-1'),
    'SW_SIDE': (
        [('1', '1', 'passive')], [('2', '2', 'passive'), ('MP', 'MP', 'passive')],
        'Side-actuated tact switch with mounting pads'),
}

# ref, symbol, value, footprint, lcsc, side, pins
P = []
def part(ref, sym, val, fp, lcsc='', side='B', **pins):
    P.append(dict(ref=ref, sym=sym, val=val, fp=fp, lcsc=lcsc, side=side, pins={k.lstrip('_'): v for k, v in pins.items()}))
def R(ref, val, a, b, lcsc='', fp=R0603): part(ref, 'Device:R', val, fp, lcsc, _1=a, _2=b)
def C(ref, val, a, b, lcsc='', fp=C0603): part(ref, 'Device:C', val, fp, lcsc, _1=a, _2=b)

# ---------------- sheet 1: USB-COM (CP2102), microSD, connector to the base board
part('X105', 'UA:USB_MICRO_B', 'Molex 47346-1001', 'Connector_USB:USB_Micro-B_Molex_47346-0001', '', 'B',
     _1='COM.VBUS', _2='COM.D-', _3='COM.D+', _4='', _5=GND, SH=GND)
part('SC101', 'UA:TPD2E001', 'TPD2E001DRLR', 'Package_TO_SOT_SMD:SOT-553', '', 'B',
     _1='COM.VBUS', _2='', _3='COM.D+', _4=GND, _5='COM.D-')
C('C103', '4.7µF/16V', 'COM.VBUS', GND, fp=C0805)
C('C101', '100nF', V33, GND)
C('C102', '4.7µF/16V', V33, GND, fp=C0805)
part('IC101', 'UA:CP2102', 'CP2102-GMR', 'Package_DFN_QFN:QFN-28-1EP_5x5mm_P0.5mm_EP3.35x3.35mm', '', 'B',
     _7='',                    # PORT: REGIN open as in the original (self-powered, VDD from the base board)
     _8='COM.VBUS', _6=V33, _4='COM.D+', _5='COM.D-', _3=GND, _29=GND,
     _9='COM.RST', _12='', _11='COM.SUSPEND', _2=V33, _1=GND, _28='EXT.USB.DTR_DSR', _27='FIRMWARE.UPDATE',
     _26='EXT.USB.RX', _25='EXT.USB.TX', _24='COM.RTS_CTS', _23='COM.RTS_CTS',
     **{f'_{n}': '' for n in [10] + list(range(13, 23))})
R('R102', '4K7', V33, 'COM.RST')
R('R101', '10K', 'COM.SUSPEND', GND)
part('X101', 'Connector_Generic:Conn_02x06_Odd_Even', 'X-COM 2x6 2.54', 'Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical', '', 'B',
     _1=GND, _2=GND, _3='FIRMWARE.UPDATE', _4='SPI1.~{CS}', _5='EXT.USB.TX', _6='SPI1.MOSI', _7='EXT.USB.RX',
     _8='SPI1.SCK', _9='EXT.USB.DTR_DSR', _10='SPI1.MISO', _11=V33, _12='CARD.SWITCH')
part('X103', 'UA:MICROSD_DM3BT', 'DM3BT-DSF-PEJS', 'Connector_Card:microSD_HC_Hirose_DM3BT-DSF-PEJS', '', 'F',
     _1='', _2='SPI1.~{CS}', _3='SPI1.MOSI', _4=V33, _5='SPI1.SCK', _6=GND, _7='SPI1.MISO', _8='SD.DAT1',
     _9=GND, _10='CARD.SWITCH', SH=GND)
part('RN101', 'Device:R_Pack04', '4x47K', 'Resistor_SMD:R_Array_Convex_4x0603', '', 'B',
     _1='SD.DAT1', _8=V33, _2='SPI1.MISO', _7=V33, _3='CARD.SWITCH', _6=V33, _4=GND, _5='FIRMWARE.UPDATE')
C('C104', '100nF', V33, GND)
C('C105', '4.7µF/6.3V', V33, GND, fp=C0805)
part('SW101', 'UA:SW_SIDE', 'FIRMWARE UPDATE', 'Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010', '', 'B',
     _1='FIRMWARE.UPDATE', _2='SW.UPD', MP=GND)
R('RN105B', '2K2', 'SW.UPD', V33)       # PORT: single resistors instead of the 2K2 array RN105

# ---------------- sheet 2: XMOS, clock select, QSPI flash shared with the base board
xu = dict(_22=X33, _3=X33, _13=X33, _34=X33, _44=X33, _55=X33,
          _27=X10, _9=X10, _10=X10, _20=X10, _31=X10, _39=X10, _40=X10, _41=X10, _52=X10, _56=X10, _59=X10,
          _53='XMOS.PLL.VDD', _54=GND, _58='XMOS.CLK', _57='XMOS.POR', _25='USB.1.DP', _26='USB.1.DM',
          _23='XMOS.VBUS.SENSE', _24='XMOS.RTUNE',
          _2='I2S.SDATA.X', _4='I2S.BCLK.X', _1='I2S.LRCK.X', _42='SPDIF.X', _64='XMOS.MCLK',
          _35='XMOS.LED1', _36='XMOS.LED2', _38='MCLK.SEL',
          _11='XQ.CS', _12='XQ.CLK', _15='XQ.D0', _17='XQ.D1', _18='XQ.D2', _19='XQ.D3', _65=GND)
for n in (14, 16, 21, 30, 32, 33, 60, 61, 62, 63, 28, 29, 43, 45, 47, 49, 50, 51, 46, 48, 37, 5, 6, 7, 8):
    xu[f'_{n}'] = ''
part('IC114', 'UA:XU208-128-TQ64', 'XU208-128-TQ64-C10', 'Package_QFP:TQFP-64-1EP_10x10mm_P0.5mm_EP5.305x5.305mm_ThermalVias', '', 'B', **xu)
for i in range(1, 7): C(f'C{i}', '100nF', X33, GND)
for i in range(7, 18): C(f'C{i}', '100nF', X10, GND)
R('R3', '4R7', X10, 'XMOS.PLL.VDD')
C('C20', '100nF', 'XMOS.PLL.VDD', GND)
part('Q101', 'UA:OSC_4PIN', '24.000MHz', 'Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm', '', 'B',
     _4=X33, _1=X33, _2=GND, _3='XMOS.CLK.OSC')
C('C21', '100nF', X33, GND)
R('R4', '50R', 'XMOS.CLK.OSC', 'XMOS.CLK')       # PORT: E24 51R would also do
R('R6', '10K', X50, 'XMOS.VBUS.SENSE')
R('R7', '47K', X50, GND)
C('C34', '100nF', 'XMOS.VBUS.SENSE', GND)
R('R2', '43R2', 'XMOS.RTUNE', GND)
part('RN103', 'Device:R_Pack04', '4x50R', 'Resistor_SMD:R_Array_Convex_4x0603', '', 'B',
     _1='I2S.SDATA.X', _8='IN.I2S.SDATA.0', _3='I2S.BCLK.X', _6='IN.I2S.BCLK.0', _2='I2S.LRCK.X', _7='IN.I2S.LRCK.0',
     _4='SPDIF.X', _5='IN.SPDIF.1')
part('X104', 'Connector_Generic:Conn_02x02_Odd_Even', 'X-USBI2S 2x2 2.54', 'Connector_PinHeader_2.54mm:PinHeader_2x02_P2.54mm_Vertical', '', 'B',
     _1='IN.SPDIF.1', _2='IN.I2S.BCLK.0', _3='IN.I2S.LRCK.0', _4='IN.I2S.SDATA.0')
part('LED1', 'Device:LED', 'AUDIO STREAM', 'LED_SMD:LED_0603_1608Metric', '', 'B', _1=GND, _2='LED1.A')
part('LED2', 'Device:LED', 'USB HOST', 'LED_SMD:LED_0603_1608Metric', '', 'B', _1=GND, _2='LED2.A')
R('RN102A', '330R', 'XMOS.LED1', 'LED1.A')
R('RN102B', '330R', 'XMOS.LED2', 'LED2.A')
part('X106', 'UA:UFL', '22.5792MHz IN', 'Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical', 'C88373', 'B', _1='MCLK.22M', _2=GND)
part('X107', 'UA:UFL', '24.576MHz IN', 'Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical', 'C88373', 'B', _1='MCLK.24M', _2=GND)
part('IC113', 'UA:SN74CB3Q3305', 'SN74CB3Q3305DCUR', 'Package_SO:VSSOP-8_2.3x2mm_P0.5mm', '', 'B',
     _1='MCLK.SEL', _2='MCLK.22M', _3='XMOS.MCLK', _4=GND, _5='MCLK.24M', _6='XMOS.MCLK', _7='MCLK.SEL.N', _8=X33)
C('C32', '100nF', X33, GND)
part('IC112', 'UA:SN74LVC1G04', '74LVC1G04DBV', 'Package_TO_SOT_SMD:SOT-23-5', '', 'B',
     _2='MCLK.SEL', _4='MCLK.SEL.N', _5=X33, _3=GND, _1='')
fl_x = dict(_2='XQ.D2', _3='XQ.D1', _4='XQ.CS', _5='XQ.D3', _6='XQ.CLK', _7='XQ.D0', _8='', _9='', _1='', _10=GND, _20=V33,
            _18='FL.IO2', _17='FL.IO1', _16='FL.~{CS}', _15='FL.IO3', _14='FL.SCK', _13='FL.IO0', _12='', _11='',
            _19='FL.XMOS.~{OE}')
part('IC103', 'UA:SN74CB3Q3245PW', 'SN74CB3Q3245PW', 'Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm', '', 'B', **fl_x)
C('C30', '100nF', V33, GND)
fl_m = dict(_2='SPI1.MOSI', _3='SPI1.SCK', _4='FL.PU', _5='FL.PU', _6='SPI1.MISO', _7='SPI1.~{CS}', _8='', _9='', _1='',
            _10=GND, _20=V33, _18='FL.IO0', _17='FL.SCK', _16='FL.IO2', _15='FL.IO3', _14='FL.IO1', _13='FL.~{CS}',
            _12='', _11='', _19='FL.MB.~{OE}')
part('IC104', 'UA:SN74CB3Q3245PW', 'SN74CB3Q3245PW', 'Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm', '', 'B', **fl_m)
C('C31', '100nF', V33, GND)
R('R10', '10K', V33, 'FL.PU')
part('IC102', 'UA:IS25LQ016B', 'IS25LQ016B-JNLE', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', '', 'B',
     _1='FL.~{CS}', _2='FL.IO1', _3='FL.IO2', _4=GND, _5='FL.IO0', _6='FL.SCK', _7='FL.IO3', _8=V33)
C('C29', '100nF', V33, GND)
R('R12', '1K', V33, 'FL.~{CS}')
part('IC105', 'UA:SN74LVC1G04', '74LVC1G04DBV', 'Package_TO_SOT_SMD:SOT-23-5', '', 'B',
     _2='FL.XMOS.~{OE}', _4='FL.MB.~{OE}', _5=V33, _3=GND, _1='')
part('IC106', 'UA:SN74LVC1G08', '74LVC1G08DBV', 'Package_TO_SOT_SMD:SOT-23-5', '', 'B',
     _1='XMOS.OFF', _2='CARD.SWITCH', _4='FL.XMOS.~{OE}', _5=V33, _3=GND)
part('IC107', 'UA:SN74LVC1G04', '74LVC1G04DBV', 'Package_TO_SOT_SMD:SOT-23-5', '', 'B',
     _2='XMOS.ON', _4='XMOS.OFF', _5=V33, _3=GND, _1='')
R('R14', '1K', X33, 'XMOS.ON')
R('R1', '10K', X33, GND)
C('C33', '100nF', V33, GND)
C('C35', '100nF', V33, GND)

# ---------------- sheet 3: USB audio connector and supplies of the XMOS
part('X102', 'UA:USB_B', 'USB-B 61729-0010BLF', 'Connector_USB:USB_B_OST_USB-B1HSxx_Horizontal', '', 'F',
     _1='AUD.VBUS', _2='USB.1.DM', _3='USB.1.DP', _4=GND, SH=GND)
part('SC102', 'UA:TPD2E001', 'TPD2E001DRLR', 'Package_TO_SOT_SMD:SOT-553', '', 'B',
     _1='AUD.VBUS', _2='', _3='USB.1.DM', _4=GND, _5='USB.1.DP')
C('C18', '100nF', 'AUD.VBUS', GND)
part('P1', 'Device:FerriteBead', 'BLM21BB050SN1', 'Inductor_SMD:L_0805_2012Metric', '', 'B', _1='AUD.VBUS', _2=X50)
C('C19', '100nF', X50, GND)
part('IC109', 'UA:TLV70233', 'TLV70233DBVR', 'Package_TO_SOT_SMD:SOT-23-5', '', 'B',
     _1=X50, _3='XMOS.EN', _2=GND, _5=X33, _4='')
R('R13', '1K', V33, 'XMOS.EN')
R('R5', '2K2', 'XMOS.EN', GND)
C('C22', '4.7µF/16V', X50, GND, fp=C0805)
C('C23', '4.7µF/16V', X33, GND, fp=C0805)
part('IC108', 'UA:STM1061', 'STM1061N27WX6F', 'Package_TO_SOT_SMD:SOT-23', '', 'B', _3=X33, _2=GND, _1='XMOS.3V3.PG')
R('RN105A', '2K2', X33, 'XMOS.3V3.PG')
C('C24', '100nF', X33, GND)
part('IC110', 'UA:LM3674-ADJ', 'LM3674MF-ADJ', 'Package_TO_SOT_SMD:SOT-23-5', '', 'B',
     _1=X50, _3='XMOS.3V3.PG', _2=GND, _5='XMOS.SW', _4='XMOS.FB')
part('L1', 'Device:L', '2.2µH LQM2HPN2R2MG0L', 'Inductor_SMD:L_1008_2520Metric', '', 'B', _1='XMOS.SW', _2=X10)
C('C25', '4.7µF/16V', X50, GND, fp=C0805)
C('C26', '330pF', X10, 'XMOS.FB')
R('RN104A', '10K', X10, 'XMOS.FB')
R('RN104B', '10K', 'XMOS.FB', GND)
C('C27', '10µF/10V', X10, GND, fp=C0805)
R('R11', '330R', X10, GND)
part('IC111', 'UA:ADM1085', 'ADM1085AKSZ', 'Package_TO_SOT_SMD:SOT-363_SC-70-6', '', 'B',
     _6=X33, _3='XMOS.1V0.DIV', _1='XMOS.3V3.PG', _5='XMOS.CEXT', _2=GND, _4='XMOS.POR')
R('R8', '3K9', X10, 'XMOS.1V0.DIV')
R('R9', '10K', 'XMOS.1V0.DIV', GND)
C('C28', '2.2nF', 'XMOS.CEXT', GND)

if __name__ == '__main__':
    from collections import Counter
    nets = Counter(n for p in P for n in p['pins'].values() if n)
    print(len(P), 'parts,', len(nets), 'nets')
    for n, k in sorted(nets.items()):
        if k < 2: print('single-pin net:', n)
