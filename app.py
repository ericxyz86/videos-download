#!/usr/bin/env python3
"""Video Downloader Web App using yt-dlp"""

import os
import subprocess
import json
import re
import threading
import secrets
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_from_directory, abort

app = Flask(__name__)

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


# Allowed video URL patterns
ALLOWED_DOMAINS = [
    # YouTube
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
    # Vimeo
    'vimeo.com', 'www.vimeo.com', 'player.vimeo.com',
    # Dailymotion
    'dailymotion.com', 'www.dailymotion.com',
    # Twitch
    'twitch.tv', 'www.twitch.tv', 'clips.twitch.tv',
    # Twitter/X
    'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com',
    # Instagram
    'instagram.com', 'www.instagram.com',
    # TikTok
    'tiktok.com', 'www.tiktok.com', 'vm.tiktok.com',
    # Facebook
    'facebook.com', 'www.facebook.com', 'fb.watch', 'www.fb.watch',
    # Reddit
    'reddit.com', 'www.reddit.com', 'v.redd.it', 'old.reddit.com',
    # Streamable
    'streamable.com', 'www.streamable.com',
    # Imgur
    'imgur.com', 'www.imgur.com', 'i.imgur.com',
    # Gfycat
    'gfycat.com', 'www.gfycat.com',
    # Rumble
    'rumble.com', 'www.rumble.com',
    # Bitchute
    'bitchute.com', 'www.bitchute.com',
    # Odysee/LBRY
    'odysee.com', 'www.odysee.com',
    # PeerTube instances (common ones)
    'peertube.tv', 'framatube.org', 'video.blender.org',
    # Bilibili
    'bilibili.com', 'www.bilibili.com', 'b23.tv',
    # Niconico
    'nicovideo.jp', 'www.nicovideo.jp',
    # SoundCloud (audio)
    'soundcloud.com', 'www.soundcloud.com',
    # Bandcamp (audio)
    'bandcamp.com',
    # Mixcloud
    'mixcloud.com', 'www.mixcloud.com',
    # Spotify (limited support)
    'open.spotify.com',
    # CNN
    'cnn.com', 'www.cnn.com',
    # BBC
    'bbc.com', 'www.bbc.com', 'bbc.co.uk', 'www.bbc.co.uk',
    # Vevo
    'vevo.com', 'www.vevo.com',
    # Coub
    'coub.com', 'www.coub.com',
    # VK
    'vk.com', 'www.vk.com',
    # Flickr
    'flickr.com', 'www.flickr.com',
    # Tumblr
    'tumblr.com', 'www.tumblr.com',
    # Ted
    'ted.com', 'www.ted.com',
    # Crunchyroll
    'crunchyroll.com', 'www.crunchyroll.com',
]

VALID_FORMATS = {'best', '1080p', '720p', '480p'}


def is_valid_video_url(url):
    """Validate that URL is from an allowed video platform."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        domain = parsed.netloc.lower()
        return any(domain == d or domain.endswith('.' + d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def is_safe_filename(filename):
    """Check if filename is safe (no path traversal)."""
    if not filename:
        return False
    # Reject any path separators or parent directory references
    if '/' in filename or '\\' in filename or '..' in filename:
        return False
    # Reject null bytes
    if '\x00' in filename:
        return False
    return True


def get_safe_filepath(filename):
    """Get safe filepath within DOWNLOAD_DIR, returns None if unsafe."""
    if not is_safe_filename(filename):
        return None
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    # Double-check with realpath
    real_download_dir = os.path.realpath(DOWNLOAD_DIR)
    real_filepath = os.path.realpath(filepath)
    if not real_filepath.startswith(real_download_dir + os.sep):
        return None
    return filepath


# Store download progress
downloads = {}
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)


def get_video_info(url):
    """Get video information without downloading"""
    if not is_valid_video_url(url):
        return {'error': 'Invalid or unsupported video URL'}

    try:
        result = subprocess.run(
            [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                '--no-check-certificates',
                '--geo-bypass',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--extractor-args', 'youtube:player_client=web,default;youtube:player_skip=webpage',
                '--', url
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        # Sanitize error message - don't expose internal details
        return {'error': 'Failed to fetch video information'}
    except subprocess.TimeoutExpired:
        return {'error': 'Timeout while fetching video info'}
    except Exception:
        return {'error': 'An error occurred while fetching video info'}


def download_video(url, download_id, format_option='best', audio_only=False):
    """Download video in background thread"""
    downloads[download_id] = {
        'status': 'downloading',
        'progress': 0,
        'filename': None,
        'error': None
    }

    # Validate URL before processing
    if not is_valid_video_url(url):
        downloads[download_id]['status'] = 'error'
        downloads[download_id]['error'] = 'Invalid or unsupported video URL'
        return

    # Validate format option
    if format_option not in VALID_FORMATS:
        format_option = 'best'

    try:
        # Build command with options to help avoid bot detection
        cmd = [
            'yt-dlp',
            '--newline',
            '--progress',
            '--no-check-certificates',
            '--geo-bypass',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--extractor-args', 'youtube:player_client=web,default;youtube:player_skip=webpage',
        ]

        if audio_only:
            cmd.extend(['-x', '--audio-format', 'mp3'])
            output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')
        else:
            # Prefer H.264 (avc1) codec for QuickTime compatibility
            # Fallback to any format if H.264 not available
            if format_option == 'best':
                cmd.extend(['-f', 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]/bestvideo+bestaudio/best'])
            elif format_option == '1080p':
                cmd.extend(['-f', 'bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=1080][vcodec^=avc1]+bestaudio/best[height<=1080][vcodec^=avc1]/bestvideo[height<=1080]+bestaudio/best[height<=1080]'])
            elif format_option == '720p':
                cmd.extend(['-f', 'bestvideo[height<=720][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=720][vcodec^=avc1]+bestaudio/best[height<=720][vcodec^=avc1]/bestvideo[height<=720]+bestaudio/best[height<=720]'])
            elif format_option == '480p':
                cmd.extend(['-f', 'bestvideo[height<=480][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=480][vcodec^=avc1]+bestaudio/best[height<=480][vcodec^=avc1]/bestvideo[height<=480]+bestaudio/best[height<=480]'])

            cmd.extend(['--merge-output-format', 'mp4'])
            output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')

        # Use '--' to prevent URL from being interpreted as options
        cmd.extend(['-o', output_template, '--', url])

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        filename = None
        error_output = []
        for line in process.stdout:
            line = line.strip()

            # Capture potential error messages
            if 'ERROR' in line or 'error' in line.lower():
                error_output.append(line)

            # Parse progress
            if '[download]' in line:
                # Match percentage
                match = re.search(r'(\d+\.?\d*)%', line)
                if match:
                    downloads[download_id]['progress'] = float(match.group(1)) * 0.7  # 70% for download

                # Match destination filename
                if 'Destination:' in line:
                    filename = line.split('Destination:')[-1].strip()

            # Merger output
            if '[Merger]' in line or '[ExtractAudio]' in line:
                downloads[download_id]['progress'] = 70

        process.wait()

        if process.returncode != 0:
            downloads[download_id]['status'] = 'error'
            # Provide more helpful error message
            if error_output:
                error_msg = error_output[-1][:100]  # Last error, truncated
                if 'Sign in' in error_msg or 'bot' in error_msg.lower():
                    downloads[download_id]['error'] = 'Video requires authentication or is blocked'
                else:
                    downloads[download_id]['error'] = f'Download failed: {error_msg}'
            else:
                downloads[download_id]['error'] = 'Download failed - video may be unavailable'
            return

        # Find the downloaded file
        downloaded_file = None
        if filename:
            base = os.path.splitext(filename)[0]
            for ext in ['.mp4', '.webm', '.mkv', '.mp3']:
                check_path = base + ext
                if os.path.exists(check_path):
                    downloaded_file = check_path
                    break

        # For audio only, we're done
        if audio_only:
            downloads[download_id]['status'] = 'completed'
            downloads[download_id]['progress'] = 100
            if downloaded_file:
                downloads[download_id]['filename'] = os.path.basename(downloaded_file)
            return

        # Convert to H.264 for QuickTime compatibility (optional - skip if ffmpeg not available)
        if downloaded_file:
            downloads[download_id]['progress'] = 75

            # Check if ffmpeg is available
            ffmpeg_available = subprocess.run(['which', 'ffprobe'], capture_output=True).returncode == 0

            if ffmpeg_available:
                # Check if already H.264
                probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', downloaded_file]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                codec = probe_result.stdout.strip()

                if codec != 'h264':
                    # Need to convert
                    output_file = os.path.splitext(downloaded_file)[0] + '_converted.mp4'

                    convert_cmd = [
                        'ffmpeg', '-i', downloaded_file,
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
                        '-c:a', 'aac', '-b:a', '192k',
                        '-movflags', '+faststart',
                        '-y', output_file
                    ]

                    convert_process = subprocess.Popen(
                        convert_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )

                    # Monitor conversion progress
                    for line in convert_process.stdout:
                        if 'frame=' in line:
                            downloads[download_id]['progress'] = 85

                    convert_process.wait()

                    if convert_process.returncode == 0:
                        # Remove original, rename converted
                        os.remove(downloaded_file)
                        final_file = os.path.splitext(downloaded_file)[0] + '.mp4'
                        os.rename(output_file, final_file)
                        downloads[download_id]['filename'] = os.path.basename(final_file)
                    else:
                        # Conversion failed, keep original
                        downloads[download_id]['filename'] = os.path.basename(downloaded_file)
                else:
                    downloads[download_id]['filename'] = os.path.basename(downloaded_file)
            else:
                # ffmpeg not available, skip conversion
                downloads[download_id]['filename'] = os.path.basename(downloaded_file)

        downloads[download_id]['status'] = 'completed'
        downloads[download_id]['progress'] = 100

    except Exception:
        downloads[download_id]['status'] = 'error'
        downloads[download_id]['error'] = 'Download failed unexpectedly'


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')


@app.route('/api/info', methods=['POST'])
def video_info():
    """Get video information"""
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    if not is_valid_video_url(url):
        return jsonify({'error': 'Invalid or unsupported video URL'}), 400

    info = get_video_info(url)
    if 'error' in info:
        return jsonify(info), 400

    # Return relevant info
    return jsonify({
        'title': info.get('title', 'Unknown'),
        'thumbnail': info.get('thumbnail', ''),
        'duration': info.get('duration', 0),
        'uploader': info.get('uploader', 'Unknown'),
        'view_count': info.get('view_count', 0),
        'description': info.get('description', '')[:200] + '...' if info.get('description') else ''
    })


@app.route('/api/download', methods=['POST'])
def start_download():
    """Start a download"""
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    url = data.get('url', '').strip()
    format_option = data.get('format', 'best')
    audio_only = bool(data.get('audio_only', False))

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    if not is_valid_video_url(url):
        return jsonify({'error': 'Invalid or unsupported video URL'}), 400

    # Validate format option
    if format_option not in VALID_FORMATS:
        format_option = 'best'

    # Generate secure random download ID
    download_id = f"dl_{secrets.token_urlsafe(16)}"

    # Start download in background
    thread = threading.Thread(
        target=download_video,
        args=(url, download_id, format_option, audio_only)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'download_id': download_id})


@app.route('/api/progress/<download_id>')
def get_progress(download_id):
    """Get download progress"""
    if download_id not in downloads:
        return jsonify({'error': 'Download not found'}), 404

    return jsonify(downloads[download_id])


@app.route('/api/downloads')
def list_downloads():
    """List downloaded files"""
    files = []
    for filename in os.listdir(DOWNLOAD_DIR):
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.isfile(filepath):
            files.append({
                'name': filename,
                'size': os.path.getsize(filepath),
                'modified': os.path.getmtime(filepath)
            })

    # Sort by modified time, newest first
    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(files)


@app.route('/downloads/<filename>')
def serve_download(filename):
    """Serve downloaded file"""
    # Validate filename to prevent path traversal
    filepath = get_safe_filepath(filename)
    if not filepath or not os.path.isfile(filepath):
        abort(404)
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a downloaded file"""
    # Validate filename to prevent path traversal
    filepath = get_safe_filepath(filename)
    if not filepath:
        return jsonify({'error': 'Invalid filename'}), 400
    if not os.path.isfile(filepath):
        return jsonify({'error': 'File not found'}), 404
    os.remove(filepath)
    return jsonify({'success': True})


if __name__ == '__main__':
    print("\n" + "="*50)
    print("  Video Downloader")
    print("="*50)
    print(f"\n  Open in browser: http://localhost:8000")
    print(f"  Downloads folder: {DOWNLOAD_DIR}")
    print("\n  Press Ctrl+C to stop the server")
    print("="*50 + "\n")

    app.run(debug=False, host='127.0.0.1', port=8000)
