#!/usr/bin/env python3
"""asset_checks.py — the free checks for create-it: measure a PNG or WAV and compare it to its reference.

    asset_checks.py check MADE [--reference REF] [--grid COLSxROWS | --frame-size WxH]
                    [--out-dir DIR] [--length-tolerance 0.05] [--level-tolerance-db 3] [--json]

What it measures (no judgment, no model):
    PNG   width and height; frame count (an APNG's own count, or the sprite-sheet grid
          when `--grid` or `--frame-size` says how the sheet is cut) and how many of
          those frames are empty; the colour palette (every distinct RGBA value).
    WAV   length, sample rate, channels, peak and RMS level in dBFS.

With `--reference` it compares and lists each difference, one line each:
    PNG   size mismatch, frame-count mismatch, colours the made file has and the
          reference does not (new), colours the reference has and the made file
          does not (missing).
    WAV   sample-rate or channel mismatch, length off by more than the length
          tolerance (a fraction, default 0.05), peak or RMS off by more than the
          level tolerance (dB, default 3).

When ImageMagick (`magick` or `convert`) or `ffmpeg` is installed and `--out-dir` is
given, it also writes a side-by-side image (PNG) and a spectrogram image (WAV, needs
ffmpeg), for a person or a model to look at. When the tool is missing, the output says
so under `skipped`; a skipped item was not checked, and nothing is silently dropped.

Only standard-library decoding: non-interlaced PNG of any colour type and bit depth,
and integer-PCM WAV. An interlaced PNG, a PNG over 4 million pixels, a float or
compressed WAV, and any other file type are measured as far as they can be and the
rest is listed under `skipped`. Checking is by file extension.

Exit codes: 0 measured and no difference from the reference; 1 at least one
difference; 2 usage error or an unreadable or malformed file.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import wave
import zlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PIXELS = 4_000_000
SHOW_COLOURS = 8  # how many example colours a difference line names

_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
_VALID_DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}


class AssetError(ValueError):
    """A file that cannot be read as what its extension says."""


# --------------------------------------------------------------------------- PNG

def _chunks(data: bytes) -> List[Tuple[bytes, bytes]]:
    if data[:8] != PNG_SIGNATURE:
        raise AssetError("not a PNG (bad signature)")
    out = []  # type: List[Tuple[bytes, bytes]]
    pos = 8
    while pos < len(data):
        if pos + 8 > len(data):
            raise AssetError("truncated PNG (chunk header)")
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise AssetError("truncated PNG (chunk %s)" % ctype.decode("latin-1"))
        out.append((ctype, body))
        pos += 12 + length
        if ctype == b"IEND":
            break
    return out


def _unfilter(raw: bytes, row_bytes: int, height: int, bpp: int) -> List[bytearray]:
    rows = []  # type: List[bytearray]
    prev = bytearray(row_bytes)
    pos = 0
    for _ in range(height):
        if pos + 1 + row_bytes > len(raw):
            raise AssetError("truncated PNG (image data)")
        ftype = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + row_bytes])
        pos += 1 + row_bytes
        if ftype == 1:
            for i in range(bpp, row_bytes):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ftype == 2:
            for i in range(row_bytes):
                line[i] = (line[i] + prev[i]) & 255
        elif ftype == 3:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(row_bytes):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        elif ftype != 0:
            raise AssetError("PNG row uses unknown filter type %d" % ftype)
        rows.append(line)
        prev = line
    return rows


def _samples(row: bytearray, count: int, depth: int) -> List[int]:
    if depth == 8:
        return list(row[:count])
    if depth == 16:
        return [(row[2 * i] << 8) | row[2 * i + 1] for i in range(count)]
    per = 8 // depth
    mask = (1 << depth) - 1
    out = []
    for i in range(count):
        byte = row[i // per]
        shift = 8 - depth * (i % per + 1)
        out.append((byte >> shift) & mask)
    return out


def read_png(path: str) -> Dict[str, Any]:
    """Header facts, APNG frame count, and, when it can be decoded, the pixel rows as RGBA tuples."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise AssetError("cannot read %s: %s" % (path, exc))
    chunks = _chunks(data)
    ihdr = next((b for t, b in chunks if t == b"IHDR"), None)
    if ihdr is None or len(ihdr) != 13:
        raise AssetError("PNG has no valid IHDR")
    width, height, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if ctype not in _CHANNELS or depth not in _VALID_DEPTHS[ctype]:
        raise AssetError("PNG has an invalid colour type / bit depth (%d / %d)" % (ctype, depth))
    info = {"width": width, "height": height, "bit_depth": depth, "color_type": ctype,
            "apng_frames": None, "pixels": None, "skipped": []}  # type: Dict[str, Any]
    actl = next((b for t, b in chunks if t == b"acTL"), None)
    if actl is not None and len(actl) >= 4:
        info["apng_frames"] = struct.unpack(">I", actl[:4])[0]
        info["skipped"].append("APNG: the palette is measured on the default image only")
    if interlace:
        info["skipped"].append("interlaced PNG: size and frames measured, palette and empty frames not")
        return info
    if width * height > MAX_PIXELS:
        info["skipped"].append("PNG over %d pixels: size and frames measured, palette and empty frames not"
                               % MAX_PIXELS)
        return info

    channels = _CHANNELS[ctype]
    bits = channels * depth
    row_bytes = (width * bits + 7) // 8
    try:
        raw = zlib.decompress(b"".join(b for t, b in chunks if t == b"IDAT"))
    except zlib.error as exc:
        raise AssetError("PNG image data is corrupt: %s" % exc)
    rows = _unfilter(raw, row_bytes, height, max(1, bits // 8))
    plte = next((b for t, b in chunks if t == b"PLTE"), b"")
    palette = [tuple(plte[i:i + 3]) for i in range(0, len(plte) - len(plte) % 3, 3)]
    trns = next((b for t, b in chunks if t == b"tRNS"), b"")
    maxv = (1 << depth) - 1
    scale = (lambda v: v * 255 // maxv) if depth != 8 else (lambda v: v)
    if ctype == 3 and not palette:
        raise AssetError("palette PNG has no PLTE chunk")

    out_rows = []  # type: List[List[Tuple[int, int, int, int]]]
    for row in rows:
        s = _samples(row, width * channels, depth)
        px = []  # type: List[Tuple[int, int, int, int]]
        for x in range(width):
            if ctype == 0:
                v = s[x]
                a = 0 if len(trns) >= 2 and v == struct.unpack(">H", trns[:2])[0] else 255
                g = scale(v)
                px.append((g, g, g, a))
            elif ctype == 2:
                r, g, b = s[3 * x:3 * x + 3]
                a = 255
                if len(trns) >= 6 and (r, g, b) == struct.unpack(">HHH", trns[:6]):
                    a = 0
                px.append((scale(r), scale(g), scale(b), a))
            elif ctype == 3:
                i = s[x]
                if i >= len(palette):
                    raise AssetError("palette PNG indexes past its PLTE")
                r, g, b = palette[i]
                px.append((r, g, b, trns[i] if i < len(trns) else 255))
            elif ctype == 4:
                g = scale(s[2 * x])
                px.append((g, g, g, scale(s[2 * x + 1])))
            else:
                r, g, b, a = s[4 * x:4 * x + 4]
                px.append((scale(r), scale(g), scale(b), scale(a)))
        out_rows.append(px)
    info["pixels"] = out_rows
    return info


def _hex(c: Tuple[int, int, int, int]) -> str:
    return "#%02x%02x%02x" % c[:3] + ("" if c[3] == 255 else "%02x" % c[3])


def parse_grid(grid: Optional[str], frame_size: Optional[str]) -> Optional[Tuple[str, int, int]]:
    for kind, value in (("grid", grid), ("frame-size", frame_size)):
        if value:
            m = re.match(r"^(\d+)[xX](\d+)$", value.strip())
            if not m or int(m.group(1)) < 1 or int(m.group(2)) < 1:
                raise AssetError("--%s needs two positive whole numbers like 8x1, got %r" % (kind, value))
            return kind, int(m.group(1)), int(m.group(2))
    return None


def png_metrics(path: str, grid: Optional[str] = None, frame_size: Optional[str] = None) -> Dict[str, Any]:
    info = read_png(path)
    cut = parse_grid(grid, frame_size)
    out = {"type": "png", "width": info["width"], "height": info["height"], "frames": None,
           "frames_from": None, "empty_frames": None, "palette": None, "skipped": list(info["skipped"])}
    w, h = info["width"], info["height"]
    fw = fh = None
    if cut:
        kind, a, b = cut
        cols, rows = (a, b) if kind == "grid" else (w // a if a else 0, h // b if b else 0)
        fw, fh = (w // a, h // b) if kind == "grid" else (a, b)
        if kind == "grid" and (w % a or h % b):
            raise AssetError("a %dx%d image does not split evenly into a %dx%d grid" % (w, h, a, b))
        if kind == "frame-size" and (w % a or h % b):
            raise AssetError("a %dx%d image is not a whole number of %dx%d frames" % (w, h, a, b))
        out["frames"], out["frames_from"] = cols * rows, "sheet %dx%d of %dx%d" % (cols, rows, fw, fh)
    elif info["apng_frames"] is not None:
        out["frames"], out["frames_from"] = info["apng_frames"], "APNG"
    else:
        out["frames"], out["frames_from"] = 1, "single image"
    px = info["pixels"]
    if px is not None:
        out["palette"] = sorted({c for row in px for c in row})
        if cut and fw and fh:
            empty = 0
            for fy in range(h // fh):
                for fx in range(w // fw):
                    if all(c[3] == 0 for row in px[fy * fh:(fy + 1) * fh] for c in row[fx * fw:(fx + 1) * fw]):
                        empty += 1
            out["empty_frames"] = empty
    return out


def compare_png(made: Dict[str, Any], ref: Dict[str, Any]) -> List[str]:
    diffs = []  # type: List[str]
    if (made["width"], made["height"]) != (ref["width"], ref["height"]):
        diffs.append("size mismatch: made %dx%d, reference %dx%d"
                     % (made["width"], made["height"], ref["width"], ref["height"]))
    if made["frames"] != ref["frames"]:
        diffs.append("frame count mismatch: made %s, reference %s" % (made["frames"], ref["frames"]))
    if made["palette"] is not None and ref["palette"] is not None:
        new = sorted(set(made["palette"]) - set(ref["palette"]))
        gone = sorted(set(ref["palette"]) - set(made["palette"]))
        if new:
            diffs.append("%d new colour(s) not in the reference: %s" % (len(new), _examples(new)))
        if gone:
            diffs.append("%d reference colour(s) missing from the made file: %s" % (len(gone), _examples(gone)))
    return diffs


def _examples(colours: Sequence[Tuple[int, int, int, int]]) -> str:
    shown = ", ".join(_hex(c) for c in colours[:SHOW_COLOURS])
    return shown + (", ..." if len(colours) > SHOW_COLOURS else "")


# --------------------------------------------------------------------------- WAV

def _db(x: float) -> Optional[float]:
    return None if x <= 0 else round(20 * math.log10(x), 2)


def _wav_format_tag(path: str) -> Optional[int]:
    """The WAV's format tag from its `fmt ` chunk (1 = integer PCM, 3 = float), or None if unreadable.

    A WAVE_FORMAT_EXTENSIBLE file (0xFFFE) names its real format in the sub-format GUID.
    The `wave` module of some Python versions opens a float file and hands back its raw
    bytes; reading them as integers would give confident, wrong levels, so the tag is
    checked here rather than left to whichever Python is running.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(65536)
    except OSError:
        return None
    if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        return None
    pos = 12
    while pos + 8 <= len(head):
        cid, size = head[pos:pos + 4], struct.unpack("<I", head[pos + 4:pos + 8])[0]
        body = head[pos + 8:pos + 8 + size]
        if cid == b"fmt " and len(body) >= 2:
            tag = struct.unpack("<H", body[:2])[0]
            if tag == 0xFFFE and len(body) >= 26:
                return struct.unpack("<H", body[24:26])[0]
            return tag
        pos += 8 + size + (size & 1)
    return None


def wav_metrics(path: str) -> Dict[str, Any]:
    tag = _wav_format_tag(path)
    if tag not in (None, 1):
        return {"type": "wav", "length_s": None, "sample_rate": None, "channels": None,
                "peak_dbfs": None, "rms_dbfs": None, "measured": False,
                "skipped": ["WAV not measured: format tag %d is not integer PCM (3 is float); only integer PCM is read" % tag]}
    try:
        wf = wave.open(path, "rb")
    except (OSError, EOFError) as exc:
        raise AssetError("cannot read %s: %s" % (path, exc))
    except wave.Error as exc:
        if not str(exc).startswith("unknown format"):
            raise AssetError("%s is not a readable WAV: %s" % (path, exc))
        # float or compressed audio: the stdlib reader refuses the format; say so, measure nothing
        return {"type": "wav", "length_s": None, "sample_rate": None, "channels": None,
                "peak_dbfs": None, "rms_dbfs": None, "measured": False,
                "skipped": ["WAV not measured: %s (only integer PCM is read)" % exc]}
    with wf:
        rate, channels, width, frames = wf.getframerate(), wf.getnchannels(), wf.getsampwidth(), wf.getnframes()
        raw = wf.readframes(frames)
    if width == 1:
        vals = [(b - 128) / 128.0 for b in raw]
    elif width == 2:
        a = array.array("h")
        a.frombytes(raw[:len(raw) - len(raw) % 2])
        if sys.byteorder == "big":
            a.byteswap()
        vals = [v / 32768.0 for v in a]
    elif width == 3:
        vals = []
        for i in range(0, len(raw) - 2, 3):
            v = int.from_bytes(raw[i:i + 3], "little", signed=True)
            vals.append(v / 8388608.0)
    elif width == 4:
        a = array.array("i")
        a.frombytes(raw[:len(raw) - len(raw) % 4])
        if sys.byteorder == "big":
            a.byteswap()
        vals = [v / 2147483648.0 for v in a]
    else:
        raise AssetError("unsupported WAV sample width %d" % width)
    peak = max((abs(v) for v in vals), default=0.0)
    rms = math.sqrt(sum(v * v for v in vals) / len(vals)) if vals else 0.0
    return {"type": "wav", "length_s": round(frames / float(rate), 4) if rate else None,
            "sample_rate": rate, "channels": channels, "peak_dbfs": _db(peak), "rms_dbfs": _db(rms),
            "measured": True, "skipped": []}


def compare_wav(made: Dict[str, Any], ref: Dict[str, Any], length_tolerance: float = 0.05,
                level_tolerance_db: float = 3.0) -> List[str]:
    if not made.get("measured") or not ref.get("measured"):
        return []
    diffs = []  # type: List[str]
    if made["sample_rate"] != ref["sample_rate"]:
        diffs.append("sample rate mismatch: made %s Hz, reference %s Hz" % (made["sample_rate"], ref["sample_rate"]))
    if made["channels"] != ref["channels"]:
        diffs.append("channel count mismatch: made %s, reference %s" % (made["channels"], ref["channels"]))
    ml, rl = made["length_s"], ref["length_s"]
    if ml is not None and rl and abs(ml - rl) / rl > length_tolerance:
        diffs.append("length differs: made %.3fs, reference %.3fs (more than %.0f%%)" % (ml, rl, length_tolerance * 100))
    for key, label in (("peak_dbfs", "peak"), ("rms_dbfs", "RMS")):
        m, r = made[key], ref[key]
        if (m is None) != (r is None):
            diffs.append("%s level differs: made %s, reference %s (one is silent)" % (label, _fmt_db(m), _fmt_db(r)))
        elif m is not None and abs(m - r) > level_tolerance_db:
            diffs.append("%s level differs: made %s, reference %s (more than %g dB)"
                         % (label, _fmt_db(m), _fmt_db(r), level_tolerance_db))
    return diffs


def _fmt_db(v: Optional[float]) -> str:
    return "silence" if v is None else "%.1f dBFS" % v


# ------------------------------------------------------------- optional tools

Which = Callable[[str], Optional[str]]
Runner = Callable[..., Any]


def side_by_side(made: str, ref: str, out: str, which: Which = shutil.which,
                 runner: Runner = subprocess.run) -> Optional[str]:
    """Write reference | made as one PNG. Returns None on success, else why it was skipped."""
    magick = which("magick") or which("convert")
    if magick:
        cmd = [magick, ref, made, "+append", out]
    elif which("ffmpeg"):
        cmd = [which("ffmpeg"), "-y", "-v", "error", "-i", ref, "-i", made,
               "-filter_complex", "hstack=inputs=2", "-frames:v", "1", out]
    else:
        return "side-by-side image skipped: neither ImageMagick (magick, convert) nor ffmpeg is installed"
    return _run(cmd, out, "side-by-side image", runner)


def spectrogram(wav: str, out: str, which: Which = shutil.which, runner: Runner = subprocess.run) -> Optional[str]:
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        return "spectrogram skipped: ffmpeg is not installed"
    cmd = [ffmpeg, "-y", "-v", "error", "-i", wav, "-lavfi", "showspectrumpic=s=800x300:legend=0", out]
    return _run(cmd, out, "spectrogram", runner)


def _run(cmd: List[str], out: str, what: str, runner: Runner) -> Optional[str]:
    try:
        p = runner(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "%s skipped: %s" % (what, exc)
    if p.returncode != 0 or not os.path.exists(out):
        return "%s skipped: %s exited %s%s" % (what, os.path.basename(cmd[0]), p.returncode,
                                              (": " + p.stderr.strip().splitlines()[-1]) if p.stderr.strip() else "")
    return None


# ----------------------------------------------------------------------- driver

def check(made: str, reference: Optional[str] = None, out_dir: Optional[str] = None,
          grid: Optional[str] = None, frame_size: Optional[str] = None,
          length_tolerance: float = 0.05, level_tolerance_db: float = 3.0,
          which: Which = shutil.which, runner: Runner = subprocess.run) -> Dict[str, Any]:
    ext = os.path.splitext(made)[1].lower()
    result = {"file": made, "reference": reference, "metrics": None, "reference_metrics": None,
              "differences": [], "artifacts": [], "skipped": []}  # type: Dict[str, Any]
    if ext == ".png":
        result["metrics"] = png_metrics(made, grid, frame_size)
        if reference:
            result["reference_metrics"] = png_metrics(reference, grid, frame_size)
            result["differences"] = compare_png(result["metrics"], result["reference_metrics"])
    elif ext == ".wav":
        if grid or frame_size:
            raise AssetError("--grid and --frame-size apply to PNG files, not WAV")
        result["metrics"] = wav_metrics(made)
        if reference:
            result["reference_metrics"] = wav_metrics(reference)
            result["differences"] = compare_wav(result["metrics"], result["reference_metrics"],
                                                length_tolerance, level_tolerance_db)
    else:
        result["skipped"].append("%s files are not checked here (only .png and .wav); nothing was measured"
                                 % (ext or "extension-less"))
        return result
    for m in (result["metrics"], result["reference_metrics"]):
        if m:
            result["skipped"] += m.pop("skipped", [])
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(made))[0]
        if ext == ".png" and reference:
            out = os.path.join(out_dir, stem + ".side-by-side.png")
            why = side_by_side(made, reference, out, which, runner)
            (result["skipped"].append(why) if why else result["artifacts"].append(out))
        if ext == ".wav":
            for label, src in (("made", made), ("reference", reference)):
                if not src:
                    continue
                out = os.path.join(out_dir, "%s.%s.spectrogram.png" % (stem, label))
                why = spectrogram(src, out, which, runner)
                (result["skipped"].append(why) if why else result["artifacts"].append(out))
    return result


def render_text(result: Dict[str, Any]) -> str:
    lines = ["file: %s" % result["file"]]
    for label, key in (("made", "metrics"), ("reference", "reference_metrics")):
        m = result[key]
        if not m:
            continue
        if m["type"] == "png":
            lines.append("%s: %dx%d, %s frame(s) (%s)%s, %s" % (
                label, m["width"], m["height"], m["frames"], m["frames_from"],
                "" if m["empty_frames"] is None else ", %d empty" % m["empty_frames"],
                "palette not measured" if m["palette"] is None else "%d colour(s)" % len(m["palette"])))
        elif m.get("measured"):
            lines.append("%s: %.3fs, %s Hz, %s channel(s), peak %s, RMS %s" % (
                label, m["length_s"], m["sample_rate"], m["channels"], _fmt_db(m["peak_dbfs"]), _fmt_db(m["rms_dbfs"])))
    if result["reference"]:
        lines.append("differences: %s" % ("none" if not result["differences"] else ""))
        lines += ["  - %s" % d for d in result["differences"]]
    for a in result["artifacts"]:
        lines.append("wrote: %s" % a)
    if result["skipped"]:
        lines.append("skipped:")
        lines += ["  - %s" % s for s in result["skipped"]]
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="asset_checks.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="measure a PNG or WAV and compare it to a reference")
    c.add_argument("made")
    c.add_argument("--reference")
    g = c.add_mutually_exclusive_group()
    g.add_argument("--grid", help="the sprite sheet is COLSxROWS frames, e.g. 8x1")
    g.add_argument("--frame-size", help="each frame is WxH pixels, e.g. 32x32")
    c.add_argument("--out-dir", help="write side-by-side / spectrogram images here when a tool is installed")
    c.add_argument("--length-tolerance", type=float, default=0.05)
    c.add_argument("--level-tolerance-db", type=float, default=3.0)
    c.add_argument("--json", action="store_true")
    return p


def _jsonable(result: Dict[str, Any]) -> Dict[str, Any]:
    """The palette as hex strings, so the JSON stays readable and small."""
    out = dict(result)
    for key in ("metrics", "reference_metrics"):
        m = out.get(key)
        if m and m.get("palette") is not None:
            m = dict(m)
            m["palette"] = [_hex(c) for c in m["palette"]]
            out[key] = m
    return out


def _utf8_stdio() -> None:
    """Write UTF-8 whatever the console's code page is: a Windows console's cp1252 cannot encode
    the arrows and dots this prints. A stream that cannot be reconfigured is left alone."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _utf8_stdio()
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        result = check(args.made, args.reference, args.out_dir, args.grid, args.frame_size,
                       args.length_tolerance, args.level_tolerance_db)
    except AssetError as exc:
        print("asset_checks: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        json.dump(_jsonable(result), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(result))
    return 1 if result["differences"] else 0


if __name__ == "__main__":
    sys.exit(main())
