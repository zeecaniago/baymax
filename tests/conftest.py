from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DATA_DIRECTORY = tempfile.TemporaryDirectory(prefix="baymax-tests-")
os.environ["BAYMAX_DB_PATH"] = str(Path(_TEST_DATA_DIRECTORY.name) / "baymax.db")
