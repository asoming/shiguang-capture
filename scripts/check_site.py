"""check_site.py — 产品站静态检查（CI 用）。

校验：
1. 四个页面可被 html.parser 完整解析
2. 页内引用的本地资源（assets/...）真实存在
3. 四个页面均引用了共享样式与共享脚本
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "docs"
PAGES = ["index.html", "features.html", "pricing.html", "download.html"]


class RefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("src", "href") and v and not v.startswith(("http", "#", "mailto:")):
                self.refs.append(v.split("#")[0])


def main() -> int:
    errors: list[str] = []
    for page in PAGES:
        path = SITE / page
        if not path.is_file():
            errors.append(f"缺少页面: {page}")
            continue
        html = path.read_text(encoding="utf-8")
        parser = RefCollector()
        parser.feed(html)
        if "assets/site.css" not in parser.refs:
            errors.append(f"{page}: 未引用共享样式 assets/site.css")
        if "assets/site.js" not in parser.refs:
            errors.append(f"{page}: 未引用共享脚本 assets/site.js")
        for ref in parser.refs:
            if not (SITE / ref).exists():
                errors.append(f"{page}: 引用不存在 -> {ref}")
    if errors:
        for e in errors:
            print(f"FAIL {e}")
        return 1
    print(f"site-check OK ({len(PAGES)} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
