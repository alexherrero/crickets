#!/usr/bin/env python3
"""loop_record.py — the build-it / create-it loop's bookkeeping: which passes to run,
what each round found, and when a pass stops.

    loop_record.py passes --profile build|create|both --size small|medium|large
                          [--security] [--prose] [--no-voice]
    loop_record.py init       --record FILE  (same flags as `passes`)
    loop_record.py open-round --record FILE --pass NAME
    loop_record.py add        --record FILE --pass NAME --class CLASS --line PATH:LINE --text TEXT
    loop_record.py stop       --record FILE --pass NAME
    loop_record.py status     --record FILE

The loop is: anchor, size, direction, make, free checks, focused passes, done-report.
This script holds what a script can settle; the command holds the judgment (what a
finding means, which class it gets, what to fix).

Passes by size (`passes` prints them as JSON, in the order to run):
    small    none. Free checks only (tests, linters, asset checks); no reviewer is called.
    medium   direction, ONE pass (the profile's first), done-check.
    large    direction, every pass for the profile, done-check.
    The security-auditor pass is added after correctness, at medium and large, only when
    `--security` says the task touches auth, secrets, shell execution or network input.
    Passes never run in parallel: the list is an order.

Passes by profile:
    build    correctness, simplicity
    create   likeness, craft, voice. Voice only for prose (`--prose`), on unless `--no-voice`.
    both     build's, then create's; medium takes the first pass of each.

Tiers (cross-review.sh's): direction is `high`; correctness is `default` at medium and
`high` at large; every other review pass is `default`; voice is `wording`. The
security-auditor and the done-check are Claude agents (`tier` is null).

A finding has a class and a cited line. The class is one of:
    real       a defect or gap to fix
    tradeoff   a real cost the design accepts on purpose
    misread    the reviewer misunderstood the code or the rule
    noise      true but not worth acting on
A finding with no `path:line` is refused: a finding that cites nothing cannot be checked.

Stop rule, per pass (`stop`): after a round, the pass is
    done        the latest round has no `real` finding (including an empty round)
    escalate    the latest round is round 3 and still has a `real` finding: the operator decides
    continue    otherwise (also before any round is opened)
A fourth round is refused. `stop` exits 0 for done and continue, 3 for escalate.

Doubt theater (`status`): two or more rounds that came back with findings while the whole
record holds no `real` one. Reviews ran and none of it mattered.

Exit codes: 0 fine; 2 usage error, unreadable or invalid record, refused input; 3 escalate.
No agentm, no vault, no network. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional

PROFILES = ("build", "create", "both")
SIZES = ("small", "medium", "large")
CLASSES = ("real", "tradeoff", "misread", "noise")
ROUND_CAP = 3
RECORD_VERSION = 1

_LINE_RE = re.compile(r"^\S.*:\d+(?:-\d+)?$")

BUILD_PASSES = ("correctness", "simplicity")
CREATE_PASSES = ("likeness", "craft", "voice")


class RecordError(ValueError):
    """Bad input to the record: refused, never half-applied."""


def passes_for(profile: str, size: str, security: bool = False, prose: bool = False,
               voice: bool = True) -> List[Dict[str, Any]]:
    """The ordered list of reviews to run. `[]` for small."""
    if profile not in PROFILES:
        raise RecordError("profile must be one of %s, not %r" % (", ".join(PROFILES), profile))
    if size not in SIZES:
        raise RecordError("size must be one of %s, not %r" % (", ".join(SIZES), size))
    if size == "small":
        return []

    build = list(BUILD_PASSES)
    create = [p for p in CREATE_PASSES if p != "voice" or (prose and voice)]
    if size == "medium":
        build, create = build[:1], create[:1]
    chosen = []  # type: List[str]
    if profile in ("build", "both"):
        chosen += build
    if profile in ("create", "both"):
        chosen += create

    out = [_entry("direction", "direction", "high", "cross-review")]
    for name in chosen:
        out.append(_pass_entry(name, size))
        if name == "correctness" and security:
            out.append(_entry("security", "pass", None, "agent:security-auditor"))
    out.append(_entry("done-check", "done-check", None, "agent:evaluator"))
    return out


def _pass_entry(name: str, size: str) -> Dict[str, Any]:
    if name == "voice":
        tier = "wording"
    elif name == "correctness" and size == "large":
        tier = "high"
    else:
        tier = "default"
    return _entry(name, "pass", tier, "cross-review")


def _entry(name: str, kind: str, tier: Optional[str], reviewer: str) -> Dict[str, Any]:
    return {"name": name, "kind": kind, "tier": tier, "reviewer": reviewer}


def new_record(profile: str, size: str, security: bool = False, prose: bool = False,
               voice: bool = True) -> Dict[str, Any]:
    entries = passes_for(profile, size, security, prose, voice)
    for e in entries:
        e["rounds"] = []
    return {"version": RECORD_VERSION, "profile": profile, "size": size,
            "security": bool(security), "prose": bool(prose), "voice": bool(voice),
            "passes": entries}


def _find(record: Dict[str, Any], name: str) -> Dict[str, Any]:
    for p in record["passes"]:
        if p["name"] == name:
            return p
    names = ", ".join(p["name"] for p in record["passes"]) or "(none: this size runs no reviews)"
    raise RecordError("no pass named %r in this record; it has: %s" % (name, names))


def open_round(record: Dict[str, Any], name: str) -> int:
    """Open the next round of a pass and return its number."""
    p = _find(record, name)
    if p["rounds"] and stop_verdict(record, name) != "continue":
        raise RecordError("pass %r has stopped (%s); nothing to open" % (name, stop_verdict(record, name)))
    if len(p["rounds"]) >= ROUND_CAP:
        raise RecordError("pass %r is at the %d-round cap; the operator decides" % (name, ROUND_CAP))
    p["rounds"].append({"n": len(p["rounds"]) + 1, "findings": []})
    return p["rounds"][-1]["n"]


def add_finding(record: Dict[str, Any], name: str, cls: str, line: str, text: str) -> None:
    """Record a finding in the pass's latest round."""
    if cls not in CLASSES:
        raise RecordError("class must be one of %s, not %r" % (", ".join(CLASSES), cls))
    if not _LINE_RE.match((line or "").strip()):
        raise RecordError("a finding must cite a line as path:LINE (or path:LINE-LINE), got %r" % line)
    if not (text or "").strip():
        raise RecordError("a finding needs text")
    p = _find(record, name)
    if not p["rounds"]:
        raise RecordError("pass %r has no open round; run open-round first" % name)
    p["rounds"][-1]["findings"].append({"class": cls, "line": line.strip(), "text": text.strip()})


def stop_verdict(record: Dict[str, Any], name: str) -> str:
    p = _find(record, name)
    if not p["rounds"]:
        return "continue"
    last = p["rounds"][-1]
    if not any(f["class"] == "real" for f in last["findings"]):
        return "done"
    return "escalate" if last["n"] >= ROUND_CAP else "continue"


def doubt_theater(record: Dict[str, Any]) -> bool:
    rounds_with_findings = 0
    for p in record["passes"]:
        for r in p["rounds"]:
            if any(f["class"] == "real" for f in r["findings"]):
                return False
            if r["findings"]:
                rounds_with_findings += 1
    return rounds_with_findings >= 2


def status(record: Dict[str, Any]) -> Dict[str, Any]:
    counts = {c: 0 for c in CLASSES}
    per_pass = []
    for p in record["passes"]:
        for r in p["rounds"]:
            for f in r["findings"]:
                counts[f["class"]] += 1
        per_pass.append({"name": p["name"], "kind": p["kind"], "tier": p["tier"],
                         "rounds": len(p["rounds"]), "verdict": stop_verdict(record, p["name"])})
    return {"profile": record["profile"], "size": record["size"], "findings": counts,
            "doubt_theater": doubt_theater(record), "passes": per_pass}


def load(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except OSError as exc:
        raise RecordError("cannot read the record %s: %s" % (path, exc))
    except ValueError as exc:
        raise RecordError("the record %s is not valid JSON: %s" % (path, exc))
    if not isinstance(rec, dict) or rec.get("version") != RECORD_VERSION or not isinstance(rec.get("passes"), list):
        raise RecordError("the record %s is not a version-%d loop record" % (path, RECORD_VERSION))
    return rec


def save(path: str, record: Dict[str, Any]) -> None:
    """Write beside the target and rename over it, so a crash never leaves half a record."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".loop-record-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _shape_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile", required=True, choices=PROFILES)
    p.add_argument("--size", required=True, choices=SIZES)
    p.add_argument("--security", action="store_true",
                   help="the task touches auth, secrets, shell execution or network input")
    p.add_argument("--prose", action="store_true", help="the work is prose (turns the voice pass on)")
    p.add_argument("--no-voice", action="store_true", help="leave the voice pass out of prose work")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="loop_record.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("passes", help="print the passes to run, as JSON")
    _shape_flags(pa)
    ini = sub.add_parser("init", help="create a record for the task")
    _shape_flags(ini)
    ini.add_argument("--record", required=True)
    for name, helptext in (("open-round", "open the pass's next round"),
                           ("add", "record a finding in the pass's latest round"),
                           ("stop", "should this pass stop?")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--record", required=True)
        sp.add_argument("--pass", dest="pass_name", required=True)
        if name == "add":
            sp.add_argument("--class", dest="cls", required=True, choices=CLASSES)
            sp.add_argument("--line", required=True, help="path:LINE the finding cites")
            sp.add_argument("--text", required=True)
    st = sub.add_parser("status", help="every pass's verdict, finding counts, doubt theater")
    st.add_argument("--record", required=True)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if args.cmd == "passes":
            print(json.dumps(passes_for(args.profile, args.size, args.security, args.prose,
                                        not args.no_voice), indent=2))
            return 0
        if args.cmd == "init":
            if os.path.exists(args.record):
                raise RecordError("%s already exists; a record is never overwritten" % args.record)
            save(args.record, new_record(args.profile, args.size, args.security, args.prose,
                                         not args.no_voice))
            return 0
        rec = load(args.record)
        if args.cmd == "open-round":
            print(open_round(rec, args.pass_name))
            save(args.record, rec)
        elif args.cmd == "add":
            add_finding(rec, args.pass_name, args.cls, args.line, args.text)
            save(args.record, rec)
        elif args.cmd == "stop":
            verdict = stop_verdict(rec, args.pass_name)
            print(verdict)
            return 3 if verdict == "escalate" else 0
        else:
            print(json.dumps(status(rec), indent=2))
        return 0
    except RecordError as exc:
        print("loop_record: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
