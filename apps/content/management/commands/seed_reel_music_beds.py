"""Generate silent MP3 placeholders for all catalog reel music beds."""

import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.content.reel_music import load_music_catalog


class Command(BaseCommand):
    help = "Create FFmpeg silent MP3 placeholders for reel music catalog tracks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--duration",
            type=int,
            default=30,
            help="Seconds per placeholder track (default: 30)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing MP3 files",
        )

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR) / "static" / "audio" / "reel-beds"
        duration = options["duration"]
        force = options["force"]
        created = 0
        skipped = 0

        for track in load_music_catalog():
            rel = track.get("file") or ""
            if not rel:
                continue
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_file() and not force:
                skipped += 1
                continue
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-t", str(duration),
                "-c:a", "libmp3lame", "-q:a", "4",
                str(dest),
            ]
            subprocess.run(cmd, check=True)
            created += 1
            self.stdout.write(f"Created {dest.relative_to(settings.BASE_DIR)}")

        self.stdout.write(
            self.style.SUCCESS(f"Done — {created} created, {skipped} skipped.")
        )
