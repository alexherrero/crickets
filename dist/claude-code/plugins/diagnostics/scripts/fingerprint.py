#!/usr/bin/env python3
"""Fingerprint normalizer for the /diagnose recall ladder (crickets wave-c-diagnostics).

The stable signature is the error class plus the top in-app stack frame(s)
(file basename, symbol, line) -- deliberately excluding raw messages, absolute
paths, PIDs, timestamps, and stdlib frames. Those never enter the hash input,
so there is nothing to strip: two failures that are the same underlying
incident but captured on different machines/runs collapse to one fingerprint.
"""
from __future__ import annotations

import hashlib
import re

FP_ALGO = "v1"

_FRAME_RE = re.compile(
    r'File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<symbol>\S+)'
)
_LAST_LINE_RE = re.compile(r"^(?P<exc>[\w.]+):")

_STDLIB_MARKERS = ("/lib/python", "/site-packages/", "<frozen ")

_MAX_IN_APP_FRAMES = 2


def _is_in_app_frame(path: str) -> bool:
    return not any(marker in path for marker in _STDLIB_MARKERS)


def _extract_error_class(traceback_text: str) -> str:
    lines = [line for line in traceback_text.strip().splitlines() if line.strip()]
    if not lines:
        return "UnknownError"
    last = lines[-1].strip()
    match = _LAST_LINE_RE.match(last)
    return match.group("exc") if match else last


def extract_signature(traceback_text: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Return (error_class, [(basename, symbol, line), ...]) for the stable frames."""
    frames = [
        (m.group("path"), m.group("symbol"), m.group("line"))
        for m in _FRAME_RE.finditer(traceback_text)
    ]
    in_app = [f for f in frames if _is_in_app_frame(f[0])]
    chosen = in_app or frames
    top_frames = chosen[-_MAX_IN_APP_FRAMES:]
    basenames = [(path.rsplit("/", 1)[-1], symbol, line) for path, symbol, line in top_frames]
    return _extract_error_class(traceback_text), basenames


def compute_fingerprint(traceback_text: str) -> tuple[str, str]:
    """Return (fingerprint_hash, fp_algo) for a raw traceback/log string."""
    error_class, frames = extract_signature(traceback_text)
    signature = "|".join([error_class] + [f"{b}:{s}:{l}" for b, s, l in frames])
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return digest, FP_ALGO
