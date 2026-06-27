"""Replace gradient Tailwind classes with solid brand surfaces in templates."""
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

GRADIENT_REPLACEMENTS = [
    (r"bg-gradient-to-br from-growth-500 to-growth-600", "bg-growth-500"),
    (r"bg-gradient-to-br from-kova-800 to-kova-700", "bg-kova-800"),
    (r"bg-gradient-to-br from-kova-500 to-kova-500", "bg-kova-800"),
    (r"bg-gradient-to-br from-kova-50 to-white dark:from-kova-950/50 dark:to-gray-900", "bg-kova-50 dark:bg-kova-950/30"),
    (r"bg-gradient-to-br from-kova-50/80 to-white dark:from-kova-950/40 dark:to-gray-900", "bg-kova-50 dark:bg-kova-950/30"),
    (r"bg-gradient-to-br from-kova-50/60 to-white dark:from-kova-950/30 dark:to-gray-900", "bg-kova-50 dark:bg-kova-950/30"),
    (r"bg-gradient-to-br from-growth-50/60 to-white dark:from-growth-950/20 dark:to-gray-900", "bg-growth-50 dark:bg-growth-950/20"),
    (r"bg-gradient-to-r from-kova-400 via-kova-400 to-pink-400", "bg-growth-500"),
    (r"bg-gradient-to-r from-kova-500 to-growth-500", "bg-growth-500"),
    (r"bg-gradient-to-br from-kova-500 to-growth-500", "bg-kova-800"),
    (r"bg-gradient-to-br from-violet-50 to-white dark:from-violet-950/20 dark:to-gray-900", "bg-kova-50 dark:bg-kova-950/20"),
]


def main():
    for dirpath, _, filenames in os.walk(ROOT):
        for fn in filenames:
            if not fn.endswith(".html"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            orig = content
            for pattern, repl in GRADIENT_REPLACEMENTS:
                content = re.sub(pattern, repl, content)
            if content != orig:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(content)
                print(path)


if __name__ == "__main__":
    main()
