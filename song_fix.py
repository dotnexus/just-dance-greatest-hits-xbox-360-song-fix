#!/usr/bin/env python3
"""
Universal Song Audio Replacement Toolkit for Just Dance Greatest Hits (Xbox 360 - XEX Format)
Replaces in-game covers or tracks with original/uncensored studio versions.
Supports community-verified timing presets (presets.json) and automatic timing analysis.
"""

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

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
    }
}

def load_presets():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    preset_file = os.path.join(script_dir, "presets.json")
    presets = dict(BUILTIN_PRESETS)
    if os.path.isfile(preset_file):
        try:
            with open(preset_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "presets" in data and isinstance(data["presets"], dict):
                    presets.update(data["presets"])
        except Exception:
            pass
    return presets

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False

def find_radvideo():
    possible_paths = [
        r"C:\Program Files (x86)\RADVideo\radvideo64.exe",
        r"C:\Program Files\RADVideo\radvideo64.exe",
        r"C:\RADVideo\radvideo64.exe"
    ]
    for p in possible_paths:
        if os.path.isfile(p):
            return p
    return None

def mix_bink_auto(radvideo_exe, in_bik, in_wav, out_bik):
    cmd = [radvideo_exe, "binkmix", in_bik, in_wav, out_bik, "/o"]
    p = subprocess.Popen(cmd)
    time.sleep(1.5)

    user32 = ctypes.windll.user32
    hwnds = []

    def enum_win(hwnd, extra):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == p.pid:
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            hwnds.append((hwnd, buff.value))
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(EnumWindowsProc(enum_win), 0)

    for hwnd, title in hwnds:
        children = []
        def enum_child(chwnd, extra):
            length = user32.GetWindowTextLengthW(chwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(chwnd, buff, length + 1)
            children.append((chwnd, buff.value))
            return True
        EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumChildWindows(hwnd, EnumChildProc(enum_child), 0)
        for chwnd, ctext in children:
            if "mix" in ctext.lower() or "done" in ctext.lower():
                user32.SendMessageW(chwnd, 0x00F5, 0, 0)

    time.sleep(2)
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    return os.path.isfile(out_bik)

def get_installed_songs(video_dir):
    if not os.path.isdir(video_dir):
        return []
    songs = []
    for f in os.listdir(video_dir):
        if f.lower().endswith(".wmv") and not f.lower().endswith("_a.wmv") and not f.lower().endswith("_b.wmv") and not f.lower().endswith(".bak"):
            songs.append(f[:-4])
    return sorted(songs)

def compute_timing_offset(ref_video, new_audio, start_sec=10.0, dur_sec=35.0):
    try:
        import librosa
        import numpy as np
        from scipy import signal
    except ImportError:
        print("[!] Note: 'librosa'/'scipy' not found. Using default offset = 0.0s.")
        print("    Install them with: pip install librosa scipy numpy to enable automatic offset detection.")
        return 0.0

    t_dir = tempfile.gettempdir()
    t_orig = os.path.join(t_dir, "jd_align_ref.wav")
    t_new = os.path.join(t_dir, "jd_align_new.wav")

    try:
        subprocess.run(["ffmpeg", "-y", "-ss", str(start_sec), "-i", ref_video, "-t", str(dur_sec), "-vn", "-ar", "22050", "-ac", "1", t_orig], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["ffmpeg", "-y", "-ss", str(start_sec), "-i", new_audio, "-t", str(dur_sec), "-vn", "-ar", "22050", "-ac", "1", t_new], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        sr = 22050
        yo, _ = librosa.load(t_orig, sr=sr)
        yn, _ = librosa.load(t_new, sr=sr)

        env_o = librosa.onset.onset_strength(y=yo, sr=sr)
        env_n = librosa.onset.onset_strength(y=yn, sr=sr)

        corr = signal.correlate(env_n, env_o, mode="full")
        lags = signal.correlation_lags(len(env_n), len(env_o), mode="full")
        best_lag = lags[np.argmax(corr)]
        offset_sec = (best_lag * 512) / sr
        return offset_sec
    except Exception as e:
        print(f"[!] Warning: Auto-detection failed ({e}). Defaulting offset to 0.0s.")
        return 0.0
    finally:
        for f in [t_orig, t_new]:
            if os.path.isfile(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

def main():
    parser = argparse.ArgumentParser(description="Universal Song Replacement Toolkit for Just Dance Greatest Hits (Xbox 360 XEX).")
    parser.add_argument("-g", "--game-dir", help="Path to Just Dance Greatest Hits directory (extracted XEX format)")
    parser.add_argument("-s", "--song", help="Song codename to replace (e.g. BarbieGirl, etc.)")
    parser.add_argument("-a", "--audio", help="Path to replacement audio file (FLAC, WAV, MP3, etc.)")
    parser.add_argument("-o", "--offset", type=float, help="Manual offset in seconds to trim from replacement audio (optional)")
    parser.add_argument("-l", "--lufs", type=float, default=None, help="Target integrated loudness in LUFS (defaults to preset or -24.3)")
    parser.add_argument("--list", action="store_true", help="List all detected songs in the game folder and exit")
    parser.add_argument("--list-presets", action="store_true", help="List all verified timing presets available and exit")
    args = parser.parse_args()

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

    if not check_ffmpeg():
        print("[!] ERROR: 'ffmpeg' was not found in PATH.")
        print("    Please install FFmpeg and make sure it is added to your PATH environment variable.")
        sys.exit(1)

    game_dir = args.game_dir
    while not game_dir or not os.path.isdir(game_dir):
        game_dir = input("\nEnter path to Just Dance Greatest Hits game directory: ").strip().strip('"')
        if not os.path.isdir(game_dir):
            print("[!] Invalid directory. Please try again.")

    video_dir = os.path.join(game_dir, "videos")
    if not os.path.isdir(video_dir):
        print(f"[!] ERROR: 'videos' folder not found inside {game_dir}")
        print("    Make sure the game is in extracted XEX format, not GOD (Games on Demand).")
        sys.exit(1)

    available_songs = get_installed_songs(video_dir)
    if not available_songs:
        print(f"[!] No WMV songs found in {video_dir}")
        sys.exit(1)

    if args.list:
        print(f"\n[*] Found {len(available_songs)} songs in the game:")
        for idx, s in enumerate(available_songs, 1):
            preset_mark = " [Verified Preset Available]" if s in presets_db else ""
            print(f"    {idx:2d}. {s}{preset_mark}")
        return

    song = args.song
    while not song or song not in available_songs:
        if not song:
            print(f"\n[*] Detected {len(available_songs)} songs in game directory:")
            for idx, s in enumerate(available_songs, 1):
                preset_mark = " *" if s in presets_db else ""
                print(f"    [{idx:2d}] {s}{preset_mark}")
            if any(s in presets_db for s in available_songs):
                print("    (* = Verified timing preset included)")
            choice = input("\nSelect song number or enter exact codename: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(available_songs):
                song = available_songs[int(choice) - 1]
            elif choice in available_songs:
                song = choice
            else:
                print("[!] Invalid choice. Please try again.")
        else:
            print(f"[!] Song '{song}' not found in {video_dir}.")
            song = None

    print(f"\n[*] Selected song: {song}")
    preset = presets_db.get(song, None)

    main_wmv = os.path.join(video_dir, f"{song}.wmv")
    source_wmv = main_wmv + ".bak" if os.path.isfile(main_wmv + ".bak") else main_wmv

    audio_path = args.audio
    while not audio_path or not os.path.isfile(audio_path):
        audio_path = input(f"Enter path to your replacement audio file for '{song}' (FLAC/MP3/WAV): ").strip().strip('"')
        if not os.path.isfile(audio_path):
            print("[!] Audio file not found. Please try again.")

    # Determine duration
    if preset and "main_video" in preset and "duration" in preset["main_video"]:
        dur_float = preset["main_video"]["duration"]
    else:
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", source_wmv], capture_output=True, text=True)
        try:
            dur_float = float(probe.stdout.strip())
        except Exception:
            dur_float = 200.0

    # Determine offset
    offset = args.offset
    if offset is not None:
        print(f"\n[*] Using user-specified offset: {offset:+.3f} seconds")
    elif preset and "offset_seconds" in preset:
        offset = preset["offset_seconds"]
        print(f"\n[✓] Using verified community preset offset for '{song}': {offset:+.3f} seconds ({offset*1000:+.1f} ms)")
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

    temp_dir = os.path.join(game_dir, f"_temp_replace_{song}")
    os.makedirs(temp_dir, exist_ok=True)

    print("\n[*] Step 1: Backing up original game files...")
    targets = [f"{song}.wmv", f"{song}_A.wmv", f"{song}_B.wmv", f"{song}_Preview.bik"]
    for fname in targets:
        src = os.path.join(video_dir, fname)
        bak = src + ".bak"
        if os.path.isfile(src) and not os.path.isfile(bak):
            shutil.copy2(src, bak)
            print(f"    Backed up: {fname} -> {fname}.bak")
        elif os.path.isfile(bak):
            print(f"    Backup already exists: {fname}.bak")

    print(f"\n[*] Step 2: Normalizing audio to {target_lufs} LUFS and applying {offset:+.3f}s offset...")
    norm_wav = os.path.join(temp_dir, "full_norm.wav")
    cmd_norm = ["ffmpeg", "-y"]
    if offset > 0:
        cmd_norm += ["-ss", str(offset)]
    cmd_norm += [
        "-i", audio_path,
        "-t", str(dur_float),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=7",
        "-ar", "48000",
        "-ac", "2",
        norm_wav
    ]
    subprocess.run(cmd_norm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("    Full normalized audio generated.")

    print(f"\n[*] Step 3: Remuxing main song video ({song}.wmv)...")
    temp_main_wmv = os.path.join(temp_dir, f"{song}.wmv")
    cmd_main = [
        "ffmpeg", "-y",
        "-i", source_wmv,
        "-i", norm_wav,
        "-map", "1:a:0",
        "-map", "0:v:0",
        "-c:v", "copy",
        "-c:a", "wmav2",
        "-b:a", "192k",
        temp_main_wmv
    ]
    subprocess.run(cmd_main, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    shutil.copy2(temp_main_wmv, main_wmv)
    print(f"    {song}.wmv updated successfully.")

    # Sub-clips A and B
    for sub in ["A", "B"]:
        sub_name = f"{song}_{sub}.wmv"
        sub_path = os.path.join(video_dir, sub_name)
        source_sub = sub_path + ".bak" if os.path.isfile(sub_path + ".bak") else sub_path
        if os.path.isfile(source_sub):
            print(f"\n[*] Step 4{sub}: Processing Mashup Clip {sub} ({sub_name})...")
            clip_key = f"clip_{sub.lower()}"
            if preset and clip_key in preset:
                sub_start = preset[clip_key].get("start_offset", 0.0)
                sub_dur = preset[clip_key].get("duration", 40.0)
            else:
                probe_sub = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", source_sub], capture_output=True, text=True)
                try:
                    sub_dur = float(probe_sub.stdout.strip())
                except Exception:
                    sub_dur = 40.0
                sub_start = 0.0

            sub_wav = os.path.join(temp_dir, f"clip_{sub}.wav")
            subprocess.run(["ffmpeg", "-y", "-ss", str(sub_start), "-i", norm_wav, "-t", str(sub_dur), sub_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            temp_sub_wmv = os.path.join(temp_dir, sub_name)
            subprocess.run(["ffmpeg", "-y", "-i", source_sub, "-i", sub_wav, "-map", "1:a:0", "-map", "0:v:0", "-c:v", "copy", "-c:a", "wmav2", "-b:a", "192k", temp_sub_wmv], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            shutil.copy2(temp_sub_wmv, sub_path)
            print(f"    {sub_name} updated successfully.")

    # Preview clip
    preview_name = f"{song}_Preview.bik"
    preview_path = os.path.join(video_dir, preview_name)
    source_preview = preview_path + ".bak" if os.path.isfile(preview_path + ".bak") else preview_path
    if os.path.isfile(source_preview):
        print(f"\n[*] Step 5: Processing Menu Preview ({preview_name})...")
        if preset and "preview" in preset:
            prev_start = preset["preview"].get("start_offset", 40.0)
            prev_dur = preset["preview"].get("duration", 8.37)
        else:
            probe_prev = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", source_preview], capture_output=True, text=True)
            try:
                prev_dur = float(probe_prev.stdout.strip())
            except Exception:
                prev_dur = 8.37
            prev_start = 40.0

        preview_wav = os.path.join(temp_dir, "preview_norm.wav")
        subprocess.run(["ffmpeg", "-y", "-ss", str(prev_start), "-i", norm_wav, "-t", str(prev_dur), "-ar", "44100", "-ac", "2", preview_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        radvideo_exe = find_radvideo()
        if radvideo_exe:
            print(f"    RAD Video Tools detected at: {radvideo_exe}")
            temp_bik = os.path.join(temp_dir, preview_name)
            if mix_bink_auto(radvideo_exe, source_preview, preview_wav, temp_bik):
                shutil.copy2(temp_bik, preview_path)
                print(f"    {preview_name} updated successfully.")
            else:
                print(f"    [!] Could not auto-mix Bink video. Exported preview audio as '{song}_preview.wav'.")
                shutil.copy2(preview_wav, os.path.join(video_dir, f"{song}_preview.wav"))
        else:
            export_prev = os.path.join(video_dir, f"{song}_preview.wav")
            shutil.copy2(preview_wav, export_prev)
            print(f"    [i] RAD Video Tools not detected. Exported audio as '{song}_preview.wav'.")

    print("\n[*] Cleaning up temporary working files...")
    shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n" + "=" * 70)
    print(f"  [SUCCESS] Song '{song}' has been successfully replaced!")
    print("=" * 70)

if __name__ == "__main__":
    main()
