# Forge DSP Hardware

Hardware-Erweiterungen für Forge DSP 96ELN/96ELN-3/96LN und ETON CORE D8, entworfen mit KiCad 10.

| Ordner | Inhalt | Issue |
|---|---|---|
| [`ExtensionPCB/`](ExtensionPCB) | Aufsatzplatine an Position 1 über X-EXT_AUDIO: Modulsteckplatz als Platinenrandstecker Samtec MEC1-120-02-F-D-EM2 (38 Kontakte, Module als 1,6-mm-Steckkarte), U.FL für S/PDIF, FFC-Buchse für X105 (SPI), Lötpad für 7,5 V | [#1](https://github.com/forge-dsp-community/hardware/issues/1) |

Geplante Einschubmodule: Bluetooth ([#2](https://github.com/forge-dsp-community/hardware/issues/2)),
CAN über MCP2515 ([firmware#73](https://github.com/forge-dsp-community/firmware/issues/73)).

**Stand:** Entwurf, nicht gefertigt, nicht am Gerät geprüft.

## Anschlüsse der Grundplatine

Belegung von X-EXT_AUDIO, X105 und EXT-SPDIF sowie die Versorgung stehen in
[#1](https://github.com/forge-dsp-community/hardware/issues/1).

## 3D-Modelle

- `ExtensionPCB/Straddle.pretty/FH12-16S-0.5SV.stp`: FFC-Buchse FH12-16S-0.5SV von **Hirose Electric Co., Ltd.**
  (© Hirose, von [hirose.com](https://www.hirose.com/)).
- `ExtensionPCB/Straddle.pretty/MEC1-120-02-F-D-EM2-TR.stp`: Platinenrandstecker MEC1-120-02-F-D-EM2 von
  **Samtec, Inc.** (© Samtec, über [samtec.com](https://www.samtec.com/products/mec1)/TraceParts).

Für beide gelten die Nutzungsbedingungen der Hersteller, nicht die Lizenz dieses Repos. Die übrigen Modelle kommen aus
der KiCad-Bibliothek.

Der Footprint `Samtec_MEC1-120-02-F-D-EM2` ist nach der Samtec-Zeichnung „Recommended PCB layout
MEC1-1XX-XX-XX-D-EMX-XX“ (Rev. H) gezeichnet; die Zeichnung selbst liegt nicht im Repo.
