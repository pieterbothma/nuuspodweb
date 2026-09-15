import sys
from pathlib import Path

# Ensure `data/` (this file's directory) is on sys.path so tests can
# `import lib.xxx` regardless of pytest's import-mode rootdir detection.
sys.path.insert(0, str(Path(__file__).parent))
