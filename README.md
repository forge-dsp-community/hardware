# Forge DSP Hardware

Hardware-Erweiterungen für Forge DSP 96ELN/96ELN-3/96LN und ETON CORE D8, entworfen mit KiCad 10.

| Ordner | Inhalt | Issue |
|---|---|---|
| [`ExtensionPCB/`](ExtensionPCB) | Aufsatzplatine an Position 1 über X-EXT_AUDIO: Modulsteckplatz als Platinenrandstecker Samtec MEC1-120-02-F-D-EM2 (38 Kontakte, Module als 1,6-mm-Steckkarte), U.FL für S/PDIF, liegende FFC-Buchse für X105 (SPI), Lötpad für 7,5 V | [#1](https://github.com/forge-dsp-community/hardware/issues/1) |
| [`UsbAudioPCB/`](UsbAudioPCB) | Nachbau der USB-Audio/COM-Platine V4.0i des Originals: XMOS XU208 (USB-Audio, I²S/S/PDIF an X104), CP2102 (USB-COM), microSD, QSPI-Flash, Stecker X101/X104 zum Mainboard. Neu: Aussparung über X-PDI für einen Dupont-Stecker. Erzeugt aus `tools/` | [#3](https://github.com/forge-dsp-community/hardware/issues/3) |

Geplante Einschubmodule: Bluetooth ([#2](https://github.com/forge-dsp-community/hardware/issues/2)),
CAN über MCP2515 ([firmware#73](https://github.com/forge-dsp-community/firmware/issues/73)).

**Stand:** Entwürfe, nicht gefertigt, nicht am Gerät geprüft. Die USB-Audio-Platine ist platziert, aber noch nicht geroutet.

## Ansichten

| | Seite F (KiCad vorne) | Seite B (KiCad hinten) |
|---|---|---|
| ExtensionPCB | ![ExtensionPCB Seite F](ExtensionPCB/images/ExtensionPCB-3d-top.png) | ![ExtensionPCB Seite B](ExtensionPCB/images/ExtensionPCB-3d-bottom.png) |
| UsbAudioPCB (Platzierung, ohne Leiterbahnen) | ![UsbAudioPCB Seite F](UsbAudioPCB/images/UsbAudioPCB-3d-top.png) | ![UsbAudioPCB Seite B](UsbAudioPCB/images/UsbAudioPCB-3d-bottom.png) |

3D-Renderings aus KiCad (`kicad-cli pcb render`). Die USB-Audio-Platine sitzt im Forge mit **Seite B nach oben**:
Seite F zeigt zum Mainboard und trägt wie im Original nur microSD-Halter und USB-B-Buchse an der Kante, alle anderen
Bauteile sitzen auf B, die Stiftleisten X101/X104 stecken von B durch die Platine ins Mainboard. Bei der USB-Audio-Platine fehlen noch die Modelle von USB-B-Buchse,
microSD-Halter und Taster.

## Anschlüsse der Grundplatine

Belegung von X-EXT_AUDIO, X105 und EXT-SPDIF sowie die Versorgung stehen in
[#1](https://github.com/forge-dsp-community/hardware/issues/1).

## 3D-Modelle

- `ExtensionPCB/Straddle.pretty/FH12-16S-0.5SH.stp` (liegend, eingebaut) und `FH12-16S-0.5SV.stp` (stehend, frühere
  Fassung): FFC-Buchsen von **Hirose Electric Co., Ltd.** (© Hirose, von [hirose.com](https://www.hirose.com/)).
- `ExtensionPCB/Straddle.pretty/MEC1-120-02-F-D-EM2-TR.stp`: Platinenrandstecker MEC1-120-02-F-D-EM2 von
  **Samtec, Inc.** (© Samtec, über [samtec.com](https://www.samtec.com/products/mec1)/TraceParts).

Für beide gelten die Nutzungsbedingungen der Hersteller, nicht die Lizenz dieses Repos. Die übrigen Modelle kommen aus
der KiCad-Bibliothek.

Der Footprint `Samtec_MEC1-120-02-F-D-EM2` ist nach der Samtec-Zeichnung „Recommended PCB layout
MEC1-1XX-XX-XX-D-EMX-XX“ (Rev. H) gezeichnet; die Zeichnung selbst liegt nicht im Repo.

## Lizenz der USB-Audio-Platine

`UsbAudioPCB/` ist ein Nachbau der Platine `pcbs/usb/com_audio/V40i` von **Mark Duprau** (Forge DSP) und steht wie das
Original unter [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Abweichungen vom Original sind in
`UsbAudioPCB/tools/parts.py` und `placement.py` mit `PORT` markiert.
