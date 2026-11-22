#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/asset_checks.py.

Every PNG and WAV here is made inside the test (a small encoder, the wave module); no
binary fixture is committed. The measurements are the free checks create-it leans on
before any reviewer looks at an asset, so each one is pinned against a file whose
answer is known by construction, including the filters, bit depths and colour types a
real sprite export uses, and the path where a tool is missing.

stdlib only.
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "src" / "development-lifecycle" / "scripts" / "asset_checks.py"


def _load():
    spec = importlib.util.spec_from_file_location("asset_checks", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["asset_checks"] = m
    spec.loader.exec_module(m)
    return m


ac = _load()


# ------------------------------------------------------------------ PNG encoder

def _chunk(ctype: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + ctype + body + struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)


def _pack(samples, depth):
    if depth == 8:
        return bytes(samples)
    if depth == 16:
        return b"".join(struct.pack(">H", v) for v in samples)
    per = 8 // depth
    out = bytearray()
    for i in range(0, len(samples), per):
        byte = 0
        group = samples[i:i + per]
        for j, v in enumerate(group):
            byte |= v << (8 - depth * (j + 1))
        out.append(byte)
    return bytes(out)


def _filter(line: bytes, prev: bytes, ftype: int, bpp: int) -> bytes:
    out = bytearray(len(line))
    for i, x in enumerate(line):
        a = line[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        if ftype == 0:
            pred = 0
        elif ftype == 1:
            pred = a
        elif ftype == 2:
            pred = b
        elif ftype == 3:
            pred = (a + b) >> 1
        else:
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
        out[i] = (x - pred) & 255
    return bytes(out)


def png_bytes(width, height, rows, ctype=6, depth=8, ftype=0, plte=None, trns=None, actl=None, interlace=0):
    """`rows` is a list of per-row sample lists (channels interleaved)."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, channels * depth // 8)
    raw = bytearray()
    prev = None
    for samples in rows:
        line = _pack(samples, depth)
        prev = prev if prev is not None else bytes(len(line))
        ft = ftype if ftype < 5 else (rows.index(samples) % 5)
        raw.append(ft)
        raw += _filter(line, prev, ft, bpp)
        prev = line
    data = ac.PNG_SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, ctype, 0, 0, interlace))
    if actl is not None:
        data += _chunk(b"acTL", struct.pack(">II", actl, 0))
    if plte is not None:
        data += _chunk(b"PLTE", bytes(v for c in plte for v in c))
    if trns is not None:
        data += _chunk(b"tRNS", trns)
    data += _chunk(b"IDAT", zlib.compress(bytes(raw))) + _chunk(b"IEND", b"")
    return data


def rgba_rows(pixels):
    """pixels: list of rows of (r,g,b,a)."""
    return [[v for px in row for v in px] for row in pixels]


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def png(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return str(p)


RED, GREEN, BLUE, CLEAR = (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (0, 0, 0, 0)


class PngDecodeTests(TmpCase):
    def test_every_filter_type_decodes_to_the_same_pixels(self):
        pixels = [[RED, GREEN, BLUE, (9, 8, 7, 255)], [BLUE, (1, 2, 3, 128), RED, GREEN],
                  [(10, 20, 30, 255), (40, 50, 60, 255), (70, 80, 90, 255), (100, 110, 120, 255)],
                  [GREEN, GREEN, RED, BLUE], [RED, BLUE, GREEN, CLEAR]]
        want = sorted({c for row in pixels for c in row})
        for ftype in range(6):  # 5 = a different filter on each row
            with self.subTest(filter=ftype):
                path = self.png("f%d.png" % ftype, png_bytes(4, 5, rgba_rows(pixels), ftype=ftype))
                self.assertEqual(ac.png_metrics(path)["palette"], want)

    def test_size_is_read(self):
        path = self.png("a.png", png_bytes(3, 2, rgba_rows([[RED] * 3, [BLUE] * 3])))
        m = ac.png_metrics(path)
        self.assertEqual((m["width"], m["height"]), (3, 2))

    def test_grayscale_and_gray_alpha_and_rgb(self):
        g = ac.png_metrics(self.png("g.png", png_bytes(2, 1, [[0, 200]], ctype=0)))
        self.assertEqual(g["palette"], [(0, 0, 0, 255), (200, 200, 200, 255)])
        ga = ac.png_metrics(self.png("ga.png", png_bytes(2, 1, [[50, 255, 50, 0]], ctype=4)))
        self.assertEqual(ga["palette"], [(50, 50, 50, 0), (50, 50, 50, 255)])
        rgb = ac.png_metrics(self.png("rgb.png", png_bytes(2, 1, [[1, 2, 3, 4, 5, 6]], ctype=2)))
        self.assertEqual(rgb["palette"], [(1, 2, 3, 255), (4, 5, 6, 255)])

    def test_palette_png_with_transparency(self):
        data = png_bytes(3, 1, [[0, 1, 2]], ctype=3, plte=[(255, 0, 0), (0, 255, 0), (0, 0, 255)],
                         trns=bytes([255, 0]))
        m = ac.png_metrics(self.png("p.png", data))
        self.assertEqual(m["palette"], [(0, 0, 255, 255), (0, 255, 0, 0), (255, 0, 0, 255)])

    def test_two_bit_palette_and_one_bit_gray_unpack_correctly(self):
        pal = [(10, 0, 0), (20, 0, 0), (30, 0, 0), (40, 0, 0)]
        m = ac.png_metrics(self.png("p2.png", png_bytes(5, 1, [[0, 1, 2, 3, 1]], ctype=3, depth=2, plte=pal)))
        self.assertEqual({c[0] for c in m["palette"]}, {10, 20, 30, 40})
        g = ac.png_metrics(self.png("g1.png", png_bytes(9, 1, [[1, 0, 1, 0, 1, 0, 1, 0, 1]], ctype=0, depth=1)))
        self.assertEqual(g["palette"], [(0, 0, 0, 255), (255, 255, 255, 255)])

    def test_sixteen_bit_samples_scale_to_eight(self):
        m = ac.png_metrics(self.png("s.png", png_bytes(1, 1, [[65535, 0, 32768, 65535]], ctype=6, depth=16)))
        self.assertEqual(m["palette"], [(255, 0, 127, 255)])

    def test_gray_transparent_colour_chunk(self):
        data = png_bytes(2, 1, [[7, 9]], ctype=0, trns=struct.pack(">H", 7))
        self.assertEqual(ac.png_metrics(self.png("t.png", data))["palette"],
                         [(7, 7, 7, 0), (9, 9, 9, 255)])

    def test_interlaced_png_is_measured_for_size_and_says_the_rest_was_skipped(self):
        m = ac.png_metrics(self.png("i.png", png_bytes(4, 4, rgba_rows([[RED] * 4] * 4), interlace=1)))
        self.assertEqual((m["width"], m["height"]), (4, 4))
        self.assertIsNone(m["palette"])
        self.assertTrue(any("interlaced" in s for s in m["skipped"]))

    def test_a_png_over_the_pixel_ceiling_is_not_decoded_and_says_so(self):
        old = ac.MAX_PIXELS
        ac.MAX_PIXELS = 3
        self.addCleanup(setattr, ac, "MAX_PIXELS", old)
        m = ac.png_metrics(self.png("big.png", png_bytes(2, 2, rgba_rows([[RED] * 2] * 2))))
        self.assertIsNone(m["palette"])
        self.assertTrue(any("pixels" in s for s in m["skipped"]))

    def test_malformed_files_are_refused(self):
        good = png_bytes(2, 2, rgba_rows([[RED] * 2] * 2))
        for name, data in (("sig.png", b"GIF89a" + b"\0" * 40), ("trunc.png", good[:30]),
                           ("empty.png", b""), ("badzlib.png", good.replace(b"IDAT", b"IDAT", 1)[:-30] + b"\0" * 18 + good[-12:])):
            with self.subTest(case=name):
                with self.assertRaises(ac.AssetError):
                    ac.png_metrics(self.png(name, data))
        with self.assertRaises(ac.AssetError):
            ac.png_metrics(str(self.dir / "missing.png"))


class FrameTests(TmpCase):
    def sheet(self):
        # 4x2 image cut into 2x1 frames of 2x2: frame 0 painted, frame 1 empty.
        return self.png("sheet.png", png_bytes(4, 2, rgba_rows([[RED, BLUE, CLEAR, CLEAR]] * 2)))

    def test_a_plain_png_is_one_frame(self):
        m = ac.png_metrics(self.sheet())
        self.assertEqual((m["frames"], m["frames_from"]), (1, "single image"))

    def test_apng_frame_count_comes_from_the_file(self):
        data = png_bytes(2, 2, rgba_rows([[RED] * 2] * 2), actl=6)
        m = ac.png_metrics(self.png("a.png", data))
        self.assertEqual((m["frames"], m["frames_from"]), (6, "APNG"))
        self.assertTrue(any("APNG" in s for s in m["skipped"]))

    def test_grid_gives_frames_and_counts_the_empty_ones(self):
        m = ac.png_metrics(self.sheet(), grid="2x1")
        self.assertEqual((m["frames"], m["empty_frames"]), (2, 1))
        self.assertIn("2x1 of 2x2", m["frames_from"])

    def test_frame_size_gives_the_same_answer_as_the_grid(self):
        a = ac.png_metrics(self.sheet(), grid="2x1")
        b = ac.png_metrics(self.sheet(), frame_size="2x2")
        self.assertEqual((a["frames"], a["empty_frames"]), (b["frames"], b["empty_frames"]))

    def test_a_sheet_that_does_not_cut_evenly_is_refused(self):
        with self.assertRaises(ac.AssetError):
            ac.png_metrics(self.sheet(), grid="3x1")
        with self.assertRaises(ac.AssetError):
            ac.png_metrics(self.sheet(), frame_size="3x2")

    def test_a_malformed_grid_is_refused(self):
        for bad in ("2", "2x", "0x1", "axb", "2*1"):
            with self.assertRaises(ac.AssetError, msg=bad):
                ac.png_metrics(self.sheet(), grid=bad)


class PngCompareTests(TmpCase):
    def make(self, name, colours, w=2, h=1):
        return self.png(name, png_bytes(w, h, rgba_rows([colours]), ctype=6))

    def test_identical_files_have_no_difference(self):
        a = ac.check(self.make("a.png", [RED, BLUE]), self.make("r.png", [RED, BLUE]))
        self.assertEqual(a["differences"], [])

    def test_new_and_missing_colours_are_named(self):
        r = ac.check(self.make("a.png", [RED, GREEN]), self.make("r.png", [RED, BLUE]))
        text = "\n".join(r["differences"])
        self.assertIn("1 new colour(s) not in the reference: #00ff00", text)
        self.assertIn("1 reference colour(s) missing from the made file: #0000ff", text)

    def test_a_size_mismatch_is_named(self):
        r = ac.check(self.make("a.png", [RED, RED], 2, 1), self.make("r.png", [RED], 1, 1))
        self.assertIn("size mismatch: made 2x1, reference 1x1", r["differences"][0])

    def test_a_frame_count_mismatch_is_named(self):
        a = self.png("a.png", png_bytes(2, 2, rgba_rows([[RED] * 2] * 2), actl=4))
        b = self.png("b.png", png_bytes(2, 2, rgba_rows([[RED] * 2] * 2), actl=8))
        self.assertIn("frame count mismatch: made 4, reference 8", ac.check(a, b)["differences"][0])

    def test_long_colour_lists_are_cut_with_an_ellipsis(self):
        many = [(i, 0, 0, 255) for i in range(20)]
        r = ac.check(self.make("a.png", many, 20, 1), self.make("r.png", [BLUE] * 20, 20, 1))
        self.assertIn("20 new colour(s)", "\n".join(r["differences"]))
        self.assertIn("...", "\n".join(r["differences"]))

    def test_without_a_reference_there_is_nothing_to_differ_from(self):
        r = ac.check(self.make("a.png", [RED, BLUE]))
        self.assertEqual(r["differences"], [])
        self.assertEqual(len(r["metrics"]["palette"]), 2)


# ------------------------------------------------------------------------- WAV

def write_wav(path, samples, rate=8000, channels=1, width=2):
    """samples: floats in [-1, 1], interleaved when stereo."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        body = bytearray()
        for v in samples:
            if width == 1:
                body.append(int(round(v * 127)) + 128)
            elif width == 2:
                body += struct.pack("<h", int(round(v * 32767)))
            elif width == 3:
                body += int(round(v * 8388607)).to_bytes(3, "little", signed=True)
            else:
                body += struct.pack("<i", int(round(v * (2 ** 31 - 1))))
        w.writeframes(bytes(body))


def sine(n, amp=0.5, cycles=50):
    return [amp * math.sin(2 * math.pi * cycles * i / n) for i in range(n)]


class WavTests(TmpCase):
    def test_length_rate_channels_peak_and_rms(self):
        p = self.dir / "a.wav"
        write_wav(p, sine(4000, 0.5), rate=8000)
        m = ac.wav_metrics(str(p))
        self.assertEqual((m["sample_rate"], m["channels"], m["length_s"]), (8000, 1, 0.5))
        self.assertAlmostEqual(m["peak_dbfs"], -6.02, delta=0.05)
        self.assertAlmostEqual(m["rms_dbfs"], -9.03, delta=0.05)  # 0.5 / sqrt(2)

    def test_every_integer_width_agrees(self):
        wave_samples = sine(2000, 0.25)
        levels = []
        for width in (1, 2, 3, 4):
            p = self.dir / ("w%d.wav" % width)
            write_wav(p, wave_samples, width=width)
            levels.append(ac.wav_metrics(str(p))["peak_dbfs"])
        for lv in levels:
            self.assertAlmostEqual(lv, -12.04, delta=0.2)

    def test_stereo_channel_count_and_length_use_frames_not_samples(self):
        p = self.dir / "s.wav"
        write_wav(p, sine(8000, 0.5), rate=8000, channels=2)
        m = ac.wav_metrics(str(p))
        self.assertEqual((m["channels"], m["length_s"]), (2, 0.5))

    def test_silence_has_no_level(self):
        p = self.dir / "z.wav"
        write_wav(p, [0.0] * 800)
        m = ac.wav_metrics(str(p))
        self.assertIsNone(m["peak_dbfs"])
        self.assertIsNone(m["rms_dbfs"])

    def test_a_float_wav_is_reported_as_not_measured_not_as_a_crash(self):
        p = self.dir / "f.wav"
        n = 100
        body = struct.pack("<%df" % n, *([0.1] * n))
        fmt = struct.pack("<HHIIHH", 3, 1, 8000, 32000, 4, 32)
        data = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(body)) + body
        p.write_bytes(b"RIFF" + struct.pack("<I", len(data)) + data)
        m = ac.wav_metrics(str(p))
        self.assertFalse(m["measured"])
        self.assertTrue(any("not measured" in s for s in m["skipped"]))

    def test_a_file_that_is_not_a_wav_is_refused(self):
        p = self.dir / "x.wav"
        p.write_bytes(b"not a wav at all")
        with self.assertRaises(ac.AssetError):
            ac.wav_metrics(str(p))

    def test_compare_flags_each_kind_of_difference(self):
        ref = self.dir / "r.wav"
        write_wav(ref, sine(4000, 0.5), rate=8000)
        cases = {
            "rate": ({"rate": 16000, "n": 8000, "amp": 0.5}, "sample rate mismatch"),
            "length": ({"rate": 8000, "n": 2000, "amp": 0.5}, "length differs"),
            "level": ({"rate": 8000, "n": 4000, "amp": 0.05}, "peak level differs"),
        }
        for name, (kw, expect) in cases.items():
            made = self.dir / (name + ".wav")
            write_wav(made, sine(kw["n"], kw["amp"]), rate=kw["rate"])
            r = ac.check(str(made), str(ref))
            self.assertIn(expect, "\n".join(r["differences"]), name)
        stereo = self.dir / "st.wav"
        write_wav(stereo, sine(8000, 0.5), rate=8000, channels=2)
        self.assertIn("channel count mismatch", "\n".join(ac.check(str(stereo), str(ref))["differences"]))

    def test_compare_passes_inside_the_tolerances(self):
        ref, made = self.dir / "r.wav", self.dir / "m.wav"
        write_wav(ref, sine(4000, 0.5))
        write_wav(made, sine(4100, 0.45))  # 2.5% longer, about -0.9 dB
        self.assertEqual(ac.check(str(made), str(ref))["differences"], [])

    def test_the_tolerances_are_arguments(self):
        ref, made = self.dir / "r.wav", self.dir / "m.wav"
        write_wav(ref, sine(4000, 0.5))
        write_wav(made, sine(4100, 0.45))
        tight = ac.check(str(made), str(ref), length_tolerance=0.01, level_tolerance_db=0.5)
        self.assertEqual(len(tight["differences"]), 3)

    def test_silence_against_sound_is_a_difference(self):
        ref, made = self.dir / "r.wav", self.dir / "m.wav"
        write_wav(ref, sine(4000, 0.5))
        write_wav(made, [0.0] * 4000)
        self.assertIn("one is silent", "\n".join(ac.check(str(made), str(ref))["differences"]))

    def test_grid_does_not_apply_to_a_wav(self):
        p = self.dir / "a.wav"
        write_wav(p, sine(800))
        with self.assertRaises(ac.AssetError):
            ac.check(str(p), grid="2x1")


# ---------------------------------------------------------------- optional tools

class FakeRun:
    """Stands in for subprocess.run; writes the output file the command names."""

    def __init__(self, returncode=0, write=True, stderr=""):
        self.calls, self.returncode, self.write, self.stderr = [], returncode, write, stderr

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if self.write and self.returncode == 0:
            Path(cmd[-1]).write_bytes(b"png")
        return subprocess.CompletedProcess(cmd, self.returncode, "", self.stderr)


class ToolTests(TmpCase):
    def setUp(self):
        super().setUp()
        self.a = self.png("a.png", png_bytes(2, 1, rgba_rows([[RED, BLUE]])))
        self.r = self.png("r.png", png_bytes(2, 1, rgba_rows([[RED, BLUE]])))
        self.w = self.dir / "a.wav"
        write_wav(self.w, sine(800))
        self.out = str(self.dir / "out")

    def test_no_tool_installed_says_so_for_both_images(self):
        r = ac.check(self.a, self.r, self.out, which=lambda n: None)
        self.assertEqual(r["artifacts"], [])
        self.assertTrue(any("neither ImageMagick" in s for s in r["skipped"]))
        w = ac.check(str(self.w), str(self.w), self.out, which=lambda n: None)
        self.assertEqual(w["artifacts"], [])
        self.assertEqual(sum("spectrogram skipped: ffmpeg is not installed" in s for s in w["skipped"]), 2)

    def test_a_missing_tool_does_not_change_the_measurements_or_the_exit_code(self):
        bare = ac.check(self.a, self.r, which=lambda n: None)
        withdir = ac.check(self.a, self.r, self.out, which=lambda n: None)
        self.assertEqual(bare["differences"], withdir["differences"])
        self.assertEqual(bare["metrics"], withdir["metrics"])

    def test_imagemagick_is_preferred_and_gets_append_args(self):
        run = FakeRun()
        r = ac.check(self.a, self.r, self.out, which=lambda n: "/bin/" + n if n in ("magick", "ffmpeg") else None, runner=run)
        self.assertEqual(len(r["artifacts"]), 1)
        self.assertIn("+append", run.calls[0])
        self.assertTrue(run.calls[0][0].endswith("magick"))
        self.assertEqual(run.calls[0][1:3], [self.r, self.a], "reference goes on the left")

    def test_ffmpeg_alone_makes_the_side_by_side_with_hstack(self):
        run = FakeRun()
        ac.check(self.a, self.r, self.out, which=lambda n: "/bin/ffmpeg" if n == "ffmpeg" else None, runner=run)
        self.assertIn("hstack=inputs=2", run.calls[0])

    def test_a_tool_that_fails_is_reported_with_its_error_not_swallowed(self):
        run = FakeRun(returncode=1, stderr="Invalid size\nboom")
        r = ac.check(self.a, self.r, self.out, which=lambda n: "/bin/ffmpeg", runner=run)
        self.assertEqual(r["artifacts"], [])
        self.assertTrue(any("exited 1: boom" in s for s in r["skipped"]), r["skipped"])

    def test_spectrograms_are_written_for_made_and_reference(self):
        run = FakeRun()
        r = ac.check(str(self.w), str(self.w), self.out, which=lambda n: "/bin/ffmpeg", runner=run)
        self.assertEqual(len(r["artifacts"]), 2)
        self.assertTrue(all("showspectrumpic" in c for call in run.calls for c in [" ".join(call)]))

    def test_no_out_dir_means_no_tool_is_called(self):
        run = FakeRun()
        ac.check(self.a, self.r, which=lambda n: "/bin/magick", runner=run)
        self.assertEqual(run.calls, [])

    def test_a_png_with_no_reference_has_no_side_by_side(self):
        run = FakeRun()
        ac.check(self.a, None, self.out, which=lambda n: "/bin/magick", runner=run)
        self.assertEqual(run.calls, [])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_a_real_spectrogram_is_written_when_ffmpeg_is_installed(self):
        r = ac.check(str(self.w), None, self.out)
        self.assertEqual(len(r["artifacts"]), 1, r["skipped"])
        self.assertGreater(Path(r["artifacts"][0]).stat().st_size, 0)


class CliTests(TmpCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = ac.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_clean_run_exits_zero_and_prints_the_measurements(self):
        a = self.png("a.png", png_bytes(2, 1, rgba_rows([[RED, BLUE]])))
        rc, out, _ = self.run_cli("check", a, "--reference", a)
        self.assertEqual(rc, 0)
        self.assertIn("made: 2x1, 1 frame(s) (single image), 2 colour(s)", out)
        self.assertIn("differences: none", out)

    def test_a_difference_exits_one_and_lists_it(self):
        a = self.png("a.png", png_bytes(1, 1, rgba_rows([[RED]])))
        b = self.png("b.png", png_bytes(1, 1, rgba_rows([[BLUE]])))
        rc, out, _ = self.run_cli("check", a, "--reference", b)
        self.assertEqual(rc, 1)
        self.assertIn("new colour(s)", out)

    def test_json_output_has_hex_colours(self):
        a = self.png("a.png", png_bytes(1, 1, rgba_rows([[RED]])))
        rc, out, _ = self.run_cli("check", a, "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["metrics"]["palette"], ["#ff0000"])

    def test_an_unreadable_or_malformed_file_exits_two(self):
        self.assertEqual(self.run_cli("check", str(self.dir / "nope.png"))[0], 2)
        bad = self.png("bad.png", b"not a png")
        rc, _, err = self.run_cli("check", bad)
        self.assertEqual(rc, 2)
        self.assertIn("not a PNG", err)

    def test_an_unsupported_type_says_nothing_was_measured_and_exits_zero(self):
        p = self.dir / "a.jpg"
        p.write_bytes(b"\xff\xd8\xff")
        rc, out, _ = self.run_cli("check", str(p))
        self.assertEqual(rc, 0)
        self.assertIn("nothing was measured", out)

    def test_grid_and_frame_size_are_exclusive(self):
        a = self.png("a.png", png_bytes(2, 1, rgba_rows([[RED, BLUE]])))
        self.assertEqual(self.run_cli("check", a, "--grid", "2x1", "--frame-size", "1x1")[0], 2)

    def test_runs_as_a_script(self):
        a = self.png("a.png", png_bytes(1, 1, rgba_rows([[RED]])))
        p = subprocess.run([sys.executable, str(_SCRIPT), "check", a], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("1x1", p.stdout)


class SourceTests(unittest.TestCase):
    def test_stdlib_only_and_no_agentm(self):
        text = _SCRIPT.read_text(encoding="utf-8").lower()
        for bad in ("harness_memory", "process_seam", "agentm_bridge", "import numpy", "import pil", "from pil"):
            self.assertNotIn(bad, text, bad)


if __name__ == "__main__":
    unittest.main()
