# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Start the server (activates venv and runs on port 8000)
./start.sh

# Or manually:
source venv/bin/activate
python app.py
```

The app runs at http://localhost:8000

## Dependencies

- Python 3.14 with Flask (see requirements.txt)
- yt-dlp binary (included as `yt-dlp_macos`)
- ffmpeg/ffprobe (for H.264 conversion)

Install Python deps: `pip install -r requirements.txt`

## Architecture

Single-file Flask app (`app.py`) with embedded yt-dlp integration:

- **URL validation**: `ALLOWED_DOMAINS` whitelist controls which video platforms are accepted (50+ sites including YouTube, Twitter/X, TikTok, Instagram, Reddit, etc.)
- **Download flow**: POST to `/api/download` spawns background thread → polls `/api/progress/<id>` → serves file from `/downloads/<filename>`
- **Video processing**: Downloads via yt-dlp, then converts to H.264/AAC if needed for QuickTime compatibility
- **Frontend**: Single `templates/index.html` with inline CSS/JS, no build step

## Key Files

- `app.py` - All backend logic (routes, download management, video processing)
- `templates/index.html` - Complete frontend (styles, UI, API client)
- `downloads/` - Where downloaded videos are stored

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/info` | POST | Fetch video metadata (title, thumbnail, duration) |
| `/api/download` | POST | Start background download, returns `download_id` |
| `/api/progress/<id>` | GET | Poll download progress (0-100%) |
| `/api/downloads` | GET | List downloaded files |
| `/api/delete/<filename>` | DELETE | Remove downloaded file |

## Adding New Platforms

Edit `ALLOWED_DOMAINS` list in `app.py`. The backend uses yt-dlp which supports 1000+ sites - the whitelist is for security. Note: the frontend `index.html` has its own `allowedDomains` array for client-side validation that should be kept in sync.
