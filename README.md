# Just Dance Greatest Hits (Xbox 360) - Song Replacement Toolkit & Methodology 💃🎮

[![Target Game: Just Dance Greatest Hits](https://img.shields.io/badge/Target%20Game-Just%20Dance%20Greatest%20Hits-orange.svg)]()
[![Platform: Xbox 360 (XEX)](https://img.shields.io/badge/Platform-Xbox%20360%20(XEX)-green.svg)]()
[![Tested on: Xenia & Xbox 360 RGH/JTAG](https://img.shields.io/badge/Tested%20on-Xenia%20%7C%20RGH%2FJTAG-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **[English](#english) | [Español](#español)**

---

<a name="english"></a>
## English

A universal toolkit, reverse-engineering guide, and methodology to replace in-game songs or covers in **Just Dance Greatest Hits for Xbox 360** with original studio audio, high-fidelity tracks, or uncensored audio.

### ⚖️ Disclaimer / Legal Notice

> **IMPORTANT LEGAL NOTICE & DISCLAIMER:**
> 
> * **Educational & Research Purposes Only:** This project, including its documentation, tools, and scripts, is provided strictly for educational, interoperability research, and personal game modding purposes.
> * **No Copyrighted Content Included:** This repository does **NOT** contain, host, or distribute any proprietary game binaries, copyrighted audio tracks, videos, or game assets. Users must independently supply their own legally acquired copy of the game and their own legally obtained audio files.
> * **No Affiliation:** This project is an independent community research effort and is in no way affiliated with, endorsed by, sponsored by, or associated with any game developer, publisher, console manufacturer, or music copyright owner.
> * **Limitation of Liability:** The authors and contributors assume no responsibility or liability whatsoever for any misuse of this software, copyright infringement, data loss, console bans, or damages of any kind resulting from the use or inability to use this toolkit. Users are solely responsible for ensuring compliance with applicable local laws and copyright regulations.

---

### Features
- 🔄 **Universal Song Replacement:** Works dynamically on any song detected in the game folder.
- 🎯 **Automatic Beat Alignment:** Automatically detects lead-in silence differences using onset cross-correlation so the audio synchronizes with the dancers, choreographies, and pictograms.
- 🔊 **Console Loudness Normalization:** Automatically adjusts modern loud audio masters to the **-24.3 LUFS** Xbox 360 standard, preventing distortion and protecting in-game sound effects.
- 🎬 **Lossless Video Quality:** Copies the original video stream directly (`-c:v copy`), preserving 100% of the visual fidelity.
- 📦 **Full Track Coverage:** Patches the main song video (`<Song>.wmv`), Mashup/Medley clips (`<Song>_A.wmv`, `<Song>_B.wmv`), and the menu selection preview (`<Song>_Preview.bik`).
- 🛡️ **Automatic Backups:** Generates safety `.bak` files before touching any game asset.

---

### ⚠️ Platform & Format Requirement
* **Target Game:** *Just Dance Greatest Hits* (known as *Just Dance Best Of* in PAL regions).
* **Target Console:** Microsoft Xbox 360 (tested on real RGH/JTAG hardware and Xenia emulator).
* **Format:** **Extracted XEX format** (folder containing `default.xex` and the `videos/` subfolder).

> **Why is GOD format NOT supported directly?**
> In **GOD (Games on Demand)** format, game files are packaged inside encrypted multi-part container blocks that cannot be edited file-by-file.
> To modify the game, convert your GOD container to ISO using tools such as **GOD2ISO**, and then extract the ISO into an XEX folder structure using **Xbox Image Browser** or **Horizon**.

---

### 🔬 Technical Deep Dive: Engine Architecture

When modding Just Dance on Xbox 360, many assume song audio is stored inside the `.forge` archives found in the root folder:

```
Just Dance Greatest Hits/
├── Data360_<SongName>.forge      <-- Contains NO audio!
├── videos/
│   ├── <SongName>.wmv            <-- THE ACTUAL AUDIO & VIDEO
│   ├── <SongName>_A.wmv          <-- Mashup Clip A audio & video
│   ├── <SongName>_B.wmv          <-- Mashup Clip B audio & video
│   └── <SongName>_Preview.bik    <-- Carousel menu preview clip
```

#### 1. What `.forge` actually contains
Deconstructing the proprietary `.forge` archives reveals:
- 3D stage geometry and environment lighting.
- Pictogram sprite sheets and UI textures.
- Kinect motion tracking gesture definitions (`NatalMoves_*`).
- Timing sequence events.

**There is zero song audio inside `.forge` files.** The choreography and Kinect detection run on an internal millisecond clock that assumes the song audio is streaming from the video player.

#### 2. The Video Container (`videos/*.wmv`)
The game engine streams both the dancers and the music simultaneously from Windows Media Video (`.wmv`) files in the Microsoft ASF container:
- **Video:** `WMV3` or `VC-1` at 1280x1440, 25 fps.
- **Audio:** WMA Standard (`wmav2`) or WMA Pro, 48,000 Hz, Stereo, 192 kbps.

By remuxing the WMV file with your replacement audio track (preserving the exact beat alignment), **the Kinect scoring, pictograms, and choreography remain 100% synchronized.**

---

### Dynamic Song Detection
The script automatically reads the `videos/` folder of your legally extracted game copy and displays an interactive menu of all available songs, so you do not need to look up or type internal codenames manually.

---

### Prerequisites
- [FFmpeg](https://ffmpeg.org/download.html) in your system `PATH`.
- [Python 3.8+](https://www.python.org/downloads/)
- *(Optional)* [RAD Video Tools](https://www.radgametools.com/bnkdown.htm) for menu preview (`.bik`) patching.
- *(Optional)* `pip install librosa scipy numpy` for automatic offset detection.

---

### Quick Usage

#### 1. Interactive Mode (Easiest)
Run `song_fix.py` without arguments (or double-click `song_fix.bat` on Windows):
```bash
python song_fix.py
```
The script will prompt you for your game path, display a list of all detected songs in your copy, let you pick which one to replace, ask for your replacement audio file, and perform all steps automatically.

#### 2. Command Line Mode
```bash
python song_fix.py -g "C:\Games\Just Dance Greatest Hits" -s "SongCodename" -a "C:\Music\MySong.flac"
```

#### 3. Listing Songs
```bash
python song_fix.py -g "C:\Games\Just Dance Greatest Hits" --list
```

---

<a name="español"></a>
## Español

Un kit de herramientas universal, guía de ingeniería inversa y metodología para reemplazar **canciones o covers del juego** en **Just Dance Greatest Hits para Xbox 360** con audios originales de estudio, másters de alta fidelidad o versiones sin censura.

### ⚖️ Descargo de Responsabilidad / Aviso Legal

> **AVISO LEGAL Y DESCARGO DE RESPONSABILIDAD IMPORTANTE:**
> 
> * **Fines Educativos y de Investigación Únicamente:** Este proyecto, incluyendo su documentación, scripts y herramientas, se proporciona estrictamente con fines educativos, de investigación de interoperabilidad de formatos y de modificación personal de videojuegos.
> * **Sin Contenido Protegido por Derechos de Autor:** Este repositorio **NO** contiene, aloja ni distribuye archivos binarios propietarios del juego, música protegida por derechos de autor, videos ni recursos del juego. Cada usuario debe suministrar de forma independiente su propia copia legítimamente adquirida del juego y sus propios archivos de audio legales.
> * **Sin Afiliación:** Este es un proyecto de investigación independiente y no está afiliado, respaldado, patrocinado ni asociado con ningún desarrollador, editor de videojuegos, fabricante de consolas ni titular de derechos de autor de obras musicales.
> * **Limitación de Responsabilidad:** Los autores y colaboradores no asumen responsabilidad alguna por el mal uso que se le dé a este software, infracciones a la propiedad intelectual, pérdida de datos, bloqueos de consola o cualquier daño directo o indirecto derivado del uso o imposibilidad de uso de estas herramientas. El usuario es el único responsable de asegurar el cumplimiento de las leyes y normativas de derechos de autor aplicables en su territorio.

---

### Características
- 🔄 **Reemplazo Universal:** Funciona de forma dinámica con cualquier canción detectada en la carpeta del juego.
- 🎯 **Alineación de Ritmo Automática:** Detecta diferencias de silencios de entrada mediante correlación cruzada de envolventes (FFT) para mantener sincronía total con la coreografía y los pictogramas.
- 🔊 **Normalización de Volumen para Consola:** Ajusta másters de streaming modernos al estándar de **-24.3 LUFS** de Xbox 360, evitando saturación y protegiendo los efectos de sonido del juego.
- 🎬 **Calidad de Video Intacta:** Copia el flujo de video original sin recomprimir (`-c:v copy`), preservando el 100% de la calidad visual.
- 📦 **Cobertura Integral:** Parchea el video principal (`<Cancion>.wmv`), los clips de Mashup (`<Cancion>_A.wmv`, `<Cancion>_B.wmv`) y la vista previa del menú (`<Cancion>_Preview.bik`).
- 🛡️ **Respaldos Automáticos:** Crea respaldos de seguridad `.bak` antes de modificar cualquier archivo.

---

### ⚠️ Requisitos de Plataforma y Formato
* **Juego:** *Just Dance Greatest Hits* (conocido como *Just Dance Best Of* en regiones PAL/Europa).
* **Plataforma:** Microsoft Xbox 360 (probado en consolas con RGH/JTAG y en emulador Xenia).
* **Formato:** **Formato XEX extraído** (carpeta que contiene `default.xex` y la subcarpeta `videos/`).

> **¿Por qué NO se admite el formato GOD directamente?**
> En formato **GOD (Games on Demand)**, los archivos del juego están empaquetados en bloques cifrados que no pueden modificarse individualmente.
> Para editar el juego, convierte tu contenedor GOD a ISO con herramientas como **GOD2ISO**, y luego extrae la ISO en una carpeta XEX usando **Xbox Image Browser** o **Horizon**.

---

### 🔬 Análisis Técnico: Arquitectura del Motor

Al modificar Just Dance en Xbox 360, muchos asumen que la música está dentro de los archivos `.forge` de la carpeta raíz:

```
Just Dance Greatest Hits/
├── Data360_<NombreCancion>.forge      <-- ¡NO CONTIENE AUDIO!
├── videos/
│   ├── <NombreCancion>.wmv            <-- AQUÍ ESTÁ EL AUDIO Y VIDEO REAL
│   ├── <NombreCancion>.wmv_A          <-- Audio y video Mashup Clip A
│   ├── <NombreCancion>.wmv_B          <-- Audio y video Mashup Clip B
│   └── <NombreCancion>_Preview.bik    <-- Vista previa de menú
```

#### 1. Qué contiene realmente un archivo `.forge`
El análisis de los archivos `.forge` revela:
- Geometría 3D y luces del escenario.
- Texturas de pictogramas e interfaz.
- Definiciones de seguimiento de movimiento del Kinect (`NatalMoves_*`).
- Eventos de tiempo y puntuación.

**No hay audio de canciones dentro de los archivos `.forge`.** El sistema de detección del Kinect y los pictogramas se rigen por un contador interno que asume que el audio proviene de la reproducción del video de fondo.

#### 2. El Contenedor de Video (`videos/*.wmv`)
El motor reproduce a los bailarines y la música simultáneamente desde archivos Windows Media Video (`.wmv` / ASF):
- **Video:** `WMV3` o `VC-1` en 1280x1440 a 25 fps.
- **Audio:** WMA Standard (`wmav2`) o WMA Pro, 48,000 Hz, Estéreo, 192 kbps.

Al remultiplexar el archivo WMV con tu canción de reemplazo (respetando la alineación del compás), **el sistema de puntuación, los pictogramas y el Kinect se mantienen 100% sincronizados.**

---

### Detección Dinámica de Canciones
El script inspecciona automáticamente la carpeta `videos/` de tu copia legítimamente extraída y muestra un menú interactivo con todas las canciones disponibles en tu versión, por lo que no requieres buscar ni escribir nombres de código manualmente.

---

### Modo de Uso

#### 1. Modo Interactivo (Recomendado)
Ejecuta el script sin parámetros (o haz doble clic sobre `song_fix.bat` en Windows):
```bash
python song_fix.py
```
El script te pedirá la ruta de tu juego, listará todas las canciones disponibles en tu copia, te permitirá elegir cuál reemplazar y te solicitará tu archivo de audio personal.

#### 2. Modo por Línea de Comandos
```bash
python song_fix.py -g "C:\Juegos\Just Dance Greatest Hits" -s "NombreDeCodigo" -a "C:\Musica\MiCancion.flac"
```

#### 3. Ver lista de canciones
```bash
python song_fix.py -g "C:\Juegos\Just Dance Greatest Hits" --list
```

---

## License / Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

*Desarrollado para la comunidad de modding y preservación de videojuegos.*
