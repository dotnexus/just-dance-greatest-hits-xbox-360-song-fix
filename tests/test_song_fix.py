import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import song_fix  # noqa: E402


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def make_wav(path, pcm, with_list_chunk=True, rate=48000, channels=2, bits=16):
    fmt = struct.pack('<HHIIHH', 1, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits)
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt
    if with_list_chunk:
        info = b'INFOISFT' + struct.pack('<I', 14) + b'Lavf62.3.100\x00\x00'
        chunks += b'LIST' + struct.pack('<I', len(info)) + info
    chunks += b'data' + struct.pack('<I', len(pcm)) + pcm
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 4 + len(chunks)) + b'WAVE' + chunks)


class PresetValidation(unittest.TestCase):
    def test_valid_preset(self):
        preset = {"offset_seconds": 0.75, "target_lufs": -24.3, "main_video": {"duration": 196.6},
                  "clip_a": {"start_offset": 41.4, "duration": 41.0}}
        self.assertEqual(song_fix.validate_preset("BarbieGirl", preset), [])

    def test_rejects_bad_values(self):
        self.assertTrue(song_fix.validate_preset("X", {"offset_seconds": 99}))
        self.assertTrue(song_fix.validate_preset("X", {"main_video": {"duration": -5}}))
        self.assertTrue(song_fix.validate_preset("X", {"clip_a": {"duration": "40"}}))
        self.assertTrue(song_fix.validate_preset("X", {"target_lufs": True}))

    def test_rejects_unsafe_name(self):
        self.assertTrue(song_fix.validate_preset("../evil", {}))
        self.assertTrue(song_fix.validate_preset("a b", {}))

    def test_shipped_presets_are_valid(self):
        import json
        with open(os.path.join(ROOT, "presets.json"), encoding="utf-8") as f:
            data = json.load(f)
        for name, preset in data["presets"].items():
            self.assertEqual(song_fix.validate_preset(name, preset), [], name)


class NormalizeCommand(unittest.TestCase):
    def test_positive_offset_trims_start(self):
        cmd = song_fix.build_norm_cmd("in.flac", 0.75, 196.642, -24.3, None, "out.wav")
        self.assertIn("-ss", cmd)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "0.75")
        self.assertNotIn("adelay", cmd[cmd.index("-af") + 1])

    def test_negative_offset_pads_silence(self):
        cmd = song_fix.build_norm_cmd("in.flac", -0.25, 100, -24.3, None, "out.wav")
        self.assertNotIn("-ss", cmd)
        self.assertTrue(cmd[cmd.index("-af") + 1].startswith("adelay=250|250,"))

    def test_fade_only_when_inside_duration(self):
        with_fade = song_fix.build_norm_cmd("in.flac", 0, 210, -24.3, 206.2, "out.wav")
        self.assertIn("afade=t=out:st=205.50:d=0.7", with_fade[with_fade.index("-af") + 1])
        no_fade = song_fix.build_norm_cmd("in.flac", 0, 100, -24.3, 206.2, "out.wav")
        self.assertNotIn("afade", no_fade[no_fade.index("-af") + 1])


class FileSafety(unittest.TestCase):
    def test_atomic_copy_replaces_and_leaves_no_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "src.bin"), os.path.join(d, "dst.bin")
            write_bytes(src, b"new data")
            write_bytes(dst, b"old")
            song_fix.atomic_copy(src, dst)
            self.assertEqual(read_bytes(dst), b"new data")
            self.assertFalse(os.path.exists(dst + ".tmp"))

    def test_restore_song_puts_backups_back(self):
        with tempfile.TemporaryDirectory() as d:
            write_bytes(os.path.join(d, "Song.wmv"), b"patched")
            write_bytes(os.path.join(d, "Song.wmv.bak"), b"original")
            write_bytes(os.path.join(d, "Song_preview.wav"), b"x")
            song_fix.restore_song(d, "Song")
            self.assertEqual(read_bytes(os.path.join(d, "Song.wmv")), b"original")
            self.assertFalse(os.path.exists(os.path.join(d, "Song_preview.wav")))

    def test_restore_without_backups_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(song_fix.ToolkitError):
                song_fix.restore_song(d, "Nothing")


@unittest.skipUnless(sys.platform == "win32", "the injector module needs Windows")
class WavReader(unittest.TestCase):
    def setUp(self):
        import wma_pro_injector
        self.read = wma_pro_injector.read_wav_pcm

    def test_skips_list_chunk(self):
        pcm = bytes(range(256)) * 4
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.wav")
            make_wav(path, pcm, with_list_chunk=True)
            self.assertEqual(self.read(path), pcm)

    def test_canonical_header(self):
        pcm = bytes(range(200)) * 2
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.wav")
            make_wav(path, pcm, with_list_chunk=False)
            self.assertEqual(self.read(path), pcm)

    def test_rejects_wrong_format(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.wav")
            make_wav(path, b"\x00" * 400, rate=44100)
            with self.assertRaises(ValueError):
                self.read(path)


class CommandLine(unittest.TestCase):
    def test_no_stdin_exits_cleanly_without_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "videos"))
            write_bytes(os.path.join(d, "videos", "Song.wmv"), b"x")
            result = subprocess.run([sys.executable, os.path.join(ROOT, "song_fix.py"), "-g", d],
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
