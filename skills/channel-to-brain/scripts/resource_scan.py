#!/usr/bin/env python3
"""Secret and private-data check for creator resources before they enter a package.
Standard library only. Usage: resource_scan.py <file-or-folder> [...]
Prints one line per finding (file, line, kind) and never prints the matched value.
Exit 1 when anything is found. A file with findings is stripped or excluded, then scanned again."""
import os
import re
import sys

PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "phone": r"(?<![\w.])\+?\d[\d \-]{9,}\d(?![\w.])",
    "api-key": r"\b(?:sk-|ghp_|github_pat_|AIza|xox[abp]-|AKIA|ya29\.)[\w-]{8,}",
    "private-key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "credential-line": r"(?i)\b(password|passcode|passwd|pwd|bearer|api[_ -]?key|secret|token|access[_ -]?token|login)\b\s*[:=]\s*\S+",
    "url-with-credentials": r"https?://[^/\s:@]+:[^/\s@]+@",
    "session": r"(?i)\b(sessionid|session[_-]?token|set-cookie|cookie)\s*[:=]",
}
# Allowed long tokens are slugs made of words; a long token with digits and mixed case is flagged.
LONG = re.compile(r"\b(?=[A-Za-z0-9_-]{32,}\b)(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{32,}\b")


def scan_text(text):
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for kind, pat in PATTERNS.items():
            if re.search(pat, line):
                found.append((n, kind))
        for m in LONG.finditer(line):
            if "-" not in m.group(0) or re.search(r"[A-Z]", m.group(0)):
                found.append((n, "long-token"))
    return found


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for r, _d, fs in os.walk(p):
                for f in sorted(fs):
                    yield os.path.join(r, f)
        else:
            yield p


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    bad = 0
    for f in files(argv):
        try:
            text = open(f, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            print(f"{f}: not text, exclude or convert before adding")
            bad += 1
            continue
        for n, kind in scan_text(text):
            print(f"{f}:{n}: {kind}")
            bad += 1
    print("clean" if not bad else f"{bad} finding(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
