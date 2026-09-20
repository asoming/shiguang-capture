# Third-party notices — 1.4.0b1 preview

The application source is MIT. Bundled dependencies retain their own licenses.
Full installed distribution metadata and available license files are collected in
`licenses/dependencies/` in each binary package. The inventory can contain build
utilities that are not linked into the executable; it must not be treated as a
minimal runtime SBOM.

- RapidOCR 1.4.4 and the bundled PP-OCRv4 detection/recognition and PP-OCRv2
  orientation models: Apache-2.0. Converted model source and exact SHA-256 are
  recorded in `src/shiguang_capture/ocr/models.json`. Upstreams:
  https://github.com/RapidAI/RapidOCR/tree/v1.4.4/python/rapidocr_onnxruntime/models
  and https://github.com/PaddlePaddle/PaddleOCR/tree/v2.7.0 . Their Apache license
  texts are included in `licenses/`. We have not modified the model files.
- ONNX Runtime 1.23.2: MIT, https://github.com/microsoft/onnxruntime/tree/v1.23.2 .
- PySide6 / Shiboken6 / Qt 6.11.2: LGPL-3.0 / GPL alternatives and third-party
  components. This application uses dynamically loaded Qt Core, Gui, Widgets,
  DBus, Network, Multimedia and platform support libraries under the LGPL option. Qt source:
  https://download.qt.io/archive/qt/6.11/6.11.2/submodules/ ; Qt for Python source:
  https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/ .
  License notices are in the dependency directories. Users may replace the
  dynamic libraries under `_internal/PySide6`, rebuild against compatible modified
  libraries, and reverse engineer the application for debugging such changes.
  There is no signature or integrity check preventing Qt library replacement.
  Build instructions and pinned dependencies are shipped in the source release.
- NumPy: BSD; its bundled numerical libraries have separate notices, including
  OpenBLAS/LAPACK BSD, GCC runtime exception and libquadmath LGPL. See NumPy's
  complete license in the package notices.
- OpenCV: Apache-2.0 plus third-party notices (including bundled codecs).
- openpyxl: MIT; Python: PSF; PyInstaller bootloader: GPL with the distribution
  exception; pynput: LGPL-3.0; python-xlib: LGPL-2.1; Pillow: HPND; other exact
  dependency versions and licenses are listed in the inventory.

No Argos translation model is included in the Linux package. The optional
translation feature is experimental and clearly identifies its dictionary fallback.

The OpenCV GUI wheel also bundles dynamically loaded Qt 5.15.19 libraries under
LGPL-3.0; see its LICENSE-3RD-PARTY.txt. Corresponding Qt sources are available at
https://download.qt.io/archive/qt/5.15/5.15.19/submodules/ . Optional Qt PDF and virtual-keyboard plugins/modules are excluded from the Linux
package. Qt license texts are provided in licenses/Qt/. DejaVu Sans is included
only as a deterministic self-test font; its Bitstream/DejaVu notices are included. System desktop libraries copied from Ubuntu are inventoried
with package versions and complete distro copyright notices under
`licenses/dependencies/system/`. Source packages are available from the Ubuntu
archive at https://archive.ubuntu.com/ubuntu/pool/ (use the source package named in
each copyright notice and matching version); dynamic libraries remain replaceable.
The Python runtime license is included as Python-LICENSE.txt.

## Added recognition and recording dependencies

- PaddlePaddle PP-OCRv5 mobile Chinese/multilingual and English recognition ONNX
  models: Apache-2.0. Exact official Hugging Face repository revisions, original
  files, sizes and SHA-256 values are in `ocr/models.json`. The ONNX files are
  unmodified; dictionaries are derived in order from each official inference YAML.
  Sources: https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx and
  https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx .
- PyAV 16.1.0: BSD-3-Clause, https://github.com/PyAV-Org/PyAV/tree/v16.1.0 .
- SoundCard 0.4.5: BSD-3-Clause, https://github.com/bastibe/SoundCard .
- PyObjC (macOS activity management and native input): MIT; see collected notices.
- CFFI: MIT; pycparser: BSD-3-Clause. See distribution metadata and collected notices.
- The Linux recording encoder links replaceable FFmpeg 8.0.1 shared libraries,
  built without GPL/nonfree or external codec libraries. Only MPEG-4 Part 2 and
  AAC encoders, their decoders, Matroska/MP4 containers and required conversion
  facilities are enabled. FFmpeg reports LGPL version 2.1 or later for this build.
  The original corresponding source archive, digest, configure arguments,
  COPYING.LGPLv2.1, LICENSE.md and rebuild script are supplied in
  `licenses/recording-runtime/`. Qt Multimedia additionally has its own FFmpeg
  runtime, with its notices in the PySide6 distribution. These are separate
  dynamic libraries. Users may replace compatible shared libraries and debug
  modified versions; no application check prevents library replacement.

Development tests may install PyAV's general-purpose wheel. It is not the encoder
runtime used in the Linux binary package. Test-wheel provenance is not a statement
that Windows/macOS binary distribution has completed release review.
