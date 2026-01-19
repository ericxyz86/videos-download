# Video Downloader

A web-based video downloader powered by yt-dlp. Download videos from 50+ platforms including YouTube, Twitter/X, TikTok, Instagram, Reddit, and more.

## Features

- Download videos in multiple quality options (Best, 1080p, 720p, 480p)
- Extract audio only (MP3)
- Automatic H.264 conversion for QuickTime/macOS compatibility
- Clean web interface with download progress tracking
- Manage downloaded files directly from the browser

## Requirements

- Python 3.x
- ffmpeg (for video conversion)
- yt-dlp (included for macOS, or install via `brew install yt-dlp`)

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
./start.sh
```

Open http://localhost:8000 in your browser.

## Supported Platforms

| Category | Platforms |
|----------|-----------|
| Video | YouTube, Vimeo, Dailymotion, Twitch, Rumble, Bitchute, Odysee, Bilibili, Niconico, TED, Crunchyroll |
| Social | Twitter/X, Instagram, TikTok, Facebook, Reddit, Tumblr, VK |
| Short Clips | Streamable, Imgur, Gfycat, Coub |
| Audio | SoundCloud, Bandcamp, Mixcloud, Spotify |
| News | CNN, BBC |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/info` | POST | Get video metadata |
| `/api/download` | POST | Start download |
| `/api/progress/<id>` | GET | Check download progress |
| `/api/downloads` | GET | List downloaded files |
| `/api/delete/<filename>` | DELETE | Delete a file |

## License

MIT
