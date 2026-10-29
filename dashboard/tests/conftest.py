"""
Dashboard testų konfigūracija: app/ į sys.path ir greiti scrypt parametrai testams.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# scrypt su numatytu N=2**15 testuose lėtas — sumažinam (saugumui įtakos neturi teste).
os.environ.setdefault("SCRYPT_N", "1024")
