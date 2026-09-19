# 拾光 Capture

> 屏幕信息捕获与再利用工具 —— 把屏幕上的信息**直接变成可用内容**。

截图只是入口。框选的瞬间，本地 OCR 与结构化引擎已经启动：表格粘进 Excel，代码粘进编辑器，无需离开当前工作流。

[![CI](https://github.com/asoming/shiguang-capture/actions/workflows/ci.yml/badge.svg)](https://github.com/asoming/shiguang-capture/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)

## 能力总览

| 层 | 能力 | 状态 |
| --- | --- | --- |
| L1 捕获层 | 区域 / 窗口 / 全屏 / 固定尺寸截图、滚动长截图、贴图置顶、像素级取色 | V1.0 |
| L2 识别层 | 本地 OCR（默认）、云端增强（显式开启） | V1.0 |
| L3 结构化层 | 表格还原、代码保真、公式转 LaTeX、字段抽取 | V1.0 ~ 付费版 |
| L4 输出层 | 多格式复制、发送至目标应用、就地翻译 | V1.0 |
| 录屏 | 区域录制、音画分控、画中画、鼠标高亮 | V2.0（独立进程） |

**商业化红线**：本地能力永久免费 · 无广告 · 不强制登录 · 不默认上传 · 识别结果无水印。

## 快速开始

```bash
git clone https://github.com/asoming/shiguang-capture.git
cd shiguang-capture
pip install -e ".[all]"      # 完整安装（GUI + OCR）
python -m shiguang_capture   # 启动（托盘常驻）
```

| 热键 | 动作 |
| --- | --- |
| `F1` | 区域截图 |
| `Shift+F1` | 全屏截图 |
| `F2` | 取色器 |
| `F3` | 剪贴板图像贴图 |
| `Shift+F3` | 隐藏 / 恢复全部贴图 |

仅使用纯逻辑层（无 GUI 依赖，例如做二次开发或 CI）：

```bash
pip install -e .
```

## 产品站

`docs/` 为静态产品站（深色主题默认，可切浅色），已通过 GitHub Pages 发布：
**https://asoming.github.io/shiguang-capture/**

本地预览：

```bash
python -m http.server 8080 -d docs
```

## 架构

```
src/shiguang_capture/
├── geometry.py      选区几何（纯逻辑）
├── config.py        配置与持久化（纯逻辑）
├── naming.py        文件命名体系（纯逻辑，截图/录屏共享）
├── colors.py        色值换算（纯逻辑）
├── ocr/base.py      OCR 后端协议 + 隐私红线守卫（纯逻辑）
├── hotkeys.py       全局热键（pynput → Qt 信号桥）
├── capture/         屏幕抓取 + 全屏取景框
├── ui/              贴图窗口 / 取色器 / 系统托盘
└── app.py           装配层
```

**设计约束**：纯逻辑层与 Qt 完全解耦——全部单元测试无需显示环境即可运行；录屏模块不进入截图进程，保证热键唤起 ≤ 200ms。

## 开发与测试

```bash
pip install -e ".[dev]"
pytest                        # 纯逻辑层单测
python scripts/check_site.py  # 产品站静态检查
```

CI（GitHub Actions）在 Windows / macOS / Linux 三平台运行：单元测试矩阵（Py 3.11/3.12）、PySide6 离屏导入冒烟、站点静态检查。

## License

[MIT](LICENSE)
