# Contributing

Thanks for helping. The most useful contribution is a **verified preset** for a new song.

## Adding a preset to `presets.json`

A preset only holds numbers (offsets, durations, loudness). **Never** add audio, video or any game file.

```json
"SongCodename": {
  "description": "Verified studio track timing profile (Artist)",
  "offset_seconds": 0.0,
  "target_lufs": -24.3,
  "main_video": { "duration": 0.0 },
  "clip_a": { "start_offset": 0.0, "duration": 0.0 },
  "clip_b": { "start_offset": 0.0, "duration": 0.0 },
  "preview": { "start_offset": 0.0, "duration": 0.0 }
}
```

What "verified" means here: you ran the toolkit with that preset and played the song on an Xbox 360 (or Xenia). The dancers show up, the audio stays in sync until the end, and the Mashup clips and the menu preview also work.

Allowed ranges (the toolkit ignores a preset outside them, and the tests check them):

| Field | Range |
| --- | --- |
| `offset_seconds` | -10 to 10 |
| `target_lufs` | -50 to 0 |
| `fade_out_seconds` | 0 to 1000 |
| `main_video.duration` | 1 to 1000 |
| `start_offset` | 0 to 1000 |
| clip / preview `duration` | 0.5 to 1000 |

The name can only have letters, digits and underscores.

## Before opening a pull request

```bash
python -m unittest discover -s tests -v
```

Changes to `presets.json`, `wma_pro_injector.py` and `.github/` are always reviewed by the owner (see `CODEOWNERS`).

## Security problems

Do not open a public issue. See [SECURITY.md](SECURITY.md).
