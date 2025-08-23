# SPDX-License-Identifier: MIT
"""
ledger_core.py — 台帳管理ツールのコアロジック（CSVベース最小土台）
"""
from __future__ import annotations

import csv
import json
import os
import zipfile
from typing import Iterable, List, Set, Tuple

ALLOWED_IMAGE_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}


def list_images(directory: str) -> List[str]:
    if not os.path.isdir(directory):
        return []
    files: List[str] = []
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() in ALLOWED_IMAGE_EXTENSIONS:
            files.append(name)
    files.sort()
    return files


def write_ledger_csv(file_path: str, filenames: Iterable[str]) -> None:
    d = os.path.dirname(file_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Page", "Filename"])
        for i, fn in enumerate(filenames, start=1):
            w.writerow([i, fn])


def read_ledger_csv(file_path: str) -> List[Tuple[int, str]]:
    rows: List[Tuple[int, str]] = []
    with open(file_path, "r", newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        _ = next(r, None)  # header
        for row in r:
            if not row:
                continue
            try:
                page = int(row[0])
            except Exception:
                continue
            rows.append((page, row[1]))
    return rows


def verify_ledger(entries: List[Tuple[int, str]], images_dir: str) -> Tuple[List[str], List[str]]:
    listed = {fn for _, fn in entries}
    actual = set(list_images(images_dir))
    missing = sorted([fn for fn in listed if fn not in actual])
    extra = sorted([fn for fn in actual if fn not in listed])
    return missing, extra


def create_zip_from_ledger(images_dir: str, entries: List[Tuple[int, str]], out_zip: str) -> int:
    d = os.path.dirname(out_zip)
    if d:
        os.makedirs(d, exist_ok=True)
    count = 0
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for _, fn in entries:
            src = os.path.join(images_dir, fn)
            if os.path.isfile(src):
                zf.write(src, arcname=fn)
                count += 1
    return count


def run_command(argv: List[str]) -> int:
    if not argv:
        print("ERROR " + json.dumps({"code": "no_command"}))
        return 1
    cmd, *rest = argv
    try:
        if cmd == "index":
            if not rest:
                print(
                    "ERROR "
                    + json.dumps({"code": "bad_args", "hint": "index <dir> [-o ledger.csv]"})
                )
                return 1
            directory = rest[0]
            out = None
            if "-o" in rest:
                i = rest.index("-o")
                out = rest[i + 1] if i + 1 < len(rest) else None
            if out is None:
                out = os.path.join(directory, "ledger.csv")
            files = list_images(directory)
            write_ledger_csv(out, files)
            print("INFO " + json.dumps({"indexed": len(files), "ledger": out}))
            return 0

        elif cmd == "audit":
            if "-l" not in rest:
                print(
                    "ERROR "
                    + json.dumps(
                        {"code": "bad_args", "hint": "audit -l ledger.csv [-d images_dir]"}
                    )
                )
                return 1
            li = rest.index("-l")
            ledger = rest[li + 1] if li + 1 < len(rest) else None
            if ledger is None or not os.path.isfile(ledger):
                print("ERROR " + json.dumps({"code": "ledger_not_found", "path": ledger}))
                return 1
            if "-d" in rest:
                di = rest.index("-d")
                images_dir = rest[di + 1] if di + 1 < len(rest) else None
            else:
                images_dir = os.path.dirname(ledger) or "."
            entries = read_ledger_csv(ledger)
            missing, extra = verify_ledger(entries, images_dir)
            print("AUDIT " + json.dumps({"missing": missing, "extra": extra}))
            return 0

        elif cmd == "export":
            if "-l" not in rest or "-o" not in rest:
                print(
                    "ERROR "
                    + json.dumps(
                        {
                            "code": "bad_args",
                            "hint": "export -l ledger.csv -o out.zip [-d images_dir]",
                        }
                    )
                )
                return 1
            li = rest.index("-l")
            oi = rest.index("-o")
            ledger = rest[li + 1] if li + 1 < len(rest) else None
            outzip = rest[oi + 1] if oi + 1 < len(rest) else None
            if ledger is None or not os.path.isfile(ledger):
                print("ERROR " + json.dumps({"code": "ledger_not_found", "path": ledger}))
                return 1
            if outzip is None:
                print(
                    "ERROR "
                    + json.dumps({"code": "bad_args", "hint": "export -l ledger.csv -o out.zip"})
                )
                return 1
            if "-d" in rest:
                di = rest.index("-d")
                images_dir = rest[di + 1] if di + 1 < len(rest) else None
            else:
                images_dir = os.path.dirname(ledger) or "."
            entries = read_ledger_csv(ledger)
            n = create_zip_from_ledger(images_dir, entries, outzip)
            print("INFO " + json.dumps({"exported": n, "zip": outzip}))
            return 0

        elif cmd == "import":
            print("INFO " + json.dumps({"msg": "import not implemented yet"}))
            return 0

        else:
            print("ERROR " + json.dumps({"code": "unknown_command", "cmd": cmd}))
            return 1
    except BrokenPipeError:
        return 0
