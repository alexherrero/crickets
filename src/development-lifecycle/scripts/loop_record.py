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
    loop_record.py dispose    --record FILE --pass NAME --round N --finding I --disposition TEXT
    loop_record.py requirement --record FILE --text TEXT --status met|not-met --evidence TEXT
    loop_record.py not-checked --record FILE --text TEXT
    loop_record.py pair       --record FILE --reference PATH --made PATH      (create / both)
    loop_record.py playtest   --record FILE --text TEXT                       (create / both)
    loop_record.py report     --record FILE
    loop_record.py add-security --record FILE      (the finished diff turned out to need it)

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
    decided     the operator settled the pass (`decide`): go ahead past a direction finding,
                or accept a fix that no further round reviewed. The decision is kept and shown
    continue    otherwise (also before any round is opened)
A fourth round is refused. `stop` exits 0 for done, decided and continue, 3 for escalate.
`decide` is refused when the latest round has no `real` finding: there is nothing to settle.

Doubt theater (`status`): two or more rounds that came back with findings while the whole
record holds no `real` one. Reviews ran and none of it mattered.

Done-report (`report` prints it as markdown; it only reads the record):
    Requirements   each Done-when line, met or not met, with the evidence for it
    Reviews        each pass: tier, rounds, verdict, and every finding with its class,
                   cited line and disposition. A finding with no disposition reads as
                   its class's default (tradeoff: accepted; misread, noise: dismissed);
                   a `real` one with none reads OPEN
    Not checked    what the run did not look at: the caller's list, plus every review
                   the size called for that never ran. The section is always there; with
                   nothing to list it says so, it is never left out. The done-check
                   is not listed: it grades this report, so it has not run yet
    Pairs, Playtest   create-it only: reference beside what was made, and a checklist
A requirement needs evidence either way; a met one with none is refused. Recording a
Done-when line again replaces its earlier entry, so the report lists each line once.

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
REQ_STATUSES = ("met", "not-met")
# What a finding reads as in the report until someone records what was done with it.
DEFAULT_DISPOSITION = {
    "real": "OPEN",
    "tradeoff": "accepted tradeoff",
    "misread": "dismissed: misread",
    "noise": "dismissed: noise",
}

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
            "passes": entries, "requirements": [], "not_checked": [], "pairs": [], "playtest": []}


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


def add_finding(record: Dict[str, Any], name: str, cls: str, line: str, text: str,
                disposition: Optional[str] = None) -> None:
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
    if p.get("decision"):
        raise RecordError("pass %r was decided by the operator; a new finding needs a new decision, "
                          "not a quiet add" % name)
    finding = {"class": cls, "line": line.strip(), "text": text.strip()}
    if disposition and disposition.strip():
        finding["disposition"] = disposition.strip()
    p["rounds"][-1]["findings"].append(finding)


def add_security(record: Dict[str, Any]) -> bool:
    """Add the security pass after correctness. False when the record already has it.

    `init` takes `--security` from what the plan says; the diff can say more once it
    exists. Refused where no security pass can run: a small task runs no reviews, and
    create-only work has no correctness pass for it to follow.
    """
    if record["size"] == "small":
        raise RecordError("a small task runs no reviews; there is nothing to add a security pass to")
    names = [p["name"] for p in record["passes"]]
    if "security" in names:
        return False
    if "correctness" not in names:
        raise RecordError("this record has no correctness pass (profile %s); security follows correctness"
                          % record["profile"])
    entry = _entry("security", "pass", None, "agent:security-auditor")
    entry["rounds"] = []
    record["passes"].insert(names.index("correctness") + 1, entry)
    record["security"] = True
    return True


def dispose(record: Dict[str, Any], name: str, round_n: int, index: int, disposition: str) -> None:
    """Record what was done with a finding. `index` counts from 1 within the round."""
    if not (disposition or "").strip():
        raise RecordError("a disposition needs text")
    p = _find(record, name)
    rounds = [r for r in p["rounds"] if r["n"] == round_n]
    if not rounds:
        raise RecordError("pass %r has no round %d" % (name, round_n))
    findings = rounds[0]["findings"]
    if not 1 <= index <= len(findings):
        raise RecordError("round %d of %r has %d finding(s); %d is out of range"
                          % (round_n, name, len(findings), index))
    findings[index - 1]["disposition"] = disposition.strip()


def add_requirement(record: Dict[str, Any], text: str, status: str, evidence: str) -> None:
    if status not in REQ_STATUSES:
        raise RecordError("status must be one of %s, not %r" % (", ".join(REQ_STATUSES), status))
    if not (text or "").strip():
        raise RecordError("a requirement needs text")
    if not (evidence or "").strip():
        raise RecordError("a requirement needs evidence, met or not: what was looked at, and what it showed")
    entry = {"text": text.strip(), "status": status, "evidence": evidence.strip()}
    reqs = record["requirements"]
    for i, r in enumerate(reqs):
        if r["text"] == entry["text"]:
            reqs[i] = entry  # newer evidence for the same line replaces the old
            return
    reqs.append(entry)


def add_not_checked(record: Dict[str, Any], text: str) -> None:
    if not (text or "").strip():
        raise RecordError("a not-checked item needs text")
    record["not_checked"].append(text.strip())


def _create_only(record: Dict[str, Any], what: str) -> None:
    if record["profile"] == "build":
        raise RecordError("%s belong to create-it work; this record's profile is build" % what)


def add_pair(record: Dict[str, Any], reference: str, made: str) -> None:
    _create_only(record, "paired images")
    if not (reference or "").strip() or not (made or "").strip():
        raise RecordError("a pair needs both a reference path and a made path")
    record["pairs"].append({"reference": reference.strip(), "made": made.strip()})


def add_playtest(record: Dict[str, Any], text: str) -> None:
    _create_only(record, "playtest items")
    if not (text or "").strip():
        raise RecordError("a playtest item needs text")
    record["playtest"].append(text.strip())


def decide(record: Dict[str, Any], name: str, decision: str) -> None:
    """Record the operator's call on a pass whose latest round still has a `real` finding."""
    p = _find(record, name)
    if not (decision or "").strip():
        raise RecordError("a decision needs text: what the operator decided")
    if p.get("decision"):
        raise RecordError("pass %r was already decided (%s); a decision is recorded once" % (name, p["decision"]))
    if not p["rounds"] or not any(f["class"] == "real" for f in p["rounds"][-1]["findings"]):
        raise RecordError("pass %r has no real finding in its latest round; there is nothing to decide" % name)
    p["decision"] = decision.strip()
    # The real findings left standing are what the operator settled: they read as decided, not OPEN.
    for f in p["rounds"][-1]["findings"]:
        if f["class"] == "real" and not f.get("disposition"):
            f["disposition"] = "decided by the operator: %s" % p["decision"]


def stop_verdict(record: Dict[str, Any], name: str) -> str:
    p = _find(record, name)
    if p.get("decision"):
        return "decided"
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


def _open_real(record: Dict[str, Any]) -> int:
    n = 0
    for p in record["passes"]:
        for r in p["rounds"]:
            for f in r["findings"]:
                if f["class"] == "real" and not f.get("disposition"):
                    n += 1
    return n


def render_report(record: Dict[str, Any]) -> str:
    """The done-report as markdown. Reads the record; changes nothing."""
    lines = []  # type: List[str]
    reqs = record["requirements"]
    met = sum(1 for r in reqs if r["status"] == "met")
    escalated = [p["name"] for p in record["passes"] if stop_verdict(record, p["name"]) == "escalate"]
    decided = [p["name"] for p in record["passes"] if stop_verdict(record, p["name"]) == "decided"]
    lines += ["# Done-report", "",
              "Profile: %s · Size: %s" % (record["profile"], record["size"]),
              "Result: %d of %d requirements met · %d real finding(s) open · escalated: %s · %s"
              "doubt theater: %s"
              % (met, len(reqs), _open_real(record), ", ".join(escalated) or "none",
                 ("decided by the operator: %s · " % ", ".join(decided)) if decided else "",
                 "yes" if doubt_theater(record) else "no"),
              "", "## Requirements", ""]
    if not reqs:
        lines.append("No requirements were recorded.")
    for r in reqs:
        lines.append("- [%s] %s — evidence: %s" % ("met" if r["status"] == "met" else "NOT MET",
                                                   r["text"], r["evidence"]))

    lines += ["", "## Reviews", ""]
    if not record["passes"]:
        lines.append("No review ran: free checks only (size: %s)." % record["size"])
    for p in record["passes"]:
        if not p["rounds"]:
            if p["kind"] != "done-check":  # it grades this report, so it cannot have run yet
                lines += ["### %s — never ran" % p["name"], ""]
            continue
        tier = p["tier"] or p["reviewer"]
        verdict = stop_verdict(record, p["name"])
        if verdict == "decided":
            verdict = "decided by the operator: %s" % p["decision"]
        lines.append("### %s (%s) — %d round(s), %s" % (p["name"], tier, len(p["rounds"]), verdict))
        for r in p["rounds"]:
            if not r["findings"]:
                lines.append("- round %d · no findings" % r["n"])
            for f in r["findings"]:
                lines.append("- round %d · %s · `%s` — %s → %s"
                             % (r["n"], f["class"], f["line"], f["text"],
                                f.get("disposition") or DEFAULT_DISPOSITION[f["class"]]))
        lines.append("")

    lines += ["## Not checked", ""]
    unchecked = list(record["not_checked"])
    if not record["passes"]:
        unchecked.append("Every review: this size runs free checks only.")
    unchecked += ["%s: the review never ran" % p["name"] for p in record["passes"]
                  if not p["rounds"] and p["kind"] != "done-check"]
    if unchecked:
        lines += ["- %s" % u for u in unchecked]
    else:
        lines.append("Nothing recorded as unchecked.")

    if record["profile"] in ("create", "both"):
        lines += ["", "## Paired images", ""]
        lines += ["- reference `%s` · made `%s`" % (x["reference"], x["made"]) for x in record["pairs"]] \
            or ["No pairs were recorded."]
        lines += ["", "## Playtest checklist", ""]
        lines += ["- [ ] %s" % t for t in record["playtest"]] or ["No playtest items were recorded."]
    return "\n".join(lines).rstrip("\n") + "\n"


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
    # Records written before the done-report existed lack these; they read as empty.
    for key in ("requirements", "not_checked", "pairs", "playtest"):
        rec.setdefault(key, [])
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
            sp.add_argument("--disposition", help="what was done with it, when already known")
    dc = sub.add_parser("decide", help="record the operator's call on a pass with a real finding standing")
    dc.add_argument("--record", required=True)
    dc.add_argument("--pass", dest="pass_name", required=True)
    dc.add_argument("--decision", required=True, help="what the operator decided, in their words")
    st = sub.add_parser("status", help="every pass's verdict, finding counts, doubt theater")
    st.add_argument("--record", required=True)
    ds = sub.add_parser("dispose", help="record what was done with a finding")
    ds.add_argument("--record", required=True)
    ds.add_argument("--pass", dest="pass_name", required=True)
    ds.add_argument("--round", dest="round_n", required=True, type=int)
    ds.add_argument("--finding", dest="index", required=True, type=int, help="1-based, within the round")
    ds.add_argument("--disposition", required=True)
    rq = sub.add_parser("requirement", help="record a Done-when line, met or not, with its evidence")
    rq.add_argument("--record", required=True)
    rq.add_argument("--text", required=True)
    rq.add_argument("--status", required=True, choices=REQ_STATUSES)
    rq.add_argument("--evidence", required=True)
    nc = sub.add_parser("not-checked", help="record something the run did not look at")
    nc.add_argument("--record", required=True)
    nc.add_argument("--text", required=True)
    pr = sub.add_parser("pair", help="record a reference beside what was made (create-it)")
    pr.add_argument("--record", required=True)
    pr.add_argument("--reference", required=True)
    pr.add_argument("--made", required=True)
    pt = sub.add_parser("playtest", help="record a playtest checklist item (create-it)")
    pt.add_argument("--record", required=True)
    pt.add_argument("--text", required=True)
    rp = sub.add_parser("report", help="print the done-report as markdown")
    rp.add_argument("--record", required=True)
    sc = sub.add_parser("add-security", help="add the security pass after correctness")
    sc.add_argument("--record", required=True)
    return p


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
            add_finding(rec, args.pass_name, args.cls, args.line, args.text, args.disposition)
            save(args.record, rec)
        elif args.cmd == "stop":
            verdict = stop_verdict(rec, args.pass_name)
            print(verdict)
            return 3 if verdict == "escalate" else 0
        elif args.cmd == "status":
            print(json.dumps(status(rec), indent=2))
        elif args.cmd == "report":
            sys.stdout.write(render_report(rec))
        elif args.cmd == "add-security":
            print("added" if add_security(rec) else "already there")
            save(args.record, rec)
        else:
            if args.cmd == "dispose":
                dispose(rec, args.pass_name, args.round_n, args.index, args.disposition)
            elif args.cmd == "decide":
                decide(rec, args.pass_name, args.decision)
            elif args.cmd == "requirement":
                add_requirement(rec, args.text, args.status, args.evidence)
            elif args.cmd == "not-checked":
                add_not_checked(rec, args.text)
            elif args.cmd == "pair":
                add_pair(rec, args.reference, args.made)
            else:
                add_playtest(rec, args.text)
            save(args.record, rec)
        return 0
    except RecordError as exc:
        print("loop_record: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
