"""updater.py — 应用更新检查（纯逻辑 + 网络查询分离）。

说明：真正的原地自更新（下载替换二进制）依赖打包产物（exe/dmg），
在 V1.0 骨架阶段，更新流程为「检查 → 通知 → 引导到 Release 页下载」。
版本比较与响应解析为纯逻辑，可单元测试。
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

GITHUB_REPO = "asoming/shiguang-capture"
_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> tuple[int, int, int]:
    """解析 'v1.2.3' / '1.2.3' / '1.2.3-beta' -> (1, 2, 3)。非法输入抛 ValueError。"""
    m = _SEMVER_RE.match(text.strip())
    if not m:
        raise ValueError(f"非法版本号: {text!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_newer(latest: str, current: str) -> bool:
    """Compare release numbers and let a trial build upgrade to its stable release."""
    latest_number, current_number = parse_version(latest), parse_version(current)
    if latest_number != current_number:
        return latest_number > current_number
    stable = r'v?\d+\.\d+\.\d+(?:\+.*)?'
    return bool(re.fullmatch(stable, latest.strip()) and not re.fullmatch(stable, current.strip()))


@dataclass
class UpdateInfo:
    version: str
    url: str
    notes: str
    published_at: str


def parse_release_payload(payload: dict) -> UpdateInfo:
    """把 GitHub release JSON 解析为 UpdateInfo（键缺失时给安全默认）。"""
    return UpdateInfo(
        version=str(payload.get("tag_name", "0.0.0")),
        url=str(payload.get("html_url", RELEASES_PAGE)),
        notes=str(payload.get("body", ""))[:500],
        published_at=str(payload.get("published_at", "")),
    )


def fetch_latest_release(repo: str = GITHUB_REPO, timeout: float = 8.0) -> UpdateInfo | None:
    """查询最新 Release；仓库还没有任何 Release 或网络失败时返回 None（不抛异常）。"""
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(api, headers={
        "User-Agent": "shiguang-capture-updater",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return parse_release_payload(json.loads(resp.read().decode("utf-8")))
    except Exception as exc:
        raise ConnectionError("无法检查更新，请稍后重试。") from exc


def check_for_update(current_version: str, repo: str = GITHUB_REPO) -> UpdateInfo | None:
    """完整检查：有新版本返回 UpdateInfo，已是最新或查询失败返回 None。"""
    latest = fetch_latest_release(repo)
    if latest is None:
        return None
    try:
        return latest if is_newer(latest.version, current_version) else None
    except ValueError as exc:
        raise ValueError("发布版本信息无效，请从发布页查看。") from exc
