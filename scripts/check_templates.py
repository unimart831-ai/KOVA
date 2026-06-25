"""Find render() template paths that are missing on disk."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
renders: set[str] = set()
for p in (ROOT / "apps").rglob("*.py"):
    text = p.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r'render\(request,\s*["\']([^"\']+)["\']', text):
        renders.add(m.group(1))

missing = []
for t in sorted(renders):
    path = ROOT / "templates" / t.replace("/", os.sep)
    if not path.exists():
        missing.append(t)

for t in missing:
    print(t)
print(f"\n{len(missing)} missing of {len(renders)} referenced")
