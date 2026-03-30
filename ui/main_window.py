import os
import subprocess
import sys
import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
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
    inspect_ready = pyqtSignal(dict, str, str, str, bool)
    inspect_failed = pyqtSignal(str)

    def __init__(self, app_dir: str):
        super().__init__()
        self.app_dir = app_dir
        self.config_path = os.path.join(app_dir, "config.yaml")
        self.config = load_config(self.config_path)
        self.config["theme"] = "dark"
        ensure_folder(self.config["download_folder"])

        self.db = DatabaseManager(os.path.join(app_dir, "merodownload.db"))
        self.downloader = MeroDownloader(self.db, self.config)

        self.setWindowTitle("MeroDownload")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 850)  # Default larger for better preview
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        icon_path = os.path.join(app_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.sidebar = Sidebar()
        self.url_bar = UrlBar(self.config)
        self.queue_panel = QueuePanel()
        self.history_panel = HistoryPanel()
        self.settings_panel = SettingsPanel(self.config)
        self.status_bar = BottomStatusBar()
        self._inspect_in_progress = False
        self._history_media_filter = "all"

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

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(self.sidebar)
        self.split.addWidget(right)
        self.split.setChildrenCollapsible(False)
        self.split.setHandleWidth(1)
        self.split.setStretchFactor(1, 1)
        self._sidebar_compact: bool | None = None
        self._adjust_splitter_for_width(self.width(), force=True)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.split)
        self.setCentralWidget(root)

        self._connect_events()
        for payload in self.downloader.snapshot_tasks():
            self.queue_panel.add_or_update(payload)
        self._apply_theme("dark")
        self._refresh_history()
        self.sidebar.update_storage(self.config["download_folder"])

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._adjust_splitter_for_width(self.width())

    def _adjust_splitter_for_width(self, width: int, force: bool = False) -> None:
        compact = width < 1240
        if not force and compact == self._sidebar_compact:
            return
        self._sidebar_compact = compact
        sidebar_width = 216 if compact else 272
        self.split.setSizes([sidebar_width, max(400, width - sidebar_width)])

    def _connect_events(self) -> None:
        self.sidebar.nav_clicked.connect(self._on_nav)
        self.url_bar.add_requested.connect(self._handle_add_url)
        self.inspect_ready.connect(self._on_inspect_ready)
        self.inspect_failed.connect(self._on_inspect_failed)

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
        self.history_panel.open_requested.connect(self._open_history_file)

        self.settings_panel.save_requested.connect(self._save_settings)
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
        elif section == "Videos":
            self.stack.setCurrentIndex(1)
            self._history_media_filter = "video"
            self._refresh_history()
        elif section == "Audio":
            self.stack.setCurrentIndex(1)
            self._history_media_filter = "audio"
            self._refresh_history()
        elif section == "Playlists":
            self.stack.setCurrentIndex(1)
            self._history_media_filter = "all"
            self._refresh_history()
        else:
            self.stack.setCurrentIndex(2)

    def _show_queue_active(self) -> None:
        self.stack.setCurrentIndex(0)
        self.queue_panel.set_filter("ACTIVE")
        btn = self.sidebar.buttons.get("Queue")
        if btn:
            btn.setChecked(True)
        for name, other in self.sidebar.buttons.items():
            if name != "Queue":
                other.setChecked(False)

    def _handle_add_url(self, url: str, fmt: str, quality: str, subtitles: bool) -> None:
        if self._inspect_in_progress:
            self.status_bar.flash("Already inspecting a URL. Please wait...")
            return

        self._inspect_in_progress = True
        self.url_bar.set_busy(True)

        def worker() -> None:
            try:
                info = self.downloader.inspect_url(url)
                self.inspect_ready.emit(info, url, fmt, quality, subtitles)
            except Exception as exc:  # noqa: BLE001
                self.inspect_failed.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_inspect_ready(self, info: dict, url: str, fmt: str, quality: str, subtitles: bool) -> None:
        self._inspect_in_progress = False
        self.url_bar.set_busy(False)
        try:
            if info.get("is_playlist"):
                dlg = PlaylistDialog(info.get("title") or "Playlist", info.get("items") or [], self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                selected = dlg.selected_items()
                if not selected:
                    return
                self._show_queue_active()
                added = 0
                for item in selected:
                    item_url = item.get("url")
                    if not item_url:
                        continue
                    self.downloader.add_task(item_url, fmt, quality, subtitles, metadata=item)
                    added += 1
                    QApplication.processEvents()
                if added:
                    self.status_bar.flash(f"Added {added} item(s) to queue.")
                return

            item = (info.get("items") or [{}])[0]
            self._show_queue_active()
            self.downloader.add_task(url, fmt, quality, subtitles, metadata=item)
            self.status_bar.flash("Added to queue.")
        except Exception as exc:  # noqa: BLE001
            self.status_bar.flash(f"Cannot add URL: {exc}")

    def _on_inspect_failed(self, error: str) -> None:
        self._inspect_in_progress = False
        self.url_bar.set_busy(False)
        self.status_bar.flash(f"Cannot add URL: {error}")

    def _refresh_history(self, search: str = "", sort_by: str = "Date") -> None:
        rows = self.db.get_history(search=search, sort_by=sort_by, media_filter=self._history_media_filter)
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
                self.status_bar.flash(f"Delete failed: {exc}")
        self._refresh_history()

    def _open_history_file(self, filepath: str) -> None:
        if not filepath or not os.path.exists(filepath):
            self.status_bar.flash("Selected file is unavailable.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(os.path.dirname(filepath))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", filepath])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(filepath)])
        except Exception as exc:  # noqa: BLE001
            self.status_bar.flash(f"Open file location failed: {exc}")

    def _save_settings(self, payload: dict) -> None:
        self.config.update(payload)
        self.config["theme"] = "dark"
        ensure_folder(self.config["download_folder"])
        save_config(self.config_path, self.config)
        for k, v in self.config.items():
            self.db.set_setting(k, v)
        self.downloader.update_config(self.config)
        self.sidebar.update_storage(self.config["download_folder"])
        self._apply_theme("dark")

    def _open_folder_for_task(self, task_id: int) -> None:
        task = self.downloader.tasks.get(task_id)
        if not task:
            return
        path = task.filepath
        if not path or not os.path.exists(path):
            self.status_bar.flash("Downloaded file path is unavailable.")
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
            self.status_bar.flash(f"Open folder failed: {exc}")

    def _notify(self, title: str, message: str) -> None:
        # Keep notifications in-app only to avoid desktop backend popup storms.
        self.status_bar.flash(f"{title}: {message}", timeout_ms=6000)

    def _apply_theme(self, theme: str) -> None:
        theme = "dark"
        if theme == "dark":
            qss = """
            QWidget {
                background: #0f1722;
                color: #e7edf5;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QMainWindow::separator { width: 1px; background: #253041; }
            QFrame#sidebar, QFrame#urlBar, QFrame#bottomStatusBar {
                background: #111b2a;
                border: none;
            }
            QFrame#urlBar {
                border-bottom: 1px solid #253041;
            }
            QFrame#bottomStatusBar {
                border-top: 1px solid #253041;
            }
            QLabel#appTitle {
                font-size: 19px;
                font-weight: 700;
                color: #f6f8fb;
            }
            QLabel#appSubtitle, QLabel#sidebarSectionLabel, QLabel#sidebarStorageText, QLabel#statusMetric {
                color: #9eb0c6;
                font-size: 12px;
            }
            QLabel#statusMessage {
                color: #8bc2ff;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#settingsInlineMessage {
                color: #8bc2ff;
                font-size: 12px;
            }
            QLabel#historySummary {
                color: #9eb0c6;
                font-size: 12px;
                padding-top: 2px;
            }
            QLabel#queueEmptyHint {
                color: #86a0bf;
                font-size: 14px;
                border: 1px dashed #2a3850;
                border-radius: 10px;
                background: #0f1a2c;
            }
            QPushButton {
                background: #1a2638;
                border: 1px solid #2a3850;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #22324a; border-color: #3b5475; }
            QPushButton:pressed { background: #152033; }
            QPushButton:disabled { color: #6f819a; border-color: #27354b; }
            QPushButton[navButton=\"true\"] {
                text-align: left;
                padding: 8px 10px;
            }
            QPushButton[navButton=\"true\"]:checked {
                background: #1f6feb;
                border-color: #1f6feb;
                color: #ffffff;
            }
            QPushButton[primary=\"true\"] {
                background: #238636;
                border-color: #238636;
                color: #ffffff;
            }
            QPushButton[primary=\"true\"]:hover { background: #2ca043; }
            QPushButton[secondary=\"true\"] {
                background: #172132;
            }
            QPushButton[danger=\"true\"] {
                border-color: #5e2831;
                color: #ffb6c0;
            }
            QPushButton[danger=\"true\"]:hover {
                background: #3a1d25;
                border-color: #893747;
            }
            QPushButton[iconButton=\"true\"] {
                padding: 0;
                border-radius: 6px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background: #0f1b2d;
                border: 1px solid #2a3850;
                border-radius: 8px;
                padding: 7px 10px;
                min-height: 22px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #4093ff;
            }
            QAbstractScrollArea, QScrollArea, QTableWidget {
                background: transparent;
            }
            QTableWidget {
                border: 1px solid #28364d;
                border-radius: 10px;
                gridline-color: #223249;
                alternate-background-color: #101a2a;
                background: #0e1828;
            }
            QHeaderView::section {
                background: #111f33;
                border: none;
                border-bottom: 1px solid #2a3850;
                color: #9eb0c6;
                padding: 8px;
                font-weight: 600;
            }
            QProgressBar {
                background: #17263b;
                border: 1px solid #2a3850;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background: #2ea043;
            }
            QFrame#downloadCard {
                background: #111c2c;
                border: 1px solid #25374f;
                border-radius: 12px;
            }
            QLabel#cardTitle { font-size: 14px; font-weight: 700; color: #f2f6fb; }
            QLabel#cardMeta { font-size: 12px; color: #9eb0c6; }
            QLabel#cardThumbnail {
                background: #182538;
                border: 1px solid #2a3850;
                border-radius: 8px;
                color: #8ea2bd;
            }
            QFrame#settingsSection {
                background: #111d2e;
                border: 1px solid #263952;
                border-radius: 10px;
            }
            QLabel#settingsSectionTitle {
                font-size: 14px;
                font-weight: 700;
                color: #f2f6fb;
            }
            """
            self.setStyleSheet(qss)
        else:  # light
            qss = """
            QWidget {
                background: #f3f6fb;
                color: #1f2a37;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QMainWindow::separator { width: 1px; background: #d4dde8; }
            QFrame#sidebar, QFrame#urlBar, QFrame#bottomStatusBar {
                background: #ffffff;
                border: none;
            }
            QFrame#urlBar {
                border-bottom: 1px solid #d4dde8;
            }
            QFrame#bottomStatusBar {
                border-top: 1px solid #d4dde8;
            }
            QLabel#appTitle {
                font-size: 19px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#appSubtitle, QLabel#sidebarSectionLabel, QLabel#sidebarStorageText, QLabel#statusMetric {
                color: #64748b;
                font-size: 12px;
            }
            QLabel#statusMessage {
                color: #1f6feb;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#settingsInlineMessage {
                color: #1f6feb;
                font-size: 12px;
            }
            QLabel#historySummary {
                color: #64748b;
                font-size: 12px;
                padding-top: 2px;
            }
            QLabel#queueEmptyHint {
                color: #71819b;
                font-size: 14px;
                border: 1px dashed #d4dde8;
                border-radius: 10px;
                background: #ffffff;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #d4dde8;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #eef3fa; border-color: #c1cfdf; }
            QPushButton:pressed { background: #e6edf8; }
            QPushButton:disabled { color: #9aa6b8; border-color: #d9e1ec; }
            QPushButton[navButton=\"true\"] {
                text-align: left;
                padding: 8px 10px;
            }
            QPushButton[navButton=\"true\"]:checked {
                background: #1f6feb;
                border-color: #1f6feb;
                color: #ffffff;
            }
            QPushButton[primary=\"true\"] {
                background: #238636;
                border-color: #238636;
                color: #ffffff;
            }
            QPushButton[primary=\"true\"]:hover { background: #2da043; }
            QPushButton[secondary=\"true\"] {
                background: #f8fbff;
            }
            QPushButton[danger=\"true\"] {
                color: #b4233d;
                border-color: #f1bdc7;
            }
            QPushButton[danger=\"true\"]:hover {
                background: #fff2f5;
                border-color: #e99aaa;
            }
            QPushButton[iconButton=\"true\"] {
                padding: 0;
                border-radius: 6px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background: #ffffff;
                border: 1px solid #d4dde8;
                border-radius: 8px;
                padding: 7px 10px;
                min-height: 22px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #2f81f7;
            }
            QAbstractScrollArea, QScrollArea, QTableWidget {
                background: transparent;
            }
            QTableWidget {
                border: 1px solid #d4dde8;
                border-radius: 10px;
                gridline-color: #e7edf5;
                alternate-background-color: #f8fbff;
                background: #ffffff;
            }
            QHeaderView::section {
                background: #f8fbff;
                border: none;
                border-bottom: 1px solid #d4dde8;
                color: #5b6d84;
                padding: 8px;
                font-weight: 600;
            }
            QProgressBar {
                background: #f0f5fb;
                border: 1px solid #d4dde8;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background: #2da043;
            }
            QFrame#downloadCard {
                background: #ffffff;
                border: 1px solid #d4dde8;
                border-radius: 12px;
            }
            QLabel#cardTitle { font-size: 14px; font-weight: 700; color: #111827; }
            QLabel#cardMeta { font-size: 12px; color: #64748b; }
            QLabel#cardThumbnail {
                background: #f6f8fc;
                border: 1px solid #d4dde8;
                border-radius: 8px;
                color: #8797ad;
            }
            QFrame#settingsSection {
                background: #ffffff;
                border: 1px solid #d4dde8;
                border-radius: 10px;
            }
            QLabel#settingsSectionTitle {
                font-size: 14px;
                font-weight: 700;
                color: #152033;
            }
            """
            self.setStyleSheet(qss)

    def closeEvent(self, event):  # noqa: N802
        self.db.close()
        super().closeEvent(event)
