# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private reporting instead: go to the **Security** tab of this repository and click **Report a vulnerability**. You will get a first answer within 7 days.

Useful details to include: what you found, the file and line, how to reproduce it, and what an attacker could do with it.

## What is in scope

- `song_fix.py` and `wma_pro_injector.py` running on your PC (for example, running an unexpected executable, overwriting files outside the game folder, or unsafe handling of the input files).
- `presets.json` values that could make the toolkit misbehave.
- The GitHub workflows in `.github/`.

## What the toolkit does and does not do

- It does not use the network and does not download anything.
- It only runs `ffmpeg`, `ffprobe`, PowerShell (to check a digital signature) and, optionally, `radvideo64.exe` from RAD Video Tools. The RAD executable is run only if it has a valid digital signature.
- It never runs strings as code and never uses `shell=True`.
- Every game file is backed up as `<name>.bak` before it is changed, and new files are written to a temporary file first and swapped in at the end.

## Supported versions

Only the latest commit on `main` is supported.
