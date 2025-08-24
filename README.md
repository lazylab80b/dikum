# DIKUM
Dialog Integrated Komawari Utility for Japanese-style Manga 

## Ledger tool (minimal CSV edition)
Run:
```bash
python ledgertool/ledger_cli.py index /path/to/pages -o /path/to/pages/ledger.csv
python ledgertool/ledger_cli.py audit -l /path/to/pages/ledger.csv -d /path/to/pages
python ledgertool/ledger_cli.py export -l /path/to/pages/ledger.csv -o bundle.zip
```

Bundle single-file for GPTs:
```bash
python scripts/bundle.py
# => GPTs/ledger.py
```

---
## This line is added and comitted by AI itself
