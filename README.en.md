<p align="center"><img src="docs/assets/icon-128.png" width="80" alt="Shiguang Capture"></p>
<h1 align="center">Shiguang Capture · 拾光</h1>
<p align="center"><strong>Capture the moment. Keep going.</strong></p>
<p align="center"><a href="README.md">简体中文</a> · <a href="https://asoming.github.io/shiguang-capture/en/">Website & demo</a> · <a href="https://github.com/asoming/shiguang-capture/releases/latest">Latest release</a> · <a href="https://github.com/asoming/shiguang-capture/issues">Feedback</a></p>
<p align="center">
<a href="https://github.com/asoming/shiguang-capture/releases/latest"><img src="https://img.shields.io/github/v/release/asoming/shiguang-capture?color=246deb" alt="Latest release"></a>
<a href="https://github.com/asoming/shiguang-capture/actions/workflows/site.yml"><img src="https://github.com/asoming/shiguang-capture/actions/workflows/site.yml/badge.svg" alt="Website checks"></a>
<a href="#download"><img src="https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-586c86" alt="Windows, macOS, Linux"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-246deb" alt="MIT license"></a>
</p>

A free, open-source desktop tool for **screenshots, in-place annotations, recording, offline OCR and Chinese–English translation**. Turn what is on your screen into something you can keep editing.

No account required. OCR and translation models are bundled; images and text stay on your computer. The application interface is currently primarily in Chinese.

## Download

| Platform | v1.4.3 download | Get started |
| --- | --- | --- |
| Windows x86_64 | [ZIP archive](https://github.com/asoming/shiguang-capture/releases/download/v1.4.3/ShiguangCapture-v1.4.3-Windows-x86_64.zip) | Extract and run `ShiguangCapture.exe` |
| macOS Apple Silicon | [TAR.GZ archive](https://github.com/asoming/shiguang-capture/releases/download/v1.4.3/ShiguangCapture-v1.4.3-macOS-arm64.tar.gz) | Extract and move the `.app` into Applications |
| Linux X11 x86_64 | [TAR.GZ archive](https://github.com/asoming/shiguang-capture/releases/download/v1.4.3/ShiguangCapture-v1.4.3-Linux-x86_64.tar.gz) | Extract and run `./install-linux.sh` |

[All releases and notes](https://github.com/asoming/shiguang-capture/releases/latest) · [SHA256SUMS](https://github.com/asoming/shiguang-capture/releases/download/v1.4.3/SHA256SUMS)

Windows packages are unsigned; macOS is ad-hoc signed and not notarized. macOS recording frame rates may be low, and system audio has not passed acceptance. Physical multi-monitor and some permission recovery scenarios still need device testing. See the [acceptance record](validation/PRD-ACCEPTANCE.md) for scope and evidence.

![Actual white recording panel with settings and a sample presentation preview](docs/assets/recording.png)
<p align="center"><sub>Current application widgets rendered with a sample presentation.</sub></p>

<details>
<summary><strong>See the blue floating control in motion</strong></summary>
<br>
<p align="center"><img src="docs/assets/orb-demo.gif" width="436" alt="Animated blue recording control and expanded buttons"></p>

Click to expand resume, pause and stop controls. Drag to an edge to dock as a blue semicircle. The [website demo](https://asoming.github.io/shiguang-capture/en/#demo) has explicit play/stop controls.
</details>

## Keep working from your screen

| Task | How Shiguang helps |
| --- | --- |
| Capture and explain | Annotate the selection with arrows, rectangles, editable text, pen marks or solid covers; undo and redo |
| Record a process | Capture a screen, region or window, with a three-second countdown, continuous live preview and floating controls |
| Find a recording | View file sizes and dates; play, delete or reveal a recording in its folder |
| Extract content | Local Chinese/English OCR for text, visible code and simple tables; review source and result side by side |
| Read across languages | Offline Chinese–English translation with original and translated text in a comparison pane |
| Use your own shortcuts | Customize capture, color picker, pin and recording shortcuts by pressing a key combination in settings |

![Actual OCR workbench with sample image, source text and translation](docs/assets/recognition.png)
<p align="center"><sub>Sample text and translation illustrate the actual UI. Review OCR and translation results before using them.</sub></p>

Annotations stay in the capture selection. Screenshots copy by default; saving is explicit. OCR does not automatically replace clipboard contents. Simple tables export to Markdown, HTML/TSV or text-cell XLSX. Complex merged tables are unsupported; scrolling capture is experimental.

## Quick start

1. Download and extract the package for your system. Start the application and customize shortcuts in settings.
2. Press **F1** to select a region. Annotate, copy, save, pin or recognize it from the selection toolbar.
3. Press **F6** to open the recorder. During recording, **F6** pauses/resumes and **F7** stops and saves.

Closing a window keeps the app in the tray. Use the tray menu to quit completely. Linux's installer and Windows's `install-windows.ps1` can create desktop shortcuts. Linux installs under `~/.local/share/shiguang-capture/1.4.3`, with a launcher at `~/.local/bin/shiguang-capture`.

For integrity verification, download `SHA256SUMS` alongside your archive; Linux/macOS can use `sha256sum -c SHA256SUMS --ignore-missing` (macOS: `shasum -a 256 -c SHA256SUMS`, checking the entry for the downloaded archive). Windows PowerShell: `Get-FileHash .\ShiguangCapture-v1.4.3-Windows-x86_64.zip -Algorithm SHA256`, then compare with the matching checksum entry.

[Full reference, in Chinese](guides/REFERENCE.md) · [Release validation](validation/RELEASE-1.4.3.md)

## Contribute

Report bugs or suggest improvements through [Issues](https://github.com/asoming/shiguang-capture/issues), including the version, OS, reproduction steps and a sanitized sample.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [Website maintenance](guides/WEBSITE.md)

## Development

Python 3.11 / 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[gui,ocr,record,offline,dev]'
python -m shiguang_capture
```

Recording also needs the media runtime. For locked Linux dependencies, the minimal FFmpeg build, models and validation commands, see the [build reference](guides/REFERENCE.md#开发验证和打包). A successful build does not establish acceptance for every physical desktop scenario.

## License

Original code is [MIT licensed](LICENSE). Models, FFmpeg and dependencies have their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md) and the notices bundled with each package.
