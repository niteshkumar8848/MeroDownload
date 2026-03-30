# MeroDownload

Modern desktop video downloader built with PyQt6 + yt-dlp.

## Features
- Multi-platform URL downloads (YouTube, Instagram, Twitter/X, Facebook, TikTok, Reddit, and more via yt-dlp)
- Queue with per-item progress, speed, ETA, pause/resume/retry
- Playlist detection with selection dialog
- SQLite history and settings persistence
- Config-backed defaults in `config.yaml`
- Desktop notifications on completion
- Light/Dark theme toggle

## Run
```bash
cd MeroDownload
pip install -r requirements.txt
python main.py
```

## Package (optional)
```bash
cd MeroDownload
pyinstaller MeroDownload.spec
```

## Notes
- For best media merging and audio conversion support, install `ffmpeg` on your system.
- `yt-dlp` site support depends on upstream extractors and website changes.
