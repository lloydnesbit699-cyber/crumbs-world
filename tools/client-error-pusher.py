"""Crumbs World client-error pusher (v6.4.11 telemetry, Harley side).

Reads logs/client-errors.jsonl (written by /api/jslog), groups by the
server-computed signature, and pushes one GitHub Issue per signature.

DEFAULT IS DRY-RUN: prints what would be created or updated, calls
nothing, and never touches the network.

LIVE MODE (--live) requires, on Harley only:
  CRUMBS_GITHUB_TOKEN  -- a GitHub token, set by Lloyd on Harley,
                          never pasted in chat, never printed here.
  CRUMBS_GITHUB_REPO   -- optional, default lloydnesbit699-cyber/crumbs-world

The token is read from the environment only. It is never printed,
never logged, and never stored by this script. If it ever appears in
chat or in a pasted log, treat it as burned: revoke it on GitHub and
make a new one.

GitHub bodies are sanitized: no player names, no keys, no full stack,
no ?key= values, no org ids. Only version, count, first/last seen,
message, source basename, and line.

Usage:
  python tools/client-error-pusher.py [--live] [--repo owner/name]
      [--log logs/client-errors.jsonl] [--state logs/client-errors-pushed.json]
"""
import argparse, json, os, re, sys, urllib.request, urllib.error
from collections import Counter, defaultdict
from datetime import datetime

DEFAULT_REPO = "lloydnesbit699-cyber/crumbs-world"

def sanitize(text):
    t = str(text or "")
    t = re.sub(r"[?&]key=[^&\s]+", "?key=[redacted]", t)
    t = re.sub(r"org_[A-Za-z0-9_]+", "org_[redacted]", t)
    t = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted]", t)
    return t[:300]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--repo", default=os.environ.get("CRUMBS_GITHUB_REPO", DEFAULT_REPO))
    ap.add_argument("--log", default="logs/client-errors.jsonl")
    ap.add_argument("--state", default="logs/client-errors-pushed.json")
    args = ap.parse_args()

    if not os.path.exists(args.log):
        print(f"no errors logged yet ({args.log} does not exist)")
        return 0

    groups = {}
    # utf-8-sig: tolerates a BOM if the log was ever written by PowerShell.
    with open(args.log, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            sig = rec.get("signature") or "unknown"
            g = groups.setdefault(sig, {"count": 0, "first": rec.get("ts", ""),
                                        "last": rec.get("ts", ""),
                                        "version": rec.get("version", ""),
                                        "msg": rec.get("msg", ""),
                                        "src": rec.get("src", ""),
                                        "line": rec.get("line", "")})
            g["count"] += 1
            if rec.get("ts", ""):
                if not g["first"] or rec["ts"] < g["first"]:
                    g["first"] = rec["ts"]
                if rec["ts"] > g["last"]:
                    g["last"] = rec["ts"]

    if not groups:
        print("no errors logged yet")
        return 0

    state = {}
    if os.path.exists(args.state):
        try:
            with open(args.state, encoding="utf-8-sig") as f:
                state = json.load(f)
        except Exception:
            state = {}

    if not args.live:
        for sig, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
            prev = state.get(sig, {})
            action = "would create issue" if "issue" not in prev else (
                "would update issue" if prev.get("count", 0) < g["count"] else "already pushed, no change")
            print(f"{sig} x{g['count']} v{g['version']} {action}: {sanitize(g['msg'])[:80]} @ {os.path.basename(str(g['src']))}:{g['line']}")
        print(f"DRY-RUN: {len(groups)} signature(s), no GitHub calls made.")
        return 0

    token = os.environ.get("CRUMBS_GITHUB_TOKEN", "")
    if not token:
        print("LIVE mode needs CRUMBS_GITHUB_TOKEN set on Harley. It is not set.")
        print("Stop here: create the token on GitHub (see the creation prompt),")
        print("set it on Harley yourself, never paste it in chat, then re-run with --live.")
        return 3

    def gh(method, url, payload=None):
        req = urllib.request.Request(url, method=method,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json",
                     "User-Agent": "crumbs-error-pusher"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            print(f"GitHub {method} failed ({e.code}): {body}")
            raise SystemExit(2)

    base = f"https://api.github.com/repos/{args.repo}"
    for sig, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
        title = f"[client-error] {sanitize(g['msg'])[:80]}"
        body = (f"Signature: `{sig}`\n\n"
                f"Version: {g['version']}\n"
                f"Reports: {g['count']}\n"
                f"First seen: {g['first']}\n"
                f"Last seen: {g['last']}\n"
                f"Message: {sanitize(g['msg'])}\n"
                f"Source: {os.path.basename(str(g['src']))}:{g['line']}\n\n"
                f"Harley log: logs/client-errors.jsonl (source of truth). "
                f"This issue is the phone notification copy.")
        prev = state.get(sig, {})
        if "issue" not in prev:
            issue = gh("POST", base + "/issues", {"title": title, "body": body, "labels": ["client-error"]})
            state[sig] = {"issue": issue.get("number"), "count": g["count"], "updated": datetime.utcnow().isoformat() + "Z"}
            print(f"{sig}: created issue #{issue.get('number')}")
        elif prev.get("count", 0) < g["count"]:
            gh("POST", f"{base}/issues/{prev['issue']}/comments",
               {"body": f"More reports: now {g['count']} (was {prev.get('count')}), last seen {g['last']}, version {g['version']}."})
            state[sig]["count"] = g["count"]
            state[sig]["updated"] = datetime.utcnow().isoformat() + "Z"
            print(f"{sig}: updated issue #{prev['issue']} (count {g['count']})")
        else:
            print(f"{sig}: already pushed, no change")

    os.makedirs(os.path.dirname(args.state) or ".", exist_ok=True)
    with open(args.state, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    print(f"LIVE: {len(groups)} signature(s) processed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
