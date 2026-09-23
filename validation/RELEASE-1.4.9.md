# 拾光 Capture v1.4.9

- 长截图预览从小图开始，随手动滚动逐渐变长；保持顶部位置不动，达到屏幕边缘后缩放完整长图。
- 修复动态预览的捕获排除范围，避免预览窗口进入截图或触发无效采集。
- Windows 提供双击安装的 `Windows-x86_64-Setup.exe`，包含桌面、开始菜单快捷方式和卸载入口。
- Debian/Ubuntu 提供 `Linux-amd64.deb`，支持图形安装器或 `sudo apt install ./ShiguangCapture-v1.4.9-Linux-amd64.deb`。便携 ZIP/TAR.GZ 包继续提供。

安装、应用启动、重复安装、卸载及保留用户设置均有自动化检查。实际构建和三平台验收记录见 `build-manifest.json` 与 `validation-evidence.zip`。

Windows 安装程序尚未签名，macOS 包使用临时签名、未公证。Linux 面向 X11，DEB 基于 Ubuntu 22.04 构建（glibc 2.35+）。macOS 系统声音、多物理屏幕和部分权限恢复仍待实机验证；完整功能边界见仓库的验收文档。
