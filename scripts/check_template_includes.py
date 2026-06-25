"""Find {% include %} / {% extends %} paths that are missing on disk."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
refs: set[str] = set()
for p in (ROOT / "templates").rglob("*.html"):
    text = p.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r'{%\s*(?:include|extends)\s+["\']([^"\']+)["\']', text):
        refs.add(m.group(1))

missing = []
for t in sorted(refs):
    path = ROOT / "templates" / t.replace("/", os.sep)
    if not path.exists():
        missing.append(t)

for t in missing:
    print(t)
print(f"\n{len(missing)} missing of {len(refs)} referenced")
