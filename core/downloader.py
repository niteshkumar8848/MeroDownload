from __future__ import annotations

import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from yt_dlp import DownloadError, YoutubeDL
from yt_dlp.version import __version__ as ytdlp_version

from core.database import DatabaseManager
from core.utils import (
    ensure_folder,
    format_bytes,
    format_eta,
    format_speed,
    platform_from_url,
    sanitize_filename,
)


@dataclass
class TaskControl:
    pause_requested: bool = False
    remove_requested: bool = False


@dataclass
class DownloadTask:
    id: int
    url: str
    title: str
    platform: str
    fmt: str
    quality: str
    embed_subtitles: bool
    status: str = "QUEUED"
    progress: float = 0.0
    speed: str = "--"
    eta: str = "--"
    size_text: str = "--"
    size_bytes: int = 0
    duration: int = 0
    thumbnail_url: str = ""
    filepath: str = ""
    error_message: str = ""
    control: TaskControl = field(default_factory=TaskControl)


class MeroDownloader(QObject):
    task_added = pyqtSignal(dict)
    task_updated = pyqtSignal(dict)
    task_removed = pyqtSignal(int)
    history_changed = pyqtSignal()
    stats_changed = pyqtSignal(dict)
    toast = pyqtSignal(str, str)

    def __init__(self, database: DatabaseManager, config: dict[str, Any]):
        super().__init__()
        self.db = database
        self.config = config
        self.download_folder = ensure_folder(config["download_folder"])
        self.executor = ThreadPoolExecutor(max_workers=int(config.get("max_concurrent", 2)))
        self.lock = threading.Lock()
        self.tasks: dict[int, DownloadTask] = {}
        self.task_queue: queue.Queue[int] = queue.Queue()
        self._completed_session = 0
        self.dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True)
        self.dispatcher.start()

        self._load_existing_downloads()
        self._emit_stats()

    @property
    def version(self) -> str:
        return ytdlp_version

    def _load_existing_downloads(self) -> None:
        rows = self.db.get_downloads(statuses=["QUEUED", "DOWNLOADING", "PAUSED", "FAILED"])
        for row in rows:
            task = self._task_from_row(row)
            if task.status == "DOWNLOADING":
                task.status = "PAUSED"
                self.db.update_status(task.id, "PAUSED", "Recovered after app restart")
            self.tasks[task.id] = task
            self.task_added.emit(self._to_payload(task))

    def snapshot_tasks(self) -> list[dict[str, Any]]:
        return [self._to_payload(task) for task in self.tasks.values()]

    def _dispatch_loop(self) -> None:
        while True:
            task_id = self.task_queue.get()
            self.executor.submit(self._run_download, task_id)

    def inspect_url(self, url: str) -> dict[str, Any]:
        opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "no_warnings": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get("entries") or []
        if entries:
            items = []
            for item in entries:
                if not item:
                    continue
                item_url = item.get("url")
                if item_url and not item_url.startswith("http"):
                    item_url = item.get("webpage_url") or item_url
                items.append(
                    {
                        "title": item.get("title") or "Untitled",
                        "url": item_url,
                        "duration": item.get("duration") or 0,
                        "thumbnail": item.get("thumbnail") or "",
                    }
                )
            return {
                "is_playlist": True,
                "title": info.get("title") or "Playlist",
                "count": len(items),
                "items": items,
            }

        return {
            "is_playlist": False,
            "title": info.get("title") or "",
            "items": [
                {
                    "title": info.get("title") or "Untitled",
                    "url": info.get("webpage_url") or url,
                    "duration": info.get("duration") or 0,
                    "thumbnail": info.get("thumbnail") or "",
                }
            ],
        }

    def add_task(
        self,
        url: str,
        fmt: str,
        quality: str,
        embed_subtitles: bool,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        info = metadata or {}
        title = info.get("title") or "Fetching title..."
        platform = platform_from_url(url)
        duration = int(info.get("duration") or 0)
        thumbnail = info.get("thumbnail") or ""

        row_id = self.db.add_download(
            {
                "url": url,
                "title": title,
                "platform": platform,
                "format": fmt,
                "quality": quality,
                "status": "QUEUED",
                "duration": duration,
                "thumbnail_url": thumbnail,
            }
        )

        task = DownloadTask(
            id=row_id,
            url=url,
            title=title,
            platform=platform,
            fmt=fmt,
            quality=quality,
            embed_subtitles=embed_subtitles,
            duration=duration,
            thumbnail_url=thumbnail,
        )
        with self.lock:
            self.tasks[row_id] = task

        self.task_added.emit(self._to_payload(task))
        self._emit_stats()
        self.task_queue.put(row_id)
        return row_id

    def pause_task(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if task and task.status == "DOWNLOADING":
            task.control.pause_requested = True

    def resume_task(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task or task.status not in {"PAUSED", "FAILED"}:
            return
        task.control.pause_requested = False
        task.control.remove_requested = False
        task.error_message = ""
        task.status = "QUEUED"
        self.db.update_status(task.id, "QUEUED", "")
        self.task_updated.emit(self._to_payload(task))
        self.task_queue.put(task_id)
        self._emit_stats()

    def remove_task(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return
        if task.status == "DOWNLOADING":
            task.control.remove_requested = True
            return
        self.tasks.pop(task_id, None)
        self.db.delete_record(task_id)
        self.task_removed.emit(task_id)
        self._emit_stats()

    def retry_task(self, task_id: int) -> None:
        self.resume_task(task_id)

    def update_config(self, cfg: dict[str, Any]) -> None:
        self.config = cfg
        self.download_folder = ensure_folder(cfg["download_folder"])

    def _run_download(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return

        if self.db.has_duplicate(task.url, task.fmt, task.quality):
            self._set_failed(task, "Duplicate download found in history")
            return

        task.status = "DOWNLOADING"
        task.error_message = ""
        self.db.update_status(task.id, "DOWNLOADING", "")
        self.task_updated.emit(self._to_payload(task))
        self._emit_stats()

        def hook(data: dict[str, Any]) -> None:
            if task.control.remove_requested:
                raise DownloadError("Removed by user")
            if task.control.pause_requested:
                raise DownloadError("Paused by user")

            status = data.get("status")
            if status == "downloading":
                downloaded = data.get("downloaded_bytes") or 0
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                percent = (downloaded / total * 100) if total else 0
                task.progress = min(percent, 100)
                task.speed = format_speed(data.get("speed"))
                task.eta = format_eta(data.get("eta"))
                task.size_bytes = int(total) if total else task.size_bytes
                task.size_text = format_bytes(task.size_bytes)
                self.task_updated.emit(self._to_payload(task))
            elif status == "finished":
                task.progress = 100
                task.eta = "Done"
                task.speed = "--"
                self.task_updated.emit(self._to_payload(task))

        options = self._build_ydl_options(task, hook)

        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(task.url, download=True)
                requested = info.get("requested_downloads") or []
                if requested:
                    task.filepath = requested[0].get("filepath") or task.filepath
                task.title = info.get("title") or task.title
                task.thumbnail_url = info.get("thumbnail") or task.thumbnail_url
                task.duration = int(info.get("duration") or task.duration or 0)
                if not task.size_bytes:
                    est_size = info.get("filesize") or info.get("filesize_approx") or 0
                    if est_size:
                        task.size_bytes = int(est_size)
                        task.size_text = format_bytes(task.size_bytes)
            if task.control.remove_requested:
                raise DownloadError("Removed by user")
            if task.control.pause_requested:
                task.status = "PAUSED"
                self.db.update_status(task.id, "PAUSED", "Paused by user")
                self.task_updated.emit(self._to_payload(task))
                self._emit_stats()
                return

            task.status = "COMPLETED"
            task.completed_at = datetime.now().isoformat(timespec="seconds")
            self.db.update_download(
                task.id,
                {
                    "status": "COMPLETED",
                    "size_bytes": task.size_bytes,
                    "filepath": task.filepath,
                    "title": task.title,
                    "platform": task.platform,
                    "duration": task.duration,
                    "thumbnail_url": task.thumbnail_url,
                    "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error_message": "",
                },
            )
            self._completed_session += 1
            self.task_updated.emit(self._to_payload(task))
            self.history_changed.emit()
            self.toast.emit(
                "Download completed",
                f"{task.title} ({task.platform}) - {format_bytes(task.size_bytes)}",
            )
        except DownloadError as exc:
            msg = str(exc)
            if "Paused by user" in msg:
                task.status = "PAUSED"
                self.db.update_status(task.id, "PAUSED", "Paused by user")
            elif "Removed by user" in msg:
                self.tasks.pop(task.id, None)
                self.db.delete_record(task.id)
                self.task_removed.emit(task.id)
            else:
                self._set_failed(task, msg)
                return
            self.task_updated.emit(self._to_payload(task))
        except Exception as exc:  # noqa: BLE001
            self._set_failed(task, str(exc))
            return
        finally:
            self._emit_stats()

    def _set_failed(self, task: DownloadTask, error: str) -> None:
        task.status = "FAILED"
        task.error_message = error
        task.speed = "--"
        task.eta = "--"
        self.db.update_status(task.id, "FAILED", error)
        self.task_updated.emit(self._to_payload(task))
        self.history_changed.emit()
        self._emit_stats()

    def _build_ydl_options(self, task: DownloadTask, hook) -> dict[str, Any]:
        ext = task.fmt.lower()
        base_name = sanitize_filename(task.title or "video")
        outtmpl = os.path.join(self.download_folder, f"{base_name}.%(ext)s")

        opts: dict[str, Any] = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "continuedl": True,
            "progress_hooks": [hook],
            "merge_output_format": "mp4",
            "proxy": self.config.get("proxy") or None,
            "cookiefile": self.config.get("cookie_file") or None,
            "ratelimit": int(self.config.get("bandwidth_limit", 0)) * 1024 or None,
        }

        quality_map = {
            "360p": 360,
            "480p": 480,
            "720p": 720,
            "1080p": 1080,
            "4K": 2160,
            "Best Available": None,
            "Audio Only": None,
        }

        if ext in {"mp3", "m4a"} or task.quality == "Audio Only":
            opts["format"] = "bestaudio/best"
            if ext == "mp3":
                opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]
            elif ext == "m4a":
                opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                    }
                ]
        elif ext == "webm":
            height = quality_map.get(task.quality)
            if height:
                opts["format"] = f"bestvideo[ext=webm][height<={height}]+bestaudio[ext=webm]/best[ext=webm]"
            else:
                opts["format"] = "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]"
            opts["merge_output_format"] = "webm"
        else:
            height = quality_map.get(task.quality)
            if height:
                opts["format"] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
            else:
                opts["format"] = "bestvideo+bestaudio/best"

        if task.embed_subtitles:
            opts["writesubtitles"] = True
            opts["embedsubtitles"] = True
            opts["subtitleslangs"] = ["all"]
        opts["nopart"] = False
        return opts

    def _task_from_row(self, row: dict[str, Any]) -> DownloadTask:
        return DownloadTask(
            id=row["id"],
            url=row["url"],
            title=row.get("title") or "Untitled",
            platform=row.get("platform") or platform_from_url(row["url"]),
            fmt=row.get("format") or "mp4",
            quality=row.get("quality") or "Best Available",
            embed_subtitles=False,
            status=row.get("status") or "QUEUED",
            size_bytes=row.get("size_bytes") or 0,
            duration=row.get("duration") or 0,
            thumbnail_url=row.get("thumbnail_url") or "",
            filepath=row.get("filepath") or "",
            error_message=row.get("error_message") or "",
        )

    def _to_payload(self, task: DownloadTask) -> dict[str, Any]:
        return {
            "id": task.id,
            "url": task.url,
            "title": task.title,
            "platform": task.platform,
            "format": task.fmt,
            "quality": task.quality,
            "status": task.status,
            "progress": task.progress,
            "speed": task.speed,
            "eta": task.eta,
            "size_text": task.size_text,
            "size_bytes": task.size_bytes,
            "duration": task.duration,
            "thumbnail_url": task.thumbnail_url,
            "filepath": task.filepath,
            "error_message": task.error_message,
        }

    def _emit_stats(self) -> None:
        active = sum(1 for t in self.tasks.values() if t.status == "DOWNLOADING")
        queued = sum(1 for t in self.tasks.values() if t.status == "QUEUED")
        completed = sum(1 for t in self.tasks.values() if t.status == "COMPLETED")
        speed_total = 0.0
        for t in self.tasks.values():
            if t.speed.endswith("/s") and t.speed != "--":
                value, unit = t.speed.split(" ", 1)
                unit = unit.replace("/s", "")
                mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}.get(unit, 1)
                try:
                    speed_total += float(value) * mult
                except Exception:
                    pass
        self.stats_changed.emit(
            {
                "active": active,
                "queued": queued,
                "completed": completed,
                "completed_session": self._completed_session,
                "total_speed": format_speed(speed_total) if speed_total else "--",
                "version": self.version,
            }
        )
