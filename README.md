# ShareTorrent Bot

## A Telegram bot that:
- Accepts a .torrent file from a user
- Parses and downloads the torrent
- Lets the user select an audio track (if multiple are present)
- Optionally generates and sends a short sample (about 1–2 minutes)
- Converts the original media to MP4 and uploads it back to a target chat

Works with Python, Telegram Bot API, libtorrent, and FFmpeg.

## Features

- Authorized-user access control via environment variables
- Torrent parsing with basic metadata preview (file count, total size, a few file names)
- Optional audio track selection for multi-audio videos
- Smart conversion strategy:
  - Downscale and/or transcode large files
  - Copy video stream when safe, transcode otherwise
  - Always uses AAC audio, MP4 container, and faststart flags
- Optional sample generation before full conversion/upload
- Uploads converted files to the current chat or a dedicated upload chat

## Requirements

- Python 3.13
- FFmpeg installed and available in PATH
- A Telegram Bot token
- Libtorrent installed
- A virtual environment (recommended)

## Configuration

Copy `.env.example` to `.env` and fill in values, or create a new `.env` file with:
```dotenv
BOT_TOKEN=123456789:ABCDEF_your_bot_token_here
# Optional: if you run a local/self-hosted Telegram Bot API (e.g., http://localhost:8081)
BASE_URL=http://localhost:8081
# Optional: read timeout (seconds)
READ_TIMEOUT=30
# Optional: numeric chat ID to upload converted files to (defaults to the user chat)
UPLOAD_CHAT_ID=
# Optional: comma-separated numeric user IDs allowed to use the bot
# Example: AVAILABLE_USER_IDS=12345678,987654321
AVAILABLE_USER_IDS=
```
### Environment variables:
- BOT_TOKEN: Your Telegram bot token
- BASE_URL: Only set if you use a self-hosted/local Bot API server. Otherwise leave unset.
- READ_TIMEOUT: Network read timeout used by the bot client
- UPLOAD_CHAT_ID: If set, the bot will send the final converted videos to this chat instead of the current chat
- AVAILABLE_USER_IDS: If set, only those user IDs can use the bot. Leave empty to allow anyone.

## Notes:
- The bot stores temporary data in these folders (created on demand):
  - torrents/ — incoming .torrent files
  - downloads/ — torrent download destination
  - upload/ — intermediate conversion output
- The “sample” step produces short previews for quick verification.
- Large files may be downscaled and transcoded to keep uploads tractable.
