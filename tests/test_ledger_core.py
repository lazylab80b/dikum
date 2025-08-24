# SPDX-License-Identifier: MIT
import os, sys
sys.path.insert(0, os.path.abspath("ledgertool"))
import ledger_core as lc  # noqa: E402

def test_list_and_ledger(tmp_path):
    (tmp_path / "p1.png").write_bytes(b"")
    (tmp_path / "p2.JPG").write_bytes(b"")
    (tmp_path / "note.txt").write_text("x")
    (tmp_path / "p3.webp").write_bytes(b"")

    imgs = lc.list_images(str(tmp_path))
    assert imgs == ["p1.png", "p2.JPG", "p3.webp"]

    ledger = tmp_path / "ledger.csv"
    lc.write_ledger_csv(str(ledger), imgs)

    rows = lc.read_ledger_csv(str(ledger))
    assert [fn for _, fn in rows] == imgs

    missing, extra = lc.verify_ledger(rows, str(tmp_path))
    assert not missing and not extra

    (tmp_path / "new.png").write_bytes(b"")
    missing, extra = lc.verify_ledger(rows, str(tmp_path))
    assert extra == ["new.png"]
