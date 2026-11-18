#!/usr/bin/env python3
"""
Universal Song Audio Replacement Toolkit for Just Dance Greatest Hits (Xbox 360 - XEX Format)
Replaces in-game covers or tracks with original/uncensored studio versions.
Supports community-verified timing presets (presets.json) and automatic timing analysis.

The video stream and the ASF container of every game file are kept byte-for-byte.
Only the audio payloads are swapped (see wma_pro_injector.py), which needs Windows.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

VERBOSE = False
SAFE_NAME = re.compile(r"^[A-Za-z0-9_]+$")

BUILTIN_PRESETS = {
    "BarbieGirl": {
        "description": "Verified studio track timing profile",
        "offset_seconds": 0.750,
        "target_lufs": -24.3,
        "main_video": {
            "duration": 196.642
        },
        "clip_a": {
            "start_offset": 41.47,
            "duration": 41.02
        },
        "clip_b": {
            "start_offset": 93.58,
            "duration": 44.62
        },
        "preview": {
            "start_offset": 43.58,
            "duration": 8.37
        }
    },
    "CantTouchThis": {
        "description": "Verified studio track timing profile",
        "offset_seconds": -2.800,
        "target_lufs": -24.3,
        "fade_out_seconds": 205.50,
        "main_video": {
            "duration": 210.68
        },
        "clip_a": {
            "start_offset": 93.96,
            "duration": 42.07
        },
        "clip_b": {
            "start_offset": 162.48,
            "duration": 48.16
        },
        "preview": {
            "start_offset": 7.84,
            "duration": 10.67
        }
    }
}


class ToolkitError(Exception):
    """A user-facing error: printed without a traceback."""


class UserQuit(Exception):
    """The user typed 'q' at a prompt."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ask(prompt):
    try:
        value = input(prompt).strip().strip('"')
    except EOFError:
        raise ToolkitError("No interactive input available. Pass the options on the command line (see --help).")
    if value.lower() in ("q", "quit", "exit"):
        raise UserQuit()
    return value


def run_tool(cmd):
    """Runs ffmpeg/ffprobe, hides the noise, and shows the last lines of stderr if it fails."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    except FileNotFoundError:
        raise ToolkitError(f"'{cmd[0]}' was not found in PATH.")
    if result.returncode != 0:
        tail = "\n".join((result.stderr or "").strip().splitlines()[-12:])
        raise ToolkitError(f"{cmd[0]} failed (exit code {result.returncode}). Last output:\n{tail}")
    if VERBOSE and result.stderr:
        print(result.stderr)
    return result


def check_tools():
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception:
            raise ToolkitError(
                f"'{tool}' was not found in PATH.\n"
                "    Please install FFmpeg (it includes ffprobe) and add it to your PATH environment variable.")


def probe_duration(path):
    result = run_tool(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1", path])
    try:
        value = float(result.stdout.strip())
    except ValueError:
        raise ToolkitError(f"Could not read the duration of {path}.")
    if value <= 0:
        raise ToolkitError(f"Invalid duration reported for {path}.")
    return value


def probe_duration_or(path, default, what):
    try:
        return probe_duration(path)
    except ToolkitError:
        print(f"    [!] Could not read the duration of the {what}. Using {default}s.")
        return default


def media_has_streams(path, kinds=("video", "audio")):
    """True when the file decodes with ffprobe and has every requested stream type."""
    try:
        result = run_tool(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                           "-of", "csv=p=0", path])
    except ToolkitError:
        return False
    found = set(result.stdout.split())
    return all(kind in found for kind in kinds)


def atomic_copy(src, dst):
    """Copies src to a temporary file next to dst and swaps it in, so dst is never half-written."""
    tmp = dst + ".tmp"
    try:
        shutil.copy2(src, tmp)
        if os.path.getsize(tmp) == 0 or os.path.getsize(tmp) != os.path.getsize(src):
            raise ToolkitError(f"Copy to {dst} was incomplete.")
        os.replace(tmp, dst)
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

def _is_num(value, lo, hi):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and lo <= value <= hi


def validate_preset(name, preset):
    """Returns a list of problems (empty when the preset is safe to use)."""
    problems = []
    if not SAFE_NAME.match(str(name)):
        problems.append("the name may only contain letters, digits and underscores")
    if not isinstance(preset, dict):
        return problems + ["the preset must be an object"]

    checks = {
        "offset_seconds": (-10, 10),
        "target_lufs": (-50, 0),
        "fade_out_seconds": (0, 1000),
    }
    for key, (lo, hi) in checks.items():
        if key in preset and not _is_num(preset[key], lo, hi):
            problems.append(f"'{key}' must be a number between {lo} and {hi}")

    sections = {
        "main_video": ({"duration": (1, 1000)}),
        "clip_a": ({"start_offset": (0, 1000), "duration": (0.5, 1000)}),
        "clip_b": ({"start_offset": (0, 1000), "duration": (0.5, 1000)}),
        "preview": ({"start_offset": (0, 1000), "duration": (0.5, 1000)}),
    }
    for section, fields in sections.items():
        if section not in preset:
            continue
        if not isinstance(preset[section], dict):
            problems.append(f"'{section}' must be an object")
            continue
        for key, (lo, hi) in fields.items():
            if key in preset[section] and not _is_num(preset[section][key], lo, hi):
                problems.append(f"'{section}.{key}' must be a number between {lo} and {hi}")
    return problems


def load_presets():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    preset_file = os.path.join(script_dir, "presets.json")
    presets = dict(BUILTIN_PRESETS)
    if not os.path.isfile(preset_file):
        return presets
    try:
        with open(preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[!] Warning: presets.json is not valid JSON ({e}). Using only the built-in presets.")
        return presets
    except OSError as e:
        print(f"[!] Warning: could not read presets.json ({e}). Using only the built-in presets.")
        return presets

    loaded = data.get("presets") if isinstance(data, dict) else None
    if not isinstance(loaded, dict):
        print("[!] Warning: presets.json has no 'presets' object. Using only the built-in presets.")
        return presets
    for name, preset in loaded.items():
        problems = validate_preset(name, preset)
        if problems:
            print(f"[!] Warning: preset '{name}' ignored: " + "; ".join(problems))
        else:
            presets[name] = preset
    return presets


# ---------------------------------------------------------------------------
# RAD Video Tools (Bink preview)
# ---------------------------------------------------------------------------

def find_radvideo(explicit=None):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for path in (r"C:\Program Files (x86)\RADVideo\radvideo64.exe",
                 r"C:\Program Files\RADVideo\radvideo64.exe"):
        if os.path.isfile(path):
            return path
    return None


def is_validly_signed(path):
    """True when the executable has a valid Authenticode signature (Windows only)."""
    env = dict(os.environ, JD_EXE_PATH=path)
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-AuthenticodeSignature -LiteralPath $env:JD_EXE_PATH).Status"],
            capture_output=True, text=True, env=env, timeout=60)
        return result.stdout.strip() == "Valid"
    except Exception:
        return False


def _click_mix_buttons(pid):
    """Sends a click to the 'Mix'/'Done' buttons of the windows owned by pid. Returns True if one was clicked."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    clicked = [False]

    def text_of(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value.lower()

    def on_child(chwnd, _):
        text = text_of(chwnd)
        if "mix" in text or "done" in text:
            user32.SendMessageW(chwnd, 0x00F5, 0, 0)  # BM_CLICK
            clicked[0] = True
        return True

    def on_top(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            user32.EnumChildWindows(hwnd, enum_proc(on_child), 0)
        return True

    user32.EnumWindows(enum_proc(on_top), 0)
    return clicked[0]


def mix_bink_auto(radvideo_exe, in_bik, in_wav, out_bik, timeout=90):
    """
    Drives radvideo64.exe 'binkmix' and waits for the output to finish writing
    (size stable for 2 s) instead of sleeping a fixed time and killing the process.
    """
    if os.path.isfile(out_bik):
        os.remove(out_bik)
    proc = subprocess.Popen([radvideo_exe, "binkmix", in_bik, in_wav, out_bik, "/o"])
    deadline = time.time() + timeout
    last_click = 0.0
    last_size = -1
    stable_since = None
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if not os.path.isfile(out_bik) and time.time() - last_click >= 5:
                _click_mix_buttons(proc.pid)
                last_click = time.time()
            if os.path.isfile(out_bik):
                size = os.path.getsize(out_bik)
                if size > 0 and size == last_size:
                    if stable_since is None:
                        stable_since = time.time()
                    elif time.time() - stable_since >= 2:
                        break
                else:
                    stable_since = None
                last_size = size
            time.sleep(0.5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.isfile(out_bik) and os.path.getsize(out_bik) > 0 and media_has_streams(out_bik)


# ---------------------------------------------------------------------------
# Game folder
# ---------------------------------------------------------------------------

def get_installed_songs(video_dir):
    if not os.path.isdir(video_dir):
        return []
    songs = []
    for f in os.listdir(video_dir):
        low = f.lower()
        if low.endswith(".wmv") and not low.endswith("_a.wmv") and not low.endswith("_b.wmv"):
            songs.append(f[:-4])
    return sorted(songs)


def song_targets(song):
    return [f"{song}.wmv", f"{song}_A.wmv", f"{song}_B.wmv", f"{song}_Preview.bik"]


def backup_originals(video_dir, song):
    for fname in song_targets(song):
        src = os.path.join(video_dir, fname)
        bak = src + ".bak"
        if os.path.isfile(src) and not os.path.isfile(bak):
            atomic_copy(src, bak)
            print(f"    Backed up: {fname} -> {fname}.bak")
        elif os.path.isfile(bak):
            print(f"    Backup already exists: {fname}.bak")


def restore_song(video_dir, song):
    restored = 0
    for fname in song_targets(song):
        path = os.path.join(video_dir, fname)
        bak = path + ".bak"
        if os.path.isfile(bak):
            atomic_copy(bak, path)
            print(f"    Restored: {fname}")
            restored += 1
    extra = os.path.join(video_dir, f"{song}_preview.wav")
    if os.path.isfile(extra):
        os.remove(extra)
        print(f"    Removed exported file: {song}_preview.wav")
    if restored == 0:
        raise ToolkitError(f"No .bak files found for '{song}'. Nothing to restore.")


# ---------------------------------------------------------------------------
# Automatic timing offset (only for songs without a preset)
# ---------------------------------------------------------------------------

def compute_timing_offset(ref_video, new_audio, start_sec=10.0, dur_sec=35.0):
    try:
        import librosa
        import numpy as np
        from scipy import signal
    except ImportError:
        print("[!] Note: 'librosa'/'scipy' not found. Using default offset = 0.0s.")
        print("    Install them with: pip install -r requirements-optional.txt to enable automatic offset detection.")
        return 0.0

    try:
        with tempfile.TemporaryDirectory(prefix="jd_align_") as t_dir:
            t_orig = os.path.join(t_dir, "ref.wav")
            t_new = os.path.join(t_dir, "new.wav")
            run_tool(["ffmpeg", "-y", "-ss", str(start_sec), "-i", ref_video, "-t", str(dur_sec),
                      "-vn", "-ar", "22050", "-ac", "1", t_orig])
            run_tool(["ffmpeg", "-y", "-ss", str(start_sec), "-i", new_audio, "-t", str(dur_sec),
                      "-vn", "-ar", "22050", "-ac", "1", t_new])

            sr = 22050
            yo, _ = librosa.load(t_orig, sr=sr)
            yn, _ = librosa.load(t_new, sr=sr)

            env_o = librosa.onset.onset_strength(y=yo, sr=sr)
            env_n = librosa.onset.onset_strength(y=yn, sr=sr)

            corr = signal.correlate(env_n, env_o, mode="full")
            lags = signal.correlation_lags(len(env_n), len(env_o), mode="full")
            best_lag = lags[np.argmax(corr)]
            return (best_lag * 512) / sr
    except Exception as e:
        print(f"[!] Warning: Auto-detection failed ({e}). Defaulting offset to 0.0s.")
        return 0.0


# ---------------------------------------------------------------------------
# Processing steps
# ---------------------------------------------------------------------------

def build_norm_cmd(audio_path, offset, duration, lufs, fade_at, out_wav):
    """ffmpeg command that trims/pads the replacement audio, normalizes it and (optionally) fades it out."""
    cmd = ["ffmpeg", "-y"]
    if offset > 0:
        cmd += ["-ss", str(offset)]
    cmd += ["-i", audio_path, "-t", str(duration)]

    filters = []
    if offset < 0:
        # negative offset: the new audio must start later, so pad silence at the beginning
        delay_ms = int(round(-offset * 1000))
        filters.append(f"adelay={delay_ms}|{delay_ms}")
    filters.append(f"loudnorm=I={lufs}:TP=-1.5:LRA=7")
    if fade_at and fade_at < duration:
        filters.append(f"afade=t=out:st={fade_at - 0.7:.2f}:d=0.7")

    cmd += ["-af", ",".join(filters), "-ar", "48000", "-ac", "2", out_wav]
    return cmd


def inject(source, wav_path, dest_tmp, label):
    if sys.platform != "win32":
        raise ToolkitError("WMA Pro injection needs Windows (it uses the WMAudio Encoder that ships with Windows).")
    try:
        from wma_pro_injector import patch_wmv_with_audio
        ok = patch_wmv_with_audio(source, wav_path, dest_tmp)
    except ToolkitError:
        raise
    except Exception as e:
        raise ToolkitError(f"WMA Pro injection failed for {label}: {e}")
    if not ok:
        raise ToolkitError(
            f"WMA Pro injection failed for {label}. The game file was NOT modified (backups are intact).")


def process_main(song, video_dir, source_wmv, norm_wav, work):
    print(f"\n[*] Step 3: Injecting native WMA Pro audio into ({song}.wmv)...")
    temp_main = os.path.join(work, f"{song}.wmv")
    inject(source_wmv, norm_wav, temp_main, f"{song}.wmv")
    atomic_copy(temp_main, os.path.join(video_dir, f"{song}.wmv"))
    print(f"    {song}.wmv updated successfully.")


def process_clips(song, video_dir, preset, norm_wav, work):
    for sub in ("A", "B"):
        sub_name = f"{song}_{sub}.wmv"
        sub_path = os.path.join(video_dir, sub_name)
        source_sub = sub_path + ".bak" if os.path.isfile(sub_path + ".bak") else sub_path
        if not os.path.isfile(source_sub):
            continue
        print(f"\n[*] Step 4{sub}: Processing Mashup Clip {sub} ({sub_name})...")
        clip_key = f"clip_{sub.lower()}"
        if preset and clip_key in preset:
            sub_start = preset[clip_key].get("start_offset", 0.0)
            sub_dur = preset[clip_key].get("duration", 40.0)
        else:
            sub_dur = probe_duration_or(source_sub, 40.0, f"Mashup Clip {sub}")
            sub_start = 0.0

        sub_wav = os.path.join(work, f"clip_{sub}.wav")
        run_tool(["ffmpeg", "-y", "-ss", str(sub_start), "-i", norm_wav, "-t", str(sub_dur),
                  "-c:a", "pcm_s16le", sub_wav])
        temp_sub = os.path.join(work, sub_name)
        inject(source_sub, sub_wav, temp_sub, sub_name)
        atomic_copy(temp_sub, sub_path)
        print(f"    {sub_name} updated successfully.")


def process_preview(song, video_dir, preset, norm_wav, work, radvideo_arg):
    preview_name = f"{song}_Preview.bik"
    preview_path = os.path.join(video_dir, preview_name)
    source_preview = preview_path + ".bak" if os.path.isfile(preview_path + ".bak") else preview_path
    if not os.path.isfile(source_preview):
        return
    print(f"\n[*] Step 5: Processing Menu Preview ({preview_name})...")
    if preset and "preview" in preset:
        prev_start = preset["preview"].get("start_offset", 40.0)
        prev_dur = preset["preview"].get("duration", 8.37)
    else:
        prev_dur = probe_duration_or(source_preview, 8.37, "menu preview")
        prev_start = 40.0

    preview_wav = os.path.join(work, "preview_norm.wav")
    run_tool(["ffmpeg", "-y", "-ss", str(prev_start), "-i", norm_wav, "-t", str(prev_dur),
              "-ar", "44100", "-ac", "2", preview_wav])

    exported = os.path.join(video_dir, f"{song}_preview.wav")
    radvideo_exe = find_radvideo(radvideo_arg)
    if radvideo_exe and sys.platform == "win32":
        if not is_validly_signed(radvideo_exe):
            print(f"    [!] {radvideo_exe} does not have a valid digital signature. Not running it.")
            radvideo_exe = None
    if not radvideo_exe:
        shutil.copy2(preview_wav, exported)
        print(f"    [i] RAD Video Tools not usable. Exported audio as '{song}_preview.wav'.")
        return

    print(f"    RAD Video Tools detected at: {radvideo_exe}")
    temp_bik = os.path.join(work, preview_name)
    if mix_bink_auto(radvideo_exe, source_preview, preview_wav, temp_bik):
        atomic_copy(temp_bik, preview_path)
        print(f"    {preview_name} updated successfully.")
    else:
        shutil.copy2(preview_wav, exported)
        print(f"    [!] Could not auto-mix Bink video. Exported preview audio as '{song}_preview.wav'.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Universal Song Replacement Toolkit for Just Dance Greatest Hits (Xbox 360 XEX).")
    parser.add_argument("-g", "--game-dir", help="Path to Just Dance Greatest Hits directory (extracted XEX format)")
    parser.add_argument("-s", "--song", help="Song codename to replace (e.g. BarbieGirl, etc.)")
    parser.add_argument("-a", "--audio", help="Path to replacement audio file (FLAC, WAV, MP3, etc.)")
    parser.add_argument("-o", "--offset", type=float, help="Manual offset in seconds (positive trims the start of the replacement audio, negative adds silence before it)")
    parser.add_argument("-l", "--lufs", type=float, default=None, help="Target integrated loudness in LUFS (defaults to preset or -24.3)")
    parser.add_argument("--radvideo", help="Path to radvideo64.exe if it is not in the default install folder")
    parser.add_argument("--restore", action="store_true", help="Restore the original files of --song from their .bak backups and exit")
    parser.add_argument("--verbose", action="store_true", help="Show the full ffmpeg output")
    parser.add_argument("--list", action="store_true", help="List all detected songs in the game folder and exit")
    parser.add_argument("--list-presets", action="store_true", help="List all verified timing presets available and exit")
    return parser.parse_args(argv)


def resolve_game_dir(args):
    game_dir = args.game_dir
    while not game_dir or not os.path.isdir(game_dir):
        game_dir = ask("\nEnter path to Just Dance Greatest Hits game directory (q to quit): ")
        if not os.path.isdir(game_dir):
            print("[!] Invalid directory. Please try again.")
    video_dir = os.path.join(game_dir, "videos")
    if not os.path.isdir(video_dir):
        raise ToolkitError(
            f"'videos' folder not found inside {game_dir}\n"
            "    Make sure the game is in extracted XEX format, not GOD (Games on Demand).")
    return video_dir


def choose_song(args, available_songs, presets_db, video_dir):
    song = args.song
    while not song or song not in available_songs:
        if not song:
            print(f"\n[*] Detected {len(available_songs)} songs in game directory:")
            for idx, s in enumerate(available_songs, 1):
                preset_mark = " *" if s in presets_db else ""
                print(f"    [{idx:2d}] {s}{preset_mark}")
            if any(s in presets_db for s in available_songs):
                print("    (* = Verified timing preset included)")
            choice = ask("\nSelect song number or enter exact codename (q to quit): ")
            if choice.isdigit() and 1 <= int(choice) <= len(available_songs):
                song = available_songs[int(choice) - 1]
            elif choice in available_songs:
                song = choice
            else:
                print("[!] Invalid choice. Please try again.")
        else:
            print(f"[!] Song '{song}' not found in {video_dir}.")
            song = None
    return song


def run(args):
    presets_db = load_presets()

    if args.list_presets:
        print("=" * 70)
        print("  Verified Timing Presets Available:")
        print("=" * 70)
        for sname, sdata in presets_db.items():
            print(f"  * {sname}:")
            print(f"      Offset  : {sdata.get('offset_seconds', 0.0)}s")
            print(f"      Loudness: {sdata.get('target_lufs', -24.3)} LUFS")
            print(f"      Info    : {sdata.get('description', '')}")
        return

    print("=" * 70)
    print("  Just Dance Greatest Hits (Xbox 360) - Song Replacement Toolkit")
    print("=" * 70)

    video_dir = resolve_game_dir(args)
    available_songs = get_installed_songs(video_dir)
    if not available_songs:
        raise ToolkitError(f"No WMV songs found in {video_dir}")

    if args.list:
        print(f"\n[*] Found {len(available_songs)} songs in the game:")
        for idx, s in enumerate(available_songs, 1):
            preset_mark = " [Verified Preset Available]" if s in presets_db else ""
            print(f"    {idx:2d}. {s}{preset_mark}")
        return

    song = choose_song(args, available_songs, presets_db, video_dir)
    print(f"\n[*] Selected song: {song}")

    if args.restore:
        print("\n[*] Restoring original files from backups...")
        restore_song(video_dir, song)
        print("    Done.")
        return

    check_tools()
    preset = presets_db.get(song, None)

    main_wmv = os.path.join(video_dir, f"{song}.wmv")
    source_wmv = main_wmv + ".bak" if os.path.isfile(main_wmv + ".bak") else main_wmv

    audio_path = args.audio
    while not audio_path or not os.path.isfile(audio_path):
        audio_path = ask(f"Enter path to your replacement audio file for '{song}' (FLAC/MP3/WAV, q to quit): ")
        if not os.path.isfile(audio_path):
            print("[!] Audio file not found. Please try again.")

    # Determine duration
    if preset and "main_video" in preset and "duration" in preset["main_video"]:
        dur_float = preset["main_video"]["duration"]
    else:
        dur_float = probe_duration(source_wmv)

    # Determine offset
    offset = args.offset
    if offset is not None:
        print(f"\n[*] Using user-specified offset: {offset:+.3f} seconds")
    elif preset and "offset_seconds" in preset:
        offset = preset["offset_seconds"]
        print(f"\n[OK] Using verified community preset offset for '{song}': {offset:+.3f} seconds ({offset*1000:+.1f} ms)")
    else:
        print("\n[*] Analyzing timing offset between in-game video and replacement audio...")
        offset = compute_timing_offset(source_wmv, audio_path)
        print(f"    Calculated offset: {offset:+.3f} seconds ({offset*1000:+.1f} ms)")

    # Determine LUFS
    if args.lufs is not None:
        target_lufs = args.lufs
    elif preset and "target_lufs" in preset:
        target_lufs = preset["target_lufs"]
    else:
        target_lufs = -24.3

    print("\n[*] Step 1: Backing up original game files...")
    backup_originals(video_dir, song)

    with tempfile.TemporaryDirectory(prefix=f"jd_{song}_") as work:
        print(f"\n[*] Step 2: Normalizing audio to {target_lufs} LUFS and applying {offset:+.3f}s offset...")
        norm_wav = os.path.join(work, "full_norm.wav")
        fade_at = preset.get("fade_out_seconds") if preset else None
        run_tool(build_norm_cmd(audio_path, offset, dur_float, target_lufs, fade_at, norm_wav))
        print("    Full normalized audio generated.")

        process_main(song, video_dir, source_wmv, norm_wav, work)
        process_clips(song, video_dir, preset, norm_wav, work)
        process_preview(song, video_dir, preset, norm_wav, work, args.radvideo)
        print("\n[*] Cleaning up temporary working files...")

    print("\n" + "=" * 70)
    print(f"  [SUCCESS] Song '{song}' has been successfully replaced!")
    print("=" * 70)


def main(argv=None):
    global VERBOSE
    args = parse_args(argv)
    VERBOSE = args.verbose
    try:
        run(args)
    except ToolkitError as e:
        print(f"\n[!] ERROR: {e}")
        sys.exit(1)
    except UserQuit:
        print("\n[*] Cancelled. No game files were changed by this step.")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n[*] Interrupted. Original files are safe in their .bak backups.")
        sys.exit(130)


if __name__ == "__main__":
    main()
