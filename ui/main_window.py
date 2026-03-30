import os
import subprocess
import sys

from plyer import notification
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.database import DatabaseManager
from core.downloader import MeroDownloader
from core.utils import ensure_folder, load_config, save_config
from ui.components.status_bar import BottomStatusBar
from ui.history_panel import HistoryPanel
from ui.queue_panel import QueuePanel
from ui.settings_panel import SettingsPanel
from ui.sidebar import Sidebar
from ui.url_bar import UrlBar


class PlaylistDialog(QDialog):
    def __init__(self, title: str, items: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist detected")
        self.setMinimumSize(540, 420)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"This URL contains {len(items)} videos in: {title}"))

        self.list_widget = QListWidget()
        for item in items:
            row = QListWidgetItem(item.get("title") or "Untitled")
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked)
            row.setData(Qt.ItemDataRole.UserRole, item)
            self.list_widget.addItem(row)
        root.addWidget(self.list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_items(self) -> list[dict]:
        selected = []
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                selected.append(it.data(Qt.ItemDataRole.UserRole))
        return selected


class MainWindow(QMainWindow):
    def __init__(self, app_dir: str):
        super().__init__()
        self.app_dir = app_dir
        self.config_path = os.path.join(app_dir, "config.yaml")
        self.config = load_config(self.config_path)
        ensure_folder(self.config["download_folder"])

        self.db = DatabaseManager(os.path.join(app_dir, "merodownload.db"))
        self.downloader = MeroDownloader(self.db, self.config)

        self.setWindowTitle("MeroDownload")
        self.setMinimumSize(1200, 780)
        icon_path = os.path.join(app_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.sidebar = Sidebar()
        self.url_bar = UrlBar(self.config)
        self.queue_panel = QueuePanel()
        self.history_panel = HistoryPanel()
        self.settings_panel = SettingsPanel(self.config)
        self.status_bar = BottomStatusBar()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.queue_panel)      # 0
        self.stack.addWidget(self.history_panel)    # 1
        self.stack.addWidget(self.settings_panel)   # 2

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.url_bar)
        right_layout.addWidget(self.stack, stretch=1)
        right_layout.addWidget(self.status_bar)

        split = QSplitter()
        split.addWidget(self.sidebar)
        split.addWidget(right)
        split.setSizes([200, 1000])

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(split)
        self.setCentralWidget(root)

        self._connect_events()
        for payload in self.downloader.snapshot_tasks():
            self.queue_panel.add_or_update(payload)
        self._apply_theme(self.config.get("theme", "light"))
        self._refresh_history()
        self.sidebar.update_storage(self.config["download_folder"])

    def _connect_events(self) -> None:
        self.sidebar.nav_clicked.connect(self._on_nav)
        self.url_bar.add_requested.connect(self._handle_add_url)

        self.queue_panel.pause_requested.connect(self.downloader.pause_task)
        self.queue_panel.resume_requested.connect(self.downloader.resume_task)
        self.queue_panel.remove_requested.connect(self.downloader.remove_task)
        self.queue_panel.open_folder_requested.connect(self._open_folder_for_task)

        self.downloader.task_added.connect(self.queue_panel.add_or_update)
        self.downloader.task_updated.connect(self.queue_panel.add_or_update)
        self.downloader.task_removed.connect(self.queue_panel.remove_card)
        self.downloader.history_changed.connect(self._refresh_history)
        self.downloader.stats_changed.connect(self.status_bar.update_stats)
        self.downloader.toast.connect(self._notify)

        self.history_panel.refresh_requested.connect(self._refresh_history)
        self.history_panel.delete_requested.connect(self._delete_history_record)

        self.settings_panel.save_requested.connect(self._save_settings)
        self.settings_panel.theme_changed.connect(self._apply_theme)

    def _on_nav(self, section: str) -> None:
        if section == "Queue":
            self.stack.setCurrentIndex(0)
            self.queue_panel.set_filter("ACTIVE")
        elif section == "Completed":
            self.stack.setCurrentIndex(0)
            self.queue_panel.set_filter("COMPLETED")
        elif section == "Failed":
            self.stack.setCurrentIndex(0)
            self.queue_panel.set_filter("FAILED")
        elif section in {"Videos", "Audio", "Playlists"}:
            self.stack.setCurrentIndex(1)
            self._refresh_history()
        else:
            self.stack.setCurrentIndex(2)

    def _handle_add_url(self, url: str, fmt: str, quality: str, subtitles: bool) -> None:
        try:
            info = self.downloader.inspect_url(url)
            if info.get("is_playlist"):
                dlg = PlaylistDialog(info.get("title") or "Playlist", info.get("items") or [], self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                selected = dlg.selected_items()
                if not selected:
                    return
                for item in selected:
                    item_url = item.get("url")
                    if not item_url:
                        continue
                    self.downloader.add_task(item_url, fmt, quality, subtitles, metadata=item)
                return

            item = (info.get("items") or [{}])[0]
            self.downloader.add_task(url, fmt, quality, subtitles, metadata=item)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Cannot add URL", str(exc))

    def _refresh_history(self, search: str = "", sort_by: str = "Date") -> None:
        rows = self.db.get_history(search=search, sort_by=sort_by)
        self.history_panel.set_records(rows)

    def _delete_history_record(self, record_id: int, delete_file: bool) -> None:
        rec = self.db.delete_record(record_id)
        if not rec:
            return
        path = rec.get("filepath") or ""
        if delete_file and path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Delete failed", str(exc))
        self._refresh_history()

    def _save_settings(self, payload: dict) -> None:
        self.config.update(payload)
        ensure_folder(self.config["download_folder"])
        save_config(self.config_path, self.config)
        for k, v in self.config.items():
            self.db.set_setting(k, v)
        self.downloader.update_config(self.config)
        self.sidebar.update_storage(self.config["download_folder"])
        self._apply_theme(self.config.get("theme", "light"))

    def _open_folder_for_task(self, task_id: int) -> None:
        task = self.downloader.tasks.get(task_id)
        if not task:
            return
        path = task.filepath
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "File not found", "Downloaded file path is unavailable.")
            return
        folder = os.path.dirname(path)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open folder failed", str(exc))

    def _notify(self, title: str, message: str) -> None:
        if not self.config.get("notifications", True):
            return
        try:
            notification.notify(title=title, message=message, app_name="MeroDownload", timeout=4)
        except Exception:
            return

    def _apply_theme(self, theme: str) -> None:
        if theme == "dark":
            self.setStyleSheet(
                """
                QWidget { background: #1a1a1a; color: #f5f5f5; font-size: 13px; }
                QFrame#sidebar, QFrame#urlBar, QFrame#bottomStatusBar { background: #242424; }
                QPushButton { background: #2d2d2d; border: 1px solid rgba(255,255,255,0.12); padding: 6px 10px; border-radius: 6px; }
                QPushButton:checked { background: #E24B4A; color: white; }
                QLineEdit, QComboBox, QSpinBox, QTableWidget, QListWidget { background: #242424; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 4px; }
                QProgressBar { background: #2a2a2a; border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; }
                QProgressBar::chunk { background: #639922; border-radius: 3px; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget { background: white; color: #222; font-size: 13px; }
                QFrame#sidebar, QFrame#urlBar, QFrame#bottomStatusBar { background: #f5f5f5; }
                QPushButton { background: white; border: 1px solid rgba(0,0,0,0.15); padding: 6px 10px; border-radius: 6px; }
                QPushButton:checked { background: #E24B4A; color: white; }
                QLineEdit, QComboBox, QSpinBox, QTableWidget, QListWidget { background: white; border: 1px solid rgba(0,0,0,0.15); border-radius: 6px; padding: 4px; }
                QProgressBar { background: #f0f0f0; border: 1px solid rgba(0,0,0,0.15); border-radius: 4px; }
                QProgressBar::chunk { background: #639922; border-radius: 3px; }
                """
            )

    def closeEvent(self, event):  # noqa: N802
        self.db.close()
        super().closeEvent(event)
