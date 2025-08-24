#!/usr/bin/env python3
# scripts/bundle.py  — flat bundler (review==prod)
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import argparse, datetime as dt, hashlib, pathlib, re, sys

def read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def main():
    ap = argparse.ArgumentParser(description="Flatten multiple Python modules into a single file.")
    ap.add_argument("sources", nargs="+", help="Input .py files in the order to concatenate.")
    ap.add_argument("-o", "--out", required=True, help="Output file path (e.g., GPTs/ledger.py)")
    ap.add_argument("--internal-prefix", default="dikum.", help="Prefix of internal imports to comment out (default: dikum.)")
    ap.add_argument("--no-comment-internal", action="store_true", help="Do NOT comment out internal imports")
    ap.add_argument("--title", default="DIKUM Bundle", help="Banner title")
    ap.add_argument("--shebang", default="/usr/bin/env python3", help="Shebang line")
    args = ap.parse_args()

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 内部 import（例: from dikum.foo import Bar）
    pat = re.compile(rf"^\s*from\s+{re.escape(args.internal_prefix)}[\w\.]+\s+import\s+.+$")

    banner = [
        f"#!{args.shebang}",
        "# -----------------------------------------------",
        f"# {args.title} - single-file bundle (review == prod)",
        f"# Built UTC: {dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"# NOTE: Internal imports starting with `{args.internal_prefix}` "
        + ("are kept as-is." if args.no_comment_internal else "were commented out by bundler."),
        "# -----------------------------------------------",
        "",
    ]

    parts = []
    for rel in args.sources:
        src_path = pathlib.Path(rel)
        if not src_path.exists():
            sys.exit(f"[bundle] missing source: {rel}")
        raw = read_text(src_path)
        lines = []
        for line in raw.splitlines():
            if not args.no_comment_internal and pat.match(line):
                lines.append("# " + line)
            else:
                lines.append(line)
        body = "\n".join(lines).rstrip() + "\n"
        header = f"# ── BEGIN {rel} (sha256={sha256(raw)}; lines={len(raw.splitlines())})"
        parts.append("\n".join([header, body, f"# ── END {rel}", ""]))

    out_path.write_text("\n".join(banner + parts), encoding="utf-8")
    print(f"[bundle] wrote {out_path}")

if __name__ == "__main__":
    main()
