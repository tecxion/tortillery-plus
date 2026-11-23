<div align="center">

<img src="docs/logo.png" alt="Tortillery+" width="220">

# Tortillery+

**Klipper, Mainsail y una pantalla táctil nueva para la Artillery Sidewinder X4 Pro y X4 Plus**

[![Versión](https://img.shields.io/github/v/tag/tecxion/tortillery-plus?label=versi%C3%B3n&color=e21e26)](https://github.com/tecxion/tortillery-plus/tags)
![Impresoras](https://img.shields.io/badge/Artillery-X4%20Pro%20%7C%20X4%20Plus-222)
![Klipper](https://img.shields.io/badge/Klipper-Moonraker%20%2B%20Mainsail-b12f36)
![Idioma](https://img.shields.io/badge/idioma-espa%C3%B1ol-f1bf00)

[Descargar](#-descarga) · [Instalar](#-instalación) · [Novedades](tortillery_plus/CAMBIOS.md) · [Guía completa](tortillery_plus/INSTALAR.md)

</div>

---

Grabas la imagen, enciendes la impresora y la pantalla te guía: **modelo, idioma, WiFi y nivelación**. Sin SSH, sin
editar archivos y conservando tu calibración en cada actualización.

## ✨ Qué trae

| | |
|---|---|
| 🖥️ **Pantalla nueva** | WiFi desde la pantalla, explorador por carpetas con USB, tiempo restante real, errores en español y calibración guiada. |
| 🎯 **Calibración guiada** | Input shaper con aceleración máxima, pressure advance, extrusor y torsión del eje X, todo desde la pantalla. |
| ⚡ **Corte de luz** | Guarda el estado cada 5 s y al volver ofrece reanudar la impresión. |
| 📷 **Cámara automática** | Cualquier webcam USB aparece en Mainsail sin configurar nada. |
| 🤖 **Vigilancia con IA** | Detecta espagueti, piezas despegadas y atascos; pausa y te avisa con foto (Anthropic, OpenAI, Google, NVIDIA u Ollama). |
| 💬 **Telegram** | Inicio, pausa con botones, fin con foto, vídeo del timelapse y aviso de mantenimiento. `/foto`, `/estado`, `/reanudar`. |
| 🔄 **Actualizaciones** | Desde Mainsail con un clic (solo versiones estables, nunca imprimiendo) y USB firmado para pantalla y placa. |
| 🛡️ **Más segura** | Apagado de calentadores en pausas largas, detección de termistor suelto, watchdog y copias automáticas de la config. |

Lista completa de cambios respecto a la Tortillery original: **[CAMBIOS.md](tortillery_plus/CAMBIOS.md)**.

## 📦 Descarga

La imagen de la eMMC y el firmware de la pantalla pesan demasiado para GitHub y están en Google Drive:

> **[⬇️ Descargar Tortillery+ (Google Drive)](ENLACE_DE_GOOGLE_DRIVE)**

## 🚀 Instalación

1. **Graba la imagen** en la eMMC de la impresora con [balenaEtcher](https://etcher.balena.io/) y deja que verifique.
2. **Enciende la impresora.** El primer arranque tarda unos minutos: graba la placa y la pantalla solo.
3. **En la pantalla**: elige X4 Pro o X4 Plus y el idioma.
4. **Bienvenida**: conecta el WiFi, nivela la cama y pulsa *Terminar*.

Mainsail queda en `http://<IP de la impresora>` (la IP aparece en la bienvenida y en *Ajustes*).

> [!TIP]
> ¿Ya tienes la Tortillery original? Puedes actualizar sin volver a grabar la eMMC: mira
> [INSTALAR.md](tortillery_plus/INSTALAR.md).

## 🔄 Actualizar

- **Desde Mainsail**: *Máquina › Actualizar › `tortillery`*. Actualiza configs, macros y KlipperLCD a la última versión
  publicada. Tu calibración (PID, Z-offset, mallas, input shaper) se conserva.
- **Por USB** (pantalla y firmware de la placa): copia la carpeta `USB` de la descarga a un pendrive FAT32 y arranca con él.

## 📁 Qué hay en este repositorio

```
tortillery_plus/   configs de Klipper, instalador, scripts, IA, Telegram y servicios
plr/               recuperación tras corte de luz y KlipperLCD (pantalla)
docs/              imágenes del README
```

## 🙏 Agradecimientos

- **[CiareCw455/Tortillery](https://github.com/CiareCw455/Tortillery)** — la Tortillery original, de donde salió la idea, y
  el proyecto `.HMI` de la pantalla Tortillery v0.5.2 sobre el que está hecha la de Tortillery+. ¡Gracias!
- **[joakimtoe/KlipperLCD](https://github.com/joakimtoe/KlipperLCD)** (Apache-2.0) — el programa que une la pantalla con
  Klipper. Los archivos modificados están en `plr/KlipperLCD/` con su licencia.
- **JeroMod** y **Tortillery 2.0** (@UrtziDV) — ideas incorporadas.
- [Klipper](https://github.com/Klipper3d/klipper), [Moonraker](https://github.com/Arksine/moonraker),
  [Mainsail](https://github.com/mainsail-crew/mainsail), Crowsnest, KAMP, Shake&Tune, Moonraker-Timelapse, Mobileraker y
  Armbian.

<div align="center">
<sub>Hecho en España 🇪🇸 para la comunidad de la Artillery X4</sub>
</div>
