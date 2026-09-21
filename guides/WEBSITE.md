# 产品网站维护

主页：<https://asoming.github.io/shiguang-capture/> · [English](https://asoming.github.io/shiguang-capture/en/)

网站是无构建依赖的静态 HTML/CSS/JavaScript，GitHub Pages 从 `main` 分支的 `/docs` 发布。中英文页面独立可索引，不依赖浏览器脚本切换语言。没有分析脚本、外部字体、Cookie 或运行时 CDN 依赖。

## 文件

- `docs/index.html`、`docs/en/index.html`：中文、英文首页。
- `docs/assets/site.css`：共享响应式样式，支持键盘焦点与减少动态效果偏好。
- `docs/assets/site.js`：按需播放/停止悬浮球 GIF；离开可视区域或隐藏页面时停止。
- `docs/assets/social.png`：1280 × 640 分享封面，可用于 GitHub 仓库 Social preview；页面已设置 Open Graph 元数据。
- `docs/sitemap.xml`、`docs/robots.txt`：索引入口；旧功能、下载、定价页面保留跳转，避免旧链接失效。

## 本地预览与检查

```bash
python scripts/check_site.py
python -m http.server 8765 --directory docs
```

打开 `http://localhost:8765/`，检查中英文、桌面与手机宽度、下载链接、演示播放和停止、FAQ。自动检查覆盖本地资源、页面锚点、主要元数据和 README 文件链接。GitHub 的 **Website checks** 工作流运行相同检查。提交合并到 `main` 后，Pages 的 **pages build and deployment** 工作流完成即更新网站。

## 更新版本

更新两份 README 和两个首页中的版本号、下载文件名、支持架构与兼容性说明；先确认 Release 附件实际存在。不要凭构建成功宣称全部实机验收通过。当前资源为 v1.4.3，未提供 Intel Mac、DMG、DEB 或 MSI 包。

## 界面素材

`scripts/render_site_assets.py` 从当前应用的真实 Qt 控件生成录制台、识别工作台与静态悬浮球图，使用公开示例内容，禁止捕获私人桌面。安装 GUI 依赖后运行：

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.5 SHIGUANG_NO_HOTKEYS=1 python scripts/render_site_assets.py
```

媒体运行库环境要求同[开发参考](REFERENCE.md#开发验证和打包)。图片中的预览和文字/译文是演示输入，不是识别准确率或录制性能证据；页面明确标注示例。`orb-demo.gif` 来自 v1.4.3 真实 `RecordingOrb` 控件的逐帧渲染，仅展示浮球动效。品牌图标沿用项目原有资源。网站和 README 的信息组织参考 [DeskPlan](https://github.com/asoming/deskplan)，文案、样式与产品素材为拾光项目制作。
