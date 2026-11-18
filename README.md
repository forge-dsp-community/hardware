# Forge DSP Hardware

Hardware-Erweiterungen für Forge DSP 96ELN/96ELN-3/96LN und ETON CORE D8, entworfen mit KiCad 10.

| Ordner | Inhalt | Issue |
|---|---|---|
| [`ExtensionPCB/`](ExtensionPCB) | Aufsatzplatine an Position 1 über X-EXT_AUDIO: 2×5-Modulbuchse (Bluetooth-Belegung wie im Original), U.FL für S/PDIF, FFC-Buchse für X105 (SPI) | [#1](https://github.com/forge-dsp-community/hardware/issues/1) |

Geplante Einschubmodule: Bluetooth ([#2](https://github.com/forge-dsp-community/hardware/issues/2)),
CAN über MCP2515 ([firmware#73](https://github.com/forge-dsp-community/firmware/issues/73)).

**Stand:** Entwurf, nicht gefertigt, nicht am Gerät geprüft.

## Anschlüsse der Grundplatine

Belegung von X-EXT_AUDIO, X105 und EXT-SPDIF sowie die Versorgung stehen in
[#1](https://github.com/forge-dsp-community/hardware/issues/1).

## 3D-Modelle

Herstellermodelle (STEP) liegen nicht im Repo. Für die 3D-Ansicht der FFC-Buchse `FH12-16S-0.5SV` das Modell von
Hirose laden und als `ExtensionPCB/Straddle.pretty/FH12-16S-0.5SV.stp` ablegen. Die übrigen Modelle kommen aus der
KiCad-Bibliothek.
