# Linux 登录自启修复 · 1.5.0b2

2026-09-28。

原因：旧实现仅写 Windows Run 注册表；Linux 保存了 `launch_at_login=true`，却没有创建启动项。系统写入失败后设置窗口仍被关闭，成功通知覆盖了错误提示。

修复：

- Linux 按 XDG 规范，在用户配置目录 `autostart/shiguang-capture.desktop` 写入自己的启动项；支持开启、关闭、系统外部禁用识别及原子写入。
- 用户目录安装指向固定的 `current/ShiguangCapture`，版本升级不必重建路径；中文、空格、百分号及其他特殊字符按 Desktop Entry Exec 规则处理。
- 设置窗口显示实际自启状态；写入失败不保存配置、不关闭窗口；配置保存失败时恢复原自启状态。
- Windows 保留 Run 注册表方式，并支持 Run 键尚未创建的情况。尚未实现的系统禁用此开关，避免假成功。

验证：完整回归 303 passed、3 skipped（可选 Argos 模型）；新增启动项开关、外部禁用、写失败原文件保留、升级路径、Windows 注册表模拟及配置回滚回归。最后的百分号路径兼容修正另跑 6 项自启测试，全部通过。

Linux 原生验证：`desktop-file-validate` 校验成功；GIO DesktopAppInfo 实际启动一个位于中文、空格、百分号、引号、美元符号、反斜杠路径中的合成程序，并确认关闭自启后条目移除。本机用户启动项已创建并校验，目标为用户安装的 current 路径。没有执行注销或重启，不将此记录称为完整重启验收。

参考：[XDG Autostart 规范](https://specifications.freedesktop.org/autostart/latest/)及 [Desktop Entry Exec 转义规则](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)。自启发生在用户登录桌面后。
