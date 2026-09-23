# 拾光 Capture · 完整使用与开发参考

[返回产品介绍](../README.md) · [产品网站](https://asoming.github.io/shiguang-capture/)

本地屏幕捕获与图片校对工具。截图、导入、标注、提取文字，再由你决定复制或保存。

1.4.8 提供 Linux X11 x86_64、Windows x86_64 与 macOS arm64 安装包。
1.4.8 增加 QQ 风格手动长截图并修复 macOS 录屏定时；保留白色录制台与蓝色动态悬浮球。屏幕、区域和窗口支持连续实时预览，无需手动刷新。隐藏面板或切到文件页时释放预览资源。

本版重新整理截图、录屏和识别交互：截图就地标注，录屏使用三秒全屏倒计时与贴边浮球，识别窗口只保留图片、结果和翻译。中英离线模型随包提供，无需上传图片或文字。

发布范围为下述已实现功能；不宣称 PRD 全量验收通过。[逐项验收记录](../validation/PRD-ACCEPTANCE.md)保留通过、失败及未验证项。macOS 原生区域录制三次重复与窗口录制均已通过帧数、内容及暂停恢复检查。

## 安装已发布稳定版

在 [正式发布页](https://github.com/asoming/shiguang-capture/releases/tag/v1.4.8) 下载 Linux 压缩包与 SHA256SUMS，校验并解压，在解压目录运行：

```bash
sha256sum -c SHA256SUMS --ignore-missing
# 解压下载的 tar.gz，然后进入 ShiguangCapture 目录
./install-linux.sh
```

桌面与应用菜单中会出现 **拾光 Capture**。也可直接运行目录内的 `ShiguangCapture`，无需 Python、联网下载模型或账号。首次运行无需联网。安装位置为 `~/.local/share/shiguang-capture/1.4.8`，启动器为 `~/.local/bin/shiguang-capture`。关闭主窗口后驻留托盘；退出请用托盘菜单。

Windows：解压后运行 `ShiguangCapture.exe`，可运行 `install-windows.ps1` 创建桌面与开始菜单快捷方式。macOS：解压 `.app` 后移到应用程序目录；当前采用 ad-hoc 签名，未进行 Apple 公证。

## 功能

- 区域／当前屏幕截图，区域操作使用同一份冻结快照，保留原生像素。
- PNG/JPEG 打开、拖入、粘贴；原图与结果并排校对，缩放、拖动和文字块定位。
- 拖选后直接用浮动工具条标注、复制、保存、贴图或识别；Enter/Ctrl+C 复制、Ctrl+S 保存、Ctrl+Z/Ctrl+Y 撤销重做，右键重选、Esc 退出。
- 箭头、矩形、文字、画笔、实色遮盖；已确认的文字可再次点击修改；连续 20 步撤销重做有自动测试，导出合并标注。
- 独立录屏面板：全屏、区域、窗口，全屏 3 秒动效倒计时，可拖动浮球控制，贴边蓝色半圆收起，暂停/继续、停止保存 MP4，异常恢复；无声为默认，可明确选择麦克风、系统音源或混音。音源可用性依系统和设备而定。
- 图像修改立即取消旧识别、清除旧文字，重新识别当前可见内容。
- 中英文 RapidOCR，独立进程、串行任务、取消／60 秒超时恢复，空闲五分钟释放模型。
- 文字／代码日志／简单表格模式。代码仅按可见位置恢复缩进，不补写、不执行。
- 有完整边框、无合并、最多 30 行 × 12 列的简单表格；保留空格位，单元格编辑与原图定位。
- 手动复制纯文本、代码块、Markdown 表格、HTML＋TSV；TXT/MD 和全单元格文本类型 XLSX 导出。
- 表格含公式风险前缀或换行时阻止 HTML＋TSV 复制，引导使用文本型 XLSX；编号、长数字和日期不会被 XLSX 导出转换。
- 贴图右键原图识别、鼠标穿透及快捷键/托盘找回；取色像素放大镜、会话颜色历史、HEX/RGB/HSL/HSV/RGBA。
- 选中文字后右键进行规则清理：默认关闭、差异预览、仅修改选区、可撤销。
- 配置冲突检查、原子保存、手动检查更新。随包模型启动前校验 SHA-256。
- 每种模式分别记忆输出格式；JSON 导出保留模式、版本和字符串单元格。

OCR 会有识别错误，置信度也不是正确率。代码符号、缩进、中文表格内容仍需人工校对。39 张合成图片的实测结果、原始输出和生成器全部公开；样本量不足以代替真实业务数据集。当前 PRD 的完整质量门槛尚未通过。

截图默认只复制，不自动落盘。OCR 不自动覆盖剪贴板；保存需选择位置。清空会话清除当前图像与识别结果，不清理系统剪贴板、桌面贴图和已保存文件。

在设置的「快捷键」页点击输入框后，直接按下组合键，再点击「保存」。Backspace 清除该快捷键，Esc 取消本次录入；可恢复默认。以下为默认值：

| 快捷键 | 动作 |
| --- | --- |
| F1 | 区域截图：复制／标注／保存／贴图／文字识别 |
| Shift+F1 | 鼠标所在屏幕截图并复制 |
| Ctrl+F1 | 滚动长截图（实验） |
| F2 | 屏幕取色 |
| F3 | 剪贴板图片贴图 |
| F4 | 剪贴板图片识别 |
| Shift+F3 | 隐藏／恢复贴图 |
| Ctrl+Shift+F3 | 找回全部贴图并退出鼠标穿透 |
| F6 | 打开录屏／暂停／继续 |
| F7 | 停止录屏并保存 |

## 实验与未覆盖范围

滚动长截图仅适用于受限静态内容，匹配失败保留已有部分；上限 64 百万像素／单边 32,767。中英 OPUS-MT 离线翻译随包提供；识别后点击翻译可上下对照，右键切换左右对照。翻译使用校对后的文字；导出、格式和清理选区放在结果右键菜单中。复杂表格、合并单元格、窗口截图和云端服务未实现。窗口录屏已提供；同名窗口无法可靠区分时会要求改用区域录屏，窗口尺寸变化会停止并保留恢复文件。macOS 系统声音尚未通过验收；具体记录见验收文档。

单屏 X11 截图和快捷键已实机验证。多屏与混合 DPI 的坐标合成经过自动化验证，尚无多物理屏幕验收证据。跨屏采用最高 DPR 输出，低 DPI 部分会重采样。没有 Windows/macOS 签名、权限恢复及安装实机验收证据。

## 开发、验证和打包

Python 3.11/3.12。Linux 正式包采用 Python 3.12、`requirements-linux.lock` 的精确依赖：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-linux.lock
python -m pip install -e . --no-deps
# 安装 C 编译器、make、pkg-config、NASM 后，构建最小动态录屏库
python scripts/build_media_runtime.py
python -m pip install --no-deps build/media-runtime/wheels/*.whl
export LD_LIBRARY_PATH="$PWD/build/media-runtime/runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
QT_QPA_PLATFORM=offscreen SHIGUANG_NO_HOTKEYS=1 pytest
python -m shiguang_capture --self-test
python -m shiguang_capture --recording-self-test
python scripts/validate_quality.py
python scripts/validate_x11.py # 真实 X11 合成窗口，需要桌面会话
python scripts/check_site.py
# 打包需系统 libxcb-cursor0；可用 SHIGUANG_XCB_CURSOR 指定解压的库文件
python scripts/build_translation_models.py
python -m shiguang_capture --translation-self-test
python scripts/build_exe.py
```

`--self-test` 强制离屏，使用合成图片验证模型、子进程、结构化输出和剪贴板保护。`--check` 只检查基础环境，不能代替完整自测。生成质量样本需系统 Noto CJK 与 DejaVu 字体。其他平台开发可使用 `pip install -e '.[gui,ocr,record,offline,dev]'`，构建成功不代表实机验收。

## 卸载和反馈

从托盘退出后，删除 `~/.local/share/shiguang-capture`、`~/.local/bin/shiguang-capture`、应用菜单的 `shiguang-capture.desktop` 和桌面的 `拾光 Capture.desktop` 即可卸载。不会删除用户另存的图片与文本。保留配置以便重装，配置位置见设置与 `config.py`。

通过 [GitHub Issues](https://github.com/asoming/shiguang-capture/issues) 报告问题，附版本、桌面环境、复现步骤和脱敏样图；不要上传含敏感内容的截图。

自有代码采用 [MIT](../LICENSE)，模型与依赖见 [第三方声明](../THIRD_PARTY_NOTICES.md) 和随包许可证。

录屏库按精简配置从 FFmpeg 8.0.1 源码构建，动态链接，可替换；对应源码、构建参数与许可证随 Linux 预览包附带。录制只在显式选择的目录产生视频和恢复文件，恢复后不删除原恢复文件。
