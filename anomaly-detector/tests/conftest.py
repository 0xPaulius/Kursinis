"""
Konfigūracija anomaly-detector testams.
Pridedame anomaly-detector/ į sys.path kad būtų galima importuoti `detector`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
