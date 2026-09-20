#!/usr/bin/env bash
# User-local installation, with a launcher and desktop/menu shortcut.
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_root="${XDG_DATA_HOME:-$HOME/.local/share}/shiguang-capture"
app_version="1.3.0"
app_target="$app_root/$app_version"
if [ ! -x "$package_dir/ShiguangCapture" ]; then
  echo '请在解压后的 ShiguangCapture 目录中运行此脚本。' >&2; exit 1
fi
mkdir -p "$app_root" "$HOME/.local/bin" "${XDG_DATA_HOME:-$HOME/.local/share}/applications"
if [ -e "$app_target" ] && [ "$package_dir" != "$app_target" ]; then
  echo "版本目录已经存在：$app_target。请先移走旧目录，再重新安装。" >&2; exit 1
fi
if [ "$package_dir" != "$app_target" ]; then
  mkdir -p "$app_target"
  cp -a "$package_dir/." "$app_target/"
fi
ln -sfn "$app_version" "$app_root/current"
# A Python-free launcher; quote all paths, including homes with spaces.
printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$app_root/current/ShiguangCapture" > "$HOME/.local/bin/shiguang-capture"
chmod +x "$HOME/.local/bin/shiguang-capture"
desktop_file="${XDG_DATA_HOME:-$HOME/.local/share}/applications/shiguang-capture.desktop"
# Desktop Exec quoting also escapes percent field codes and literal special chars.
desktop_exec="${HOME//\\/\\\\}/.local/bin/shiguang-capture"
desktop_exec="${desktop_exec//\"/\\\"}"; desktop_exec="${desktop_exec//\$/\\\$}"; desktop_exec="${desktop_exec//\`/\\\`}"; desktop_exec="${desktop_exec//%/%%}"
cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=拾光 Capture
Comment=本地截图、标注与文字校对
Exec="$desktop_exec"
Icon=$app_root/current/icon.png
Terminal=false
Categories=Graphics;
StartupWMClass=shiguang-capture
EOF
desktop_dir="$(xdg-user-dir DESKTOP 2>/dev/null || printf '%s/Desktop' "$HOME")"
if [ -d "$desktop_dir" ]; then
  cp "$desktop_file" "$desktop_dir/拾光 Capture.desktop"
  chmod +x "$desktop_dir/拾光 Capture.desktop"
  if command -v gio >/dev/null; then gio set "$desktop_dir/拾光 Capture.desktop" metadata::trusted true 2>/dev/null || true; fi
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$(dirname "$desktop_file")" || true
printf '已安装 %s。可从桌面或应用菜单打开拾光 Capture。\n' "$app_version"
