import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import yaml

DEFAULT_CONFIG = {
    "download_folder": "~/Downloads/MeroDownload",
    "max_concurrent": 2,
    "default_format": "mp4",
    "default_quality": "1080p",
    "bandwidth_limit": 0,
    "proxy": "",
    "cookie_file": "",
    "notifications": True,
    "theme": "light",
    "embed_subtitles": False,
}


def ensure_folder(path: str) -> str:
    expanded = os.path.expanduser(path)
    os.makedirs(expanded, exist_ok=True)
    return expanded


def load_config(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return DEFAULT_CONFIG.copy()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(data)
    return cfg


def save_config(path: str, config: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|]", "", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean or f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def platform_from_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    if "youtube" in host or "youtu.be" in host:
        return "YouTube"
    if "instagram" in host:
        return "Instagram"
    if "twitter" in host or "x.com" in host:
        return "Twitter"
    if "facebook" in host or "fb.watch" in host:
        return "Facebook"
    if "tiktok" in host:
        return "TikTok"
    if "reddit" in host:
        return "Reddit"
    return "Other"


def is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def format_bytes(size: int | float | None) -> str:
    if size in (None, 0):
        return "--"
    size = float(size)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def format_speed(speed: int | float | None) -> str:
    if not speed:
        return "--"
    return f"{format_bytes(speed)}/s"


def format_eta(seconds: int | None) -> str:
    if seconds is None:
        return "--"
    if seconds < 60:
        return f"~{seconds}s left"
    mins, sec = divmod(seconds, 60)
    if mins < 60:
        return f"~{mins}m {sec}s left"
    hours, mins = divmod(mins, 60)
    return f"~{hours}h {mins}m left"


def truncated(text: str, length: int = 56) -> str:
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."
