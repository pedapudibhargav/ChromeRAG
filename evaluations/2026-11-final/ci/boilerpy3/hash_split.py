"""Print an order-stable sha256 digest of a WCXB split (ground truth and HTML files)."""
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
lines = []
for sub in ("ground-truth", "html"):
    for f in sorted((root / sub).iterdir()):
        lines.append(f"{sub}/{f.name}\t{hashlib.sha256(f.read_bytes()).hexdigest()}")
print(len(lines), hashlib.sha256("\n".join(lines).encode()).hexdigest())
