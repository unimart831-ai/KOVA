"""One-off: replace legacy purple (#7c3aed) with Kova brand solids."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REPLACEMENTS = [
    ("background-color:#10B981", "background-color:#10B981"),
    ("{% block header_bg %}#1E3A8A", "{% block header_bg %}#1E3A8A"),
    ("var(--brand-accent, #1E3A8A)", "var(--brand-accent, #1E3A8A)"),
    ("border-left:4px solid #1E3A8A", "border-left:4px solid #1E3A8A"),
    ("background-color:#EFF6FF", "background-color:#EFF6FF"),
    ("color: #1E3A8A", "color: #1E3A8A"),
    ("color:#1E3A8A", "color:#1E3A8A"),
    ('default="#10B981"', 'default="#10B981"'),
    ("'#1E3A8A'", "'#1E3A8A'"),
    ('"#1E3A8A"', '"#1E3A8A"'),
    ("#EFF6FF", "#EFF6FF"),
    ("else %}#10B981", "else %}#10B981"),
    ("#EFF6FF", "#EFF6FF"),
]

EXTS = {".html", ".py", ".js", ".css"}
SKIP = {"node_modules", ".git", "venv", ".venv"}


def main():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for fn in filenames:
            if os.path.splitext(fn)[1] not in EXTS:
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            orig = content
            for old, new in REPLACEMENTS:
                content = content.replace(old, new)
            if content != orig:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(content)
                print(path)


if __name__ == "__main__":
    main()
