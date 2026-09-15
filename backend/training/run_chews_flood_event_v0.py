"""
Build chews_flood_event_v0 observation registry.

Does NOT train, create rainfall labels, modify weather history, or touch production CHEWS.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from training.run_flood_event_acquisition import main  # noqa: E402

if __name__ == "__main__":
    main()
