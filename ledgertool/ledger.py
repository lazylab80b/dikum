# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, argparse, os

sys.path.insert(0, os.path.dirname(__file__))
import ledger_core as core  # noqa: E402

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index")
    p_index.add_argument("directory")
    p_index.add_argument("-o","--output")

    p_export = sub.add_parser("export")
    p_export.add_argument("-l","--ledger", required=True)
    p_export.add_argument("-o","--output", required=True)
    p_export.add_argument("-d","--dir")

    p_audit = sub.add_parser("audit")
    p_audit.add_argument("-l","--ledger", required=True)
    p_audit.add_argument("-d","--dir")

    p_import = sub.add_parser("import")

    args, unknown = ap.parse_known_args(argv)

    cmdline = [args.cmd]
    if args.cmd == "index":
        cmdline += [args.directory]
        if args.output: cmdline += ["-o", args.output]
    elif args.cmd == "export":
        cmdline += ["-l", args.ledger, "-o", args.output]
        if args.dir: cmdline += ["-d", args.dir]
    elif args.cmd == "audit":
        cmdline += ["-l", args.ledger]
        if args.dir: cmdline += ["-d", args.dir]
    elif args.cmd == "import":
        pass
    cmdline += unknown

    try:
        rc = core.run_command(cmdline)
    except BrokenPipeError:
        rc = 0
    sys.exit(rc)

if __name__ == "__main__":
    main()
