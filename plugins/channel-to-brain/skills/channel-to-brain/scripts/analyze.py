#!/usr/bin/env python3
"""Channel to Brain: controlled model-call queue (for Claude Code or any shell client).

Python 3 standard library only. Calls ONE configured HTTPS endpoint, one window at a
time, in ranked order, using ctb.py's claim and record rules.

Safety rules built in:
- Dry run is the default. A live call needs --confirm-live (the user's go-ahead).
- No automatic retry. Any non-success (HTTP error, timeout, empty text, filter reason)
  is recorded as blocked and the run STOPS. Only the user can approve a retry
  (ctb.py unblock --approval-note ...). While any window is blocked, a new run refuses to start
  unless the user has accepted the gaps (--user-accepted-blocks).
- The API key is read from the environment variable named in the config, only at
  call time. It is never printed, logged or written. Errors are scrubbed of it.
- HTTPS only, to a host listed in allowed_hosts (default: generativelanguage.googleapis.com),
  checked before the key is attached. Redirects are never followed, so the key cannot
  be sent to another origin. All config is validated before any network call.
- Success needs HTTP 200, non-empty text and finishReason exactly STOP; anything
  else, including malformed JSON, is blocked.
- One request at a time, spaced by min_seconds_between_calls, at most max_calls_per_run.
- Nothing is hardcoded: model, endpoint, header, prompt file and request body come
  from ctb.config.json under "analyze". There is no default model.

Config (ctb.config.json), example in the README, all keys under "analyze":
  model, endpoint_template (uses {model}), key_env_name, auth_header,
  prompt_file, fps, video_url_template (uses {video_id}), allowed_hosts, max_calls_per_run,
  min_seconds_between_calls, timeout_seconds, request_template (optional JSON)

Usage: python3 analyze.py --workdir DIR run [--limit N] [--confirm-live] [--user-accepted-blocks TEXT]
"""
import argparse, copy, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctb  # noqa: E402

# Default body, checked 2026-11-25 against https://ai.google.dev/api/generate-content :
# Part.fileData.fileUri (required) with optional mimeType (omitted: "video/*" is not an
# IANA type), and the sibling Part.videoMetadata {startOffset, endOffset: strings,
# fps: number in (0, 24]}. Auth header x-goog-api-key is shown in the official REST
# quickstart https://ai.google.dev/gemini-api/docs/quickstart . Re-check before the
# first live call (SKILL 7.4); override via request_template.
DEFAULT_BODY = {
    "contents": [{"parts": [
        {"fileData": {"fileUri": "{video_url}"},
         "videoMetadata": {"startOffset": "{start}s", "endOffset": "{end}s", "fps": "{fps}"}},
        {"text": "{prompt}"}]}],
}
DEFAULT_ALLOWED_HOSTS = ["generativelanguage.googleapis.com"]
PLACEHOLDERS = ("{video_url}", "{start}", "{end}", "{fps}", "{prompt}", "{model}", "{video_id}")
DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_HEADER = "x-goog-api-key"


def fill(node, vals):
    if isinstance(node, dict):
        return {k: fill(v, vals) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, vals) for v in node]
    if isinstance(node, str):
        if node == "{fps}":
            return float(vals["fps"])
        for k, v in vals.items():
            node = node.replace("{%s}" % k, str(v))
        return node
    return node


def scrub(text, key):
    return text.replace(key, "[key]") if key else text


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # a redirect is returned as an error; the key is never sent elsewhere


def check_endpoint(url, allowed_hosts):
    """Return a problem string, or None. Must pass before any credential is attached."""
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https":
        return "endpoint must use https"
    if u.username or u.password:
        return "endpoint must not contain credentials"
    if u.port not in (None, 443):
        return "endpoint port must be 443"
    if (u.hostname or "").lower() not in [h.lower() for h in allowed_hosts]:
        return "endpoint host %r is not in allowed_hosts" % (u.hostname,)
    return None


def default_transport(url, headers, body, timeout, allowed_hosts=None):
    prob = check_endpoint(url, allowed_hosts or DEFAULT_ALLOWED_HOSTS)
    if prob:
        raise ValueError(prob)
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def classify(status, raw):
    """-> (record_status, text, tokens, note). Never raises.
    Conservative rule: success only if HTTP 200, a JSON object, a non-empty candidates list,
    non-empty text, and finishReason exactly "STOP". Anything else is blocked:
    "error" for transport or schema problems, "filter" for a model or safety stop."""
    try:
        if status != 200:
            return "error", "", 0, "HTTP %s" % status
        j = json.loads(raw)
        if not isinstance(j, dict):
            return "error", "", 0, "malformed response: not a JSON object"
        um = j.get("usageMetadata")
        tokens = um.get("totalTokenCount", 0) if isinstance(um, dict) else 0
        tokens = tokens if isinstance(tokens, int) else 0
        pf = j.get("promptFeedback")
        block = pf.get("blockReason") if isinstance(pf, dict) else None
        if block:
            return "filter", "", tokens, "prompt blocked: %s" % block
        cands = j.get("candidates")
        if not isinstance(cands, list) or not cands or not isinstance(cands[0], dict):
            return "filter", "", tokens, "no candidates"
        c = cands[0]
        content = c.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if parts is not None and not isinstance(parts, list):
            return "error", "", tokens, "malformed response: parts is not a list"
        text = "".join(p["text"] for p in (parts or []) if isinstance(p, dict) and isinstance(p.get("text"), str))
        fin = c.get("finishReason")
        if fin != "STOP":
            return "filter", "", tokens, "not a normal finish, finishReason=%s" % (fin if fin else "missing")
        if not text.strip():
            return "filter", "", tokens, "empty text with finishReason=STOP"
        return "ok", text, tokens, ""
    except (ValueError, TypeError, KeyError, AttributeError) as ex:
        return "error", "", 0, "malformed response (%s)" % type(ex).__name__


def validate_config(w, cfg):
    """All checks run before any network call or credential use. Returns a list of problems."""
    P = []
    for need in ("model", "key_env_name", "prompt_file"):
        if not isinstance(cfg.get(need), str) or not cfg.get(need):
            P.append("analyze.%s is not set (no default is assumed)" % need)
    if isinstance(cfg.get("model"), str) and cfg["model"] and not re.fullmatch(r"[A-Za-z0-9._-]+", cfg["model"]):
        P.append("analyze.model has characters outside letters, digits, . _ -")
    if isinstance(cfg.get("key_env_name"), str) and cfg["key_env_name"] and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cfg["key_env_name"]):
        P.append("analyze.key_env_name must be an environment variable name, not a key")
    pf = cfg.get("prompt_file")
    if isinstance(pf, str) and pf:
        full = pf if os.path.isabs(pf) else os.path.join(w.dir, pf)
        ok = False
        if os.path.isfile(full):
            with open(full) as fh:
                ok = bool(fh.read().strip())
        if not ok:
            P.append("prompt_file %s is missing or empty" % pf)
    fps = cfg.get("fps", 0.2)
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not (0 < fps <= 24):
        P.append("analyze.fps must be a number in (0, 24]")
    for k, lo in (("max_calls_per_run", 1), ("window_seconds", 1)):
        val = cfg.get(k) if k != "window_seconds" else w.cfg.get("window_seconds")
        if val is not None and (isinstance(val, bool) or not isinstance(val, int) or val < lo):
            P.append("%s must be an integer >= %d" % (k, lo))
    for k, lo in (("min_seconds_between_calls", 0), ("timeout_seconds", 1)):
        val = cfg.get(k)
        if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float)) or val < lo):
            P.append("analyze.%s must be a number >= %s" % (k, lo))
    hosts = cfg.get("allowed_hosts", DEFAULT_ALLOWED_HOSTS)
    if not isinstance(hosts, list) or not hosts or not all(isinstance(h, str) and h for h in hosts):
        P.append("analyze.allowed_hosts must be a non-empty list of host names")
        hosts = DEFAULT_ALLOWED_HOSTS
    ep_t = cfg.get("endpoint_template", DEFAULT_ENDPOINT)
    if isinstance(cfg.get("model"), str) and cfg.get("model") and isinstance(ep_t, str):
        try:
            prob = check_endpoint(ep_t.format(model=cfg["model"]), hosts)
        except (KeyError, IndexError, ValueError):
            prob = "endpoint_template has an unknown placeholder"
        if prob:
            P.append(prob)
    else:
        P.append("endpoint_template must be a string")
    vurl = cfg.get("video_url_template", "https://www.youtube.com/watch?v={video_id}")
    if not isinstance(vurl, str) or not vurl.startswith("https://") or "{video_id}" not in vurl:
        P.append("video_url_template must be an https URL containing {video_id}")
    bt = cfg.get("request_template", DEFAULT_BODY)
    if not isinstance(bt, dict):
        P.append("request_template must be a JSON object")
    else:
        try:
            sample = fill(copy.deepcopy(bt), {"video_url": "https://example.invalid/v", "start": 0, "end": 1, "fps": 1, "prompt": "p"})
            dumped = json.dumps(sample)
            left = [x for x in PLACEHOLDERS if x in dumped]
            if left:
                P.append("request_template leaves unfilled placeholders: %s" % ", ".join(left))
            if "{prompt}" not in json.dumps(bt):
                P.append("request_template does not contain {prompt}")
        except (TypeError, ValueError) as ex:
            P.append("request_template cannot be built: %s" % type(ex).__name__)
    return P


def run(w, limit=None, confirm_live=False, transport=None, sleep=time.sleep, env=None, out=print, accepted_blocks_note=""):
    env = os.environ if env is None else env
    cfg = w.cfg.get("analyze") or {}
    problems = validate_config(w, cfg)
    if problems:
        for m in problems:
            out("config error: " + m)
        out("Nothing was sent. Fix the config and run again.")
        return 2
    pf = cfg["prompt_file"] if os.path.isabs(cfg["prompt_file"]) else os.path.join(w.dir, cfg["prompt_file"])
    with open(pf) as f:
        prompt = f.read().strip()
    hosts = cfg.get("allowed_hosts", DEFAULT_ALLOWED_HOSTS)
    endpoint = cfg.get("endpoint_template", DEFAULT_ENDPOINT).format(model=cfg["model"])
    header = cfg.get("auth_header", DEFAULT_HEADER)
    body_t = cfg.get("request_template", DEFAULT_BODY)
    vurl = cfg.get("video_url_template", "https://www.youtube.com/watch?v={video_id}")
    fps = cfg.get("fps", 0.2)
    cap = int(cfg.get("max_calls_per_run", 5))
    if limit:
        cap = min(cap, limit)
    gap = float(cfg.get("min_seconds_between_calls", 6))
    timeout = float(cfg.get("timeout_seconds", 120))
    key = env.get(cfg["key_env_name"], "")
    if confirm_live and not key:
        out("credential error: environment variable %s is not set" % cfg["key_env_name"])
        return 2
    if transport is None:
        def transport(url, headers, body, tmo):
            return default_transport(url, headers, body, tmo, hosts)
    inv = w.load()
    blocked = [(v["video_id"], a, b) for v in inv["videos"] for a, b in w.window_list(v)
               if w.state(v["video_id"], a, b) == "blocked"]
    if blocked and not accepted_blocks_note.strip():
        out("STOPPED: %d window(s) are blocked and need the user's decision (approve a retry with ctb.py unblock, "
            "or the user accepts the gap and you pass --user-accepted-blocks with the user's words)." % len(blocked))
        return 1
    if blocked:
        with open(os.path.join(w.res_dir, "approvals.log"), "a") as f:
            f.write("accepted-gaps\t%s\t%s\n" % (len(blocked), accepted_blocks_note.strip()))
    calls = 0
    for v in inv["videos"]:
        for s, e in w.window_list(v):
            vid = v["video_id"]
            if calls >= cap:
                out("stopped at max_calls_per_run=%d" % cap)
                return 0
            if w.state(vid, s, e) != "missing":
                continue
            vals = {"video_url": vurl.format(video_id=vid), "start": s, "end": e, "fps": fps, "prompt": prompt}
            body = fill(copy.deepcopy(body_t), vals)
            if not confirm_live:
                out("DRY RUN %s %d-%d: POST %s header %s=[key] body=%s" % (vid, s, e, endpoint, header, json.dumps(body)))
                calls += 1
                continue
            m = ctb.claim_window(w, vid, s, e, "analyze")
            if m:
                out("skip %s %d-%d: %s" % (vid, s, e, m))
                continue
            rs, text, tokens, note, status = "error", "", 0, "unexpected failure", 0
            try:
                if calls:
                    sleep(gap)
                try:
                    status, raw = transport(endpoint, {header: key, "Content-Type": "application/json"}, body, timeout)
                    rs, text, tokens, note = classify(status, scrub(str(raw), key))
                except Exception as ex:  # timeout, network error or refused endpoint: block, never retry
                    status = 0
                    rs, text, tokens = "error", "", 0
                    note = "network error or timeout: %s" % scrub(type(ex).__name__, key)
                calls += 1
            finally:
                # always settle the claim: record the outcome, or release it so nothing stays stuck
                msg = ctb.record_result(w, vid, s, e, rs, status, tokens, cfg["model"], scrub(note, key), text)
                if msg:
                    ctb.record_result(w, vid, s, e, "error", status, 0, cfg["model"], "record refused: " + scrub(msg, key))
                if os.path.exists(w.cpath(vid, s, e)):
                    os.remove(w.cpath(vid, s, e))
            if rs != "ok":
                out("BLOCKED %s %d-%d: %s. Stopped. Ask the user before any retry." % (vid, s, e, note))
                return 1
            out("ok %s %d-%d tokens=%d" % (vid, s, e, tokens))
    out("no missing windows left" if confirm_live else "dry run complete (no calls made)")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--limit", type=int)
    r.add_argument("--user-accepted-blocks", default="", help="the user's own words accepting the existing blocked windows as gaps")
    r.add_argument("--confirm-live", action="store_true", help="make real calls; needs the user's go-ahead")
    a = p.parse_args()
    sys.exit(run(ctb.Work(a.workdir), a.limit, a.confirm_live, accepted_blocks_note=a.user_accepted_blocks))


if __name__ == "__main__":
    main()
