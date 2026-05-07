from __future__ import annotations

import sys
from pathlib import Path


repo_src = Path(__file__).resolve().parents[3] / "src"
if repo_src.exists():
    sys.path.insert(0, str(repo_src))

from folio_scribe.futu_snapshot import main


if __name__ == "__main__":
    raise SystemExit(main())
