#!/usr/bin/env python3
"""Channel to Brain helper. Python 3 standard library only.

Offline bookkeeping: inventory by unique video ID, ranking, analysis windows,
claim/record/resume, result-file checks, coverage counts.
It makes NO network or API calls, installs nothing, and never reads or prints
a credential value. Nothing here chooses a model, route or channel.

Usage: python3 ctb.py --workdir DIR <command> [options]
Commands: init, import, rank, windows, next, claim, release, record,
          unblock, check, coverage, credential-check
Every failure (error status, filter output, refusal) is recorded as
"blocked" and is never offered again until the user approves it with
`unblock --approval-note TEXT`.
"""
import argparse, csv, datetime, json, math, os, re, sys

STAGES = ["transcript", "spoken", "visual", "currency", "reviewed", "package_ready"]
STATUSES = ["not_started", "in_progress", "done", "partial", "blocked", "missing", "n/a"]
DEFAULT_CONFIG = {
    "window_seconds": 600,
    "inventory_file": "inventory.json",
    "results_dir": "results",
    "key_env_name": "",
}


ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def safe_id(vid):
    """Video IDs become file names: letters, digits, underscore, hyphen only."""
    if not isinstance(vid, str) or not ID_RE.match(vid):
        die("unsafe or invalid video_id %r (allowed: 1-64 of letters, digits, _ and -)" % (vid,))
    return vid


def read_json(path, what):
    try:
        with open(path) as f:
            return json.load(f)
    except (ValueError, OSError) as ex:
        die("corrupt or unreadable %s %s (%s). Not guessing; fix or remove it." % (what, path, type(ex).__name__))


def valid_date(d):
    if not isinstance(d, str) or not DATE_RE.match(d):
        return False
    try:
        datetime.date.fromisoformat(d)
    except ValueError:
        return False
    return True


def num(v, name, vid, integer=False):
    if isinstance(v, bool):
        die("%s for %s is not a number: %r" % (name, vid, v))
    try:
        x = float(v)
    except (TypeError, ValueError):
        die("%s for %s is not a number: %r" % (name, vid, v))
    if not math.isfinite(x) or x < 0:
        die("%s for %s must be finite and >= 0: %r" % (name, vid, v))
    if integer and x != int(x):
        die("%s for %s must be a whole number: %r" % (name, vid, v))
    return int(x) if integer else x


def die(msg, code=2):
    print("error: " + msg, file=sys.stderr)
    sys.exit(code)


def result_problem(r, vid, s, e):
    """Returns None if the result record is sound for this exact window, else a reason."""
    if not isinstance(r, dict):
        return "not a JSON object"
    if r.get("video_id") != vid or r.get("start") != s or r.get("end") != e or isinstance(r.get("start"), bool):
        return "video_id or window in contents does not match the file name"
    if r.get("status") not in ("ok", "error", "filter", "refusal"):
        return "invalid status"
    for k in ("http_status", "tokens"):
        x = r.get(k, 0)
        if isinstance(x, bool) or not isinstance(x, int) or x < 0:
            return "%s must be a whole number >= 0" % k
    for k in ("model", "note", "text"):
        if not isinstance(r.get(k, ""), str):
            return "%s must be text" % k
    if r["status"] == "ok" and not (r.get("text") or "").strip():
        return "ok result has empty text"
    return None


class Work:
    def __init__(self, workdir):
        self.dir = os.path.abspath(workdir)
        self.cfg_path = os.path.join(self.dir, "ctb.config.json")
        self.cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(self.cfg_path):
            c = read_json(self.cfg_path, "config")
            if not isinstance(c, dict):
                die("config %s must be a JSON object" % self.cfg_path)
            self.cfg.update(c)
        ws = self.cfg.get("window_seconds")
        if isinstance(ws, bool) or not isinstance(ws, int) or ws < 1:
            die("window_seconds in config must be a whole number >= 1")
        for k in ("inventory_file", "results_dir"):
            v = self.cfg.get(k)
            if not isinstance(v, str) or not v or os.path.isabs(v) or ".." in v.replace("\\", "/").split("/"):
                die("%s in config must be a relative path inside the work folder" % k)
        self.inv_path = os.path.join(self.dir, self.cfg["inventory_file"])
        self.res_dir = os.path.join(self.dir, self.cfg["results_dir"])

    def load(self):
        if not os.path.exists(self.inv_path):
            die("no inventory at %s (run init, then import)" % self.inv_path)
        inv = read_json(self.inv_path, "inventory")
        if not isinstance(inv, dict) or not isinstance(inv.get("videos"), list):
            die("inventory %s has no videos list" % self.inv_path)
        seen = set()
        for v in inv["videos"]:
            if not isinstance(v, dict):
                die("inventory entry is not an object")
            safe_id(v.get("video_id"))
            if v["video_id"] in seen:
                die("duplicate video_id %s in inventory" % v["video_id"])
            seen.add(v["video_id"])
            for k in ("length_s", "views", "relevance", "knowledge_value"):
                v[k] = num(v.get(k, 0) if v.get(k) not in (None, "") else 0, k, v["video_id"])  # normalised to numbers
            d = v.get("upload_date") or ""
            if d and not valid_date(d):
                die("upload_date for %s must be a real date, YYYY-MM-DD: %r" % (v["video_id"], d))
            if "stages" in v:
                st = v["stages"]
                if not isinstance(st, dict) or any(k not in STAGES or x not in STATUSES for k, x in st.items()):
                    die("stages for %s are invalid" % v["video_id"])
            else:
                v["stages"] = {x: "not_started" for x in STAGES}
            for k in ("title", "date_evidence", "content_language", "rank_reason"):
                if not isinstance(v.get(k, ""), str):
                    die("%s for %s must be text" % (k, v["video_id"]))
        return inv

    def save(self, inv):
        tmp = self.inv_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(inv, f, indent=2, sort_keys=True)
        os.replace(tmp, self.inv_path)

    def wname(self, vid, s, e):
        safe_id(vid)
        if not (isinstance(s, int) and isinstance(e, int)) or s < 0 or e <= s:
            die("window must be whole seconds with 0 <= start < end")
        return "%s__%d-%d" % (vid, s, e)

    def rpath(self, vid, s, e):
        return os.path.join(self.res_dir, self.wname(vid, s, e) + ".json")

    def cpath(self, vid, s, e):
        return os.path.join(self.res_dir, self.wname(vid, s, e) + ".claim")

    def window_list(self, v):
        n = int(num(v.get("length_s") or 0, "length_s", v.get("video_id")))
        step = int(self.cfg["window_seconds"])
        if n <= 0:
            return []
        return [(s, min(s + step, n)) for s in range(0, n, step)]

    def state(self, vid, s, e):
        p = self.rpath(vid, s, e)
        if os.path.exists(p):
            r = read_json(p, "result file")
            bad = result_problem(r, vid, s, e)
            if bad:
                die("result file %s is invalid (%s). Not counting it; fix or remove it." % (p, bad))
            return "done" if r["status"] == "ok" else "blocked"
        if os.path.exists(self.cpath(vid, s, e)):
            return "claimed"
        return "missing"


def cmd_init(w, a):
    os.makedirs(w.res_dir, exist_ok=True)
    if not os.path.exists(w.cfg_path):
        with open(w.cfg_path, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    if not os.path.exists(w.inv_path):
        w.save({"videos": []})
    print("initialised", w.dir)


def cmd_import(w, a):
    inv = w.load()
    have = {v["video_id"] for v in inv["videos"]}
    rows = []
    if a.file.endswith(".json"):
        rows = read_json(a.file, "import file")
        if not isinstance(rows, list):
            die("import JSON must be a list of objects")
    else:
        try:
            with open(a.file, newline="") as f:
                rows = list(csv.DictReader(f))
        except (OSError, UnicodeDecodeError, csv.Error) as ex:
            die("cannot read import file (%s)" % type(ex).__name__)
    added = dup = 0
    for r in rows:
        if not isinstance(r, dict):
            die("import row is not an object: %r" % (r,))
        vid = safe_id(str(r.get("video_id") or "").strip())
        if vid in have:
            dup += 1
            continue
        have.add(vid)
        v = {"video_id": vid, "stages": {s: "not_started" for s in STAGES}}
        for k in ("title", "upload_date", "date_evidence", "content_language", "rank_reason"):
            v[k] = str(r.get(k) or "")[:500]
        if v["upload_date"] and not valid_date(v["upload_date"]):
            die("upload_date for %s must be a real date, YYYY-MM-DD: %r" % (vid, v["upload_date"]))
        for k in ("length_s", "views", "relevance", "knowledge_value"):
            v[k] = num(r.get(k) if r.get(k) not in (None, "") else 0, k, vid)
        inv["videos"].append(v)
        added += 1
    w.save(inv)
    print(json.dumps({"added": added, "duplicates_skipped": dup, "unique_total": len(inv["videos"])}))


def cmd_rank(w, a):
    inv = w.load()

    def key(v):
        d = v.get("upload_date") or ""
        # relevance desc, knowledge desc, upload date desc (unknown last), views desc, id asc
        return (-v.get("relevance", 0), -v.get("knowledge_value", 0),
                0 if d else 1, "".join(chr(255 - ord(c)) for c in d),
                -v.get("views", 0), v["video_id"])
    inv["videos"].sort(key=key)
    for i, v in enumerate(inv["videos"], 1):
        v["rank"] = i
    w.save(inv)
    print("ranked %d videos" % len(inv["videos"]))


def cmd_windows(w, a):
    inv = w.load()
    out = []
    for v in inv["videos"]:
        if a.video and v["video_id"] != a.video:
            continue
        for s, e in w.window_list(v):
            out.append({"video_id": v["video_id"], "start": s, "end": e,
                        "state": w.state(v["video_id"], s, e)})
    print(json.dumps(out, indent=2))


def cmd_next(w, a):
    inv = w.load()
    out, blocked, claimed = [], [], []
    for v in inv["videos"]:
        for s, e in w.window_list(v):
            st = w.state(v["video_id"], s, e)
            item = {"video_id": v["video_id"], "start": s, "end": e}
            if st == "missing" and len(out) < a.limit:
                out.append(item)
            elif st == "blocked":
                blocked.append(item)
            elif st == "claimed":
                claimed.append(item)
    print(json.dumps({"next": out, "blocked_need_user_decision": blocked,
                      "claimed_in_progress_or_stale": claimed}, indent=2))


def in_plan(w, vid, s, e):
    for v in w.load()["videos"]:
        if v["video_id"] == vid:
            return (s, e) in w.window_list(v)
    return False


def claim_window(w, vid, s, e, owner=""):
    """Returns None on success, or a message on refusal."""
    if not in_plan(w, vid, s, e):
        return "window is not in the plan for this video"
    os.makedirs(w.res_dir, exist_ok=True)
    if os.path.exists(w.rpath(vid, s, e)):
        return "window already has a result: refusing duplicate"
    try:
        fd = os.open(w.cpath(vid, s, e), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return "window already claimed by another worker"
    os.write(fd, ("%s pid=%d t=%d" % (owner or "", os.getpid(), int(__import__("time").time()))).encode())
    os.close(fd)
    return None


def cmd_claim(w, a):
    m = claim_window(w, a.video, a.start, a.end, a.owner)
    if m:
        die(m, 3)
    print("claimed", w.wname(a.video, a.start, a.end))


def cmd_release(w, a):
    try:
        os.remove(w.cpath(a.video, a.start, a.end))
    except FileNotFoundError:
        pass
    print("released")


def record_result(w, vid, s, e, status, http_status=0, tokens=0, model="", note="", text=""):
    """Returns None on success, or a message on refusal."""
    if status not in ("ok", "error", "filter", "refusal"):
        return "status must be ok, error, filter or refusal"
    if not in_plan(w, vid, s, e):
        return "window is not in the plan for this video"
    p = w.rpath(vid, s, e)
    if os.path.exists(p):
        old = read_json(p, "result file")
        if isinstance(old, dict) and old.get("status") == "ok":
            return "saved success exists: not overwriting"
        return "window is blocked; use unblock with the user's approval first"
    if status == "ok" and not text.strip():
        return "status ok needs non-empty text: empty output is a block, record it as filter or error"
    os.makedirs(w.res_dir, exist_ok=True)
    rec = {"video_id": vid, "start": s, "end": e, "status": status,
           "http_status": http_status, "tokens": tokens, "model": model,
           "note": note, "text": text}
    # Write to a private temp file, then publish with os.link: atomic, never leaves a
    # half-written result, and fails if another writer got there first (no overwrite).
    tmp = "%s.%d-%s.tmp" % (p, os.getpid(), os.urandom(6).hex())  # unique per writer, threads included
    with open(tmp, "w") as f:
        json.dump(rec, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    try:
        try:
            os.link(tmp, p)
        except FileExistsError:
            return "another writer saved this window first: not overwriting"
        except OSError as ex:
            # No silent fallback to an overwrite race: stop, keep the claim, tell the user.
            die("cannot publish result safely: this folder's filesystem does not support hard links (%s). "
                "Stopped without saving; the claim is kept. Move the work folder to a local disk and ask the user before retrying." % type(ex).__name__, 4)
    finally:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            pass
    try:
        os.remove(w.cpath(vid, s, e))
    except FileNotFoundError:
        pass
    return None


def cmd_record(w, a):
    text = ""
    if a.text_file:
        with open(a.text_file) as f:
            text = f.read()
    m = record_result(w, a.video, a.start, a.end, a.status, a.http_status, a.tokens, a.model, a.note, text)
    if m:
        die(m, 3 if "refus" in m or "blocked" in m or "saved" in m else 2)
    print("recorded", w.wname(a.video, a.start, a.end), a.status)
    if a.status != "ok":
        print("BLOCKED: stop and ask the user before any retry, rephrase or route change")


def cmd_unblock(w, a):
    if not a.approval_note or not a.approval_note.strip():
        die("unblock needs --approval-note describing the user's approval for this exact case")
    p = w.rpath(a.video, a.start, a.end)
    if not os.path.exists(p):
        die("no result to unblock")
    r = read_json(p, "result file")
    if isinstance(r, dict) and r.get("status") == "ok":
        die("a saved success is never unblocked")
    os.makedirs(os.path.join(w.res_dir, "archive"), exist_ok=True)
    os.replace(p, os.path.join(w.res_dir, "archive", w.wname(a.video, a.start, a.end) + ".approved-retry.json"))
    with open(os.path.join(w.res_dir, "approvals.log"), "a") as f:
        f.write("%s\t%s\n" % (w.wname(a.video, a.start, a.end), a.approval_note.strip()))
    print("window reopened for one approved attempt")


def cmd_check(w, a):
    inv = w.load()
    ids = {v["video_id"]: v for v in inv["videos"]}
    problems = []
    if os.path.isdir(w.res_dir):
        for fn in sorted(os.listdir(w.res_dir)):
            if fn.endswith(".claim"):
                problems.append("%s: claim present (in progress, or stale after a crash; release only if no worker is running)" % fn)
                continue
            if fn.endswith(".tmp"):
                problems.append("%s: leftover temp file from an interrupted write" % fn)
                continue
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(w.res_dir, fn)) as f:
                    r = json.load(f)
            except (ValueError, OSError):
                problems.append("%s: corrupt or unreadable" % fn)
                continue
            if not isinstance(r, dict):
                problems.append("%s: not a JSON object" % fn)
                continue
            vid, st, en = r.get("video_id"), r.get("start"), r.get("end")
            if not (isinstance(vid, str) and ID_RE.match(vid) and isinstance(st, int) and isinstance(en, int)
                    and not isinstance(st, bool) and not isinstance(en, bool) and 0 <= st < en):
                problems.append("%s: invalid video_id or window in contents" % fn)
                continue
            if fn != "%s__%d-%d.json" % (vid, st, en):
                problems.append("%s: name does not match contents" % fn)
            v = ids.get(vid)
            if v is None:
                problems.append("%s: video not in inventory" % fn)
            elif (st, en) not in w.window_list(v):
                problems.append("%s: window not in plan" % fn)
            bad = result_problem(r, vid, st, en)
            if bad:
                problems.append("%s: %s" % (fn, bad))
    print(json.dumps({"problems": problems}, indent=2))
    sys.exit(1 if problems else 0)


def coverage(w):
    inv = w.load()
    per, counts = [], {"done": 0, "partial": 0, "remaining": 0, "blocked": 0, "no_windows": 0}
    for v in inv["videos"]:
        wl = w.window_list(v)
        sts = [w.state(v["video_id"], s, e) for s, e in wl]
        if not wl:
            k = "no_windows"
        elif "blocked" in sts:
            k = "blocked"
        elif all(s == "done" for s in sts):
            k = "done"
        elif any(s == "done" for s in sts):
            k = "partial"
        else:
            k = "remaining"
        counts[k] += 1
        per.append({"video_id": v["video_id"], "visual_windows_done": sts.count("done"),
                    "windows": len(wl), "visual": k})
    return {"unique_videos": len(inv["videos"]), "visual_pass": counts, "videos": per,
            "note": "API/visual coverage only. Written, reviewed and package-ready counts come from the inventory stages, not from result files."}


def cmd_coverage(w, a):
    c = coverage(w)
    if a.write:
        lines = ["# COVERAGE_MANIFEST (generated)", "",
                 "Unique videos: %d" % c["unique_videos"], ""]
        for k, n in c["visual_pass"].items():
            lines.append("- visual pass %s: %d" % (k, n))
        lines += ["", c["note"], "", "| video_id | windows done | windows | visual |", "|---|---|---|---|"]
        for p in c["videos"]:
            lines.append("| %s | %d | %d | %s |" % (p["video_id"], p["visual_windows_done"], p["windows"], p["visual"]))
        with open(a.write, "w") as f:
            f.write("\n".join(lines) + "\n")
    print(json.dumps({k: c[k] for k in ("unique_videos", "visual_pass", "note")}, indent=2))


def cmd_credential_check(w, a):
    name = w.cfg.get("key_env_name", "")
    if not name:
        print("no key_env_name configured: no credential route set up")
        sys.exit(1)
    print("%s: %s" % (name, "present" if os.environ.get(name) else "absent"))
    sys.exit(0 if os.environ.get(name) else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(f=cmd_init)
    s = sub.add_parser("import"); s.add_argument("--file", required=True); s.set_defaults(f=cmd_import)
    sub.add_parser("rank").set_defaults(f=cmd_rank)
    s = sub.add_parser("windows"); s.add_argument("--video"); s.set_defaults(f=cmd_windows)
    s = sub.add_parser("next"); s.add_argument("--limit", type=int, default=1); s.set_defaults(f=cmd_next)
    for name, fn in (("claim", cmd_claim), ("release", cmd_release), ("record", cmd_record), ("unblock", cmd_unblock)):
        s = sub.add_parser(name)
        s.add_argument("--video", required=True)
        s.add_argument("--start", type=int, required=True)
        s.add_argument("--end", type=int, required=True)
        if name == "claim":
            s.add_argument("--owner", default="")
        if name == "record":
            s.add_argument("--status", required=True)
            s.add_argument("--http-status", type=int, default=0)
            s.add_argument("--tokens", type=int, default=0)
            s.add_argument("--model", default="")
            s.add_argument("--note", default="")
            s.add_argument("--text-file")
        if name == "unblock":
            s.add_argument("--approval-note")
        s.set_defaults(f=fn)
    sub.add_parser("check").set_defaults(f=cmd_check)
    s = sub.add_parser("coverage"); s.add_argument("--write"); s.set_defaults(f=cmd_coverage)
    sub.add_parser("credential-check").set_defaults(f=cmd_credential_check)
    a = p.parse_args()
    try:
        a.f(Work(a.workdir), a)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as ex:  # controlled stop, never a silent wrong count
        die("unexpected %s: stopping without changing anything further" % type(ex).__name__)


if __name__ == "__main__":
    main()
