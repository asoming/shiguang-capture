# 拾光 Capture 1.3.0

本地屏幕捕获与图片校对工具。截图、导入、标注、提取文字，再由你决定复制或保存。

**本次正式发行范围：Linux x86_64、X11 桌面。** 实测 Ubuntu 22.04，系统需 glibc 2.35 或更新版本、图形桌面和中文字体。Windows、macOS、Wayland 为实验支持，不提供这些平台的正式安装包。完整记录见 [验收报告](validation/RELEASE-1.3.0.md)。本版不宣称已经满足 PRD 的全部识别准确率目标。

## 安装

在 [正式发布页](https://github.com/asoming/shiguang-capture/releases/tag/v1.3.0) 下载 Linux 压缩包与 SHA256SUMS，校验并解压，在解压目录运行：

```bash
sha256sum -c SHA256SUMS --ignore-missing
# 解压下载的 tar.gz，然后进入 ShiguangCapture 目录
./install-linux.sh
```

桌面与应用菜单中会出现 **拾光 Capture**。也可直接运行目录内的 `ShiguangCapture`，无需 Python、联网下载模型或账号。首次运行无需联网。安装位置为 `~/.local/share/shiguang-capture/1.3.0`，启动器为 `~/.local/bin/shiguang-capture`。关闭工作台后驻留托盘；退出请用托盘菜单。

## 功能

- 区域／当前屏幕截图，区域操作使用同一份冻结快照，保留原生像素。
- PNG/JPEG 打开、拖入、粘贴；原图与结果并排校对，缩放、拖动和文字块定位。
- 箭头、矩形、文字、画笔、实色遮盖、撤销／重做；复制和保存均合并标注。
- 图像修改立即取消旧识别、清除旧文字，重新识别当前可见内容。
- 中英文 RapidOCR，独立进程、串行任务、取消／60 秒超时恢复，空闲五分钟释放模型。
- 文字／代码日志／简单表格模式。代码仅按可见位置恢复缩进，不补写、不执行。
- 有完整边框、无合并、最多 30 行 × 12 列的简单表格；保留空格位，单元格编辑与原图定位。
- 手动复制纯文本、代码块、Markdown 表格、HTML＋TSV；TXT/MD 和全单元格文本类型 XLSX 导出。
- 表格含公式风险前缀或换行时阻止 HTML＋TSV 复制，引导使用文本型 XLSX；编号、长数字和日期不会被 XLSX 导出转换。
- 桌面贴图、取色、配置冲突检查、原子保存、手动检查更新。随包模型启动前校验 SHA-256。

OCR 会有识别错误，置信度也不是正确率。代码符号、缩进、中文表格内容仍需人工校对。39 张合成图片的实测结果、原始输出和生成器全部公开；样本量不足以代替真实业务数据集。当前 PRD 的完整质量门槛尚未通过。

截图默认只复制，不自动落盘。OCR 不自动覆盖剪贴板；保存需选择位置。清空会话清除当前图像与识别结果，不清理系统剪贴板、桌面贴图和已保存文件。

| 快捷键 | 动作 |
| --- | --- |
| F1 | 区域截图：复制／标注／保存／贴图／文字识别 |
| Shift+F1 | 鼠标所在屏幕截图并复制 |
| Ctrl+F1 | 滚动长截图（实验） |
| F2 | 屏幕取色 |
| F3 | 剪贴板图片贴图 |
| F4 | 剪贴板图片识别 |
| Shift+F3 | 隐藏／恢复贴图 |

## 实验与未覆盖范围

滚动长截图仅适用于受限静态内容，匹配失败保留已有部分；上限 64 百万像素／单边 32,767。翻译为可选实验功能；正式包未附带 Argos 模型，界面明确显示词典替换降级，不能当作完整译文。复杂表格、合并单元格、窗口专用捕获、录屏和云端服务未实现。

单屏 X11 截图和快捷键已实机验证。多屏与混合 DPI 的坐标合成经过自动化验证，尚无多物理屏幕验收证据。跨屏采用最高 DPR 输出，低 DPI 部分会重采样。没有 Windows/macOS 签名、权限恢复及安装实机验收证据。

## 开发、验证和打包

Python 3.11/3.12。Linux 正式包采用 Python 3.12、`requirements-linux.lock` 的精确依赖：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-linux.lock
python -m pip install -e . --no-deps
QT_QPA_PLATFORM=offscreen SHIGUANG_NO_HOTKEYS=1 pytest
python -m shiguang_capture --self-test
python scripts/validate_quality.py
python scripts/validate_x11.py # 真实 X11 合成窗口，需要桌面会话
python scripts/check_site.py
# 打包需系统 libxcb-cursor0；可用 SHIGUANG_XCB_CURSOR 指定解压的库文件
python scripts/build_exe.py
```

`--self-test` 强制离屏，使用合成图片验证模型、子进程、结构化输出和剪贴板保护。`--check` 只检查基础环境，不能代替完整自测。生成质量样本需系统 Noto CJK 与 DejaVu 字体。其他平台开发可使用 `pip install -e '.[gui,ocr,dev]'`，构建成功不代表实机验收。

## 卸载和反馈

从托盘退出后，删除 `~/.local/share/shiguang-capture`、`~/.local/bin/shiguang-capture`、应用菜单的 `shiguang-capture.desktop` 和桌面的 `拾光 Capture.desktop` 即可卸载。不会删除用户另存的图片与文本。保留配置以便重装，配置位置见设置与 `config.py`。

通过 [GitHub Issues](https://github.com/asoming/shiguang-capture/issues) 报告问题，附版本、桌面环境、复现步骤和脱敏样图；不要上传含敏感内容的截图。

自有代码采用 [MIT](LICENSE)，模型与依赖见 [第三方声明](THIRD_PARTY_NOTICES.md) 和随包许可证。
