# 拾光 Capture v1.4.8

QQ 风格手动长截图与 macOS 录屏修复。

- 长截图由你自行滚动，实时保留截图框与外侧蒙板，显示累计尺寸和缩略预览；工具条支持编辑、保存、取消、完成复制。
- 截图使用紧凑白色工具条，提供椭圆、颜色与粗细选择，文字可再次编辑。
- 保留白色录制台、蓝色可拖动悬浮球、三秒倒计时、连续实时预览与录屏文件管理；截图、录屏快捷键可在设置中自定义。
- 修复 macOS 定时唤醒延迟导致的录屏帧数不足；原有验收标准未降低。

## 下载与安装

- Linux X11 x86_64：解压后运行 `./install-linux.sh`，使用桌面或应用菜单中的“拾光 Capture”。
- Windows x86_64：解压后运行 `ShiguangCapture.exe`。
- macOS Apple Silicon：解压后将 `ShiguangCapture.app` 移至应用程序目录。

OCR 与中英离线翻译模型随包提供。下载后可使用 `SHA256SUMS` 校验。

## 验证与使用范围

三平台 CI、原生区域／窗口录屏及暂停恢复检查通过；正式包包含 OCR、翻译、编码自测，Windows/macOS 包另测实时预览和原生录制。对应提交和运行链接见 `build-manifest.json`，详细证据见 `validation-evidence.zip`。

Windows 包未签名，macOS 使用临时签名、未公证。Linux 面向 X11。macOS 系统声音、多物理屏幕及部分权限恢复仍待实机验证；复杂表格、合并单元格和云端服务未实现。长截图适用于有足够重叠的静态内容，匹配失败时保留已有结果。完整状态见仓库 `validation/PRD-ACCEPTANCE.md`。
