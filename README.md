# PhotoJournal

A Discord bot that turns image posts into dated, captioned polaroids and organizes them into a searchable local photo journal.

PhotoJournal watches selected Discord channels, saves image attachments by date, generates a polaroid-style copy with the message text, and provides commands for browsing, searching, exporting, and archiving the collection.

> **Status:** useful prototype. Core image processing and Discord commands are implemented, but permissions, destructive commands, path safety, tests, and deployment documentation need hardening.

## Features

- watches configured channels for image attachments
- stores original and polaroid versions in date-based folders
- adds a caption and timestamp with Pillow
- writes text sidecars for local caption search
- lists, retrieves, and randomly selects journal images
- exports a day as a ZIP archive
- downloads logs by date/channel through Discord commands
- supports caption regeneration
- includes age-based cleanup and moderator purge commands

## Example output

The repository includes `test_polaroid.jpg` as an early visual example. Do not treat it as a production screenshot or accuracy benchmark.

## Technology

- Python
- discord.py
- Pillow
- aiohttp
- python-dotenv

## Setup

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a local `.env` file:

```text
DISCORD_TOKEN=your-bot-token
```

Never commit the token. Enable the Discord message-content intent for the bot application.

## Configuration

Edit these constants in `bot.py` before running:

- `CHANNEL_NAMES`
- `IMAGE_ROOT`
- `MAX_IMAGE_SIZE_MB`
- `FONT_PATH`

## Run

```bash
python bot.py
```

Use `!helpme` in Discord for the current command list.

## Privacy and destructive commands

The bot saves Discord attachments and message captions to local storage. Server members should know what is retained, where it is stored, and who can access it.

`!cleanupdays` deletes local files, and `!purge` deletes Discord messages. Review and restrict command permissions before inviting the bot to a real server. Back up the journal before testing cleanup behavior.

## Validation status

No automated tests or CI workflow currently exist. Image rendering should be separated from Discord networking so it can be tested with temporary files. Commands also need permission, path-traversal, size-limit, and missing-folder tests.

## Known limitations

- most commands do not consistently restrict channel names or file paths
- the configured maximum upload size is not currently enforced
- some cleanup commands are broader than their help text suggests
- a new aiohttp session is created for each attachment
- failures are printed or sent directly without structured logging
- files are stored locally with no retention policy or backup mechanism

## Roadmap

- enforce attachment limits and safe path handling
- add explicit authorization checks for cleanup/archive commands
- test image rendering independently from Discord
- add configurable retention and storage limits
- reuse one HTTP session and add graceful shutdown
- add Docker or service deployment documentation
- create a privacy-safe demonstration server and GIF

## Authorship

Created by [SimpleCaci](https://github.com/SimpleCaci). A project license has not yet been selected.
