#!/usr/bin/env python3
"""
Discord Image Cleanup Script

Automatically removes junk files (emojis, avatars, small icons) from Discord export.
Runs periodically to keep the folder clean.
"""

from pathlib import Path
import time

IMAGE_DIR = Path(__file__).parent / "discord_history" / "DISCORD_.html_Files"
LOG_FILE = Path(__file__).parent / "logs" / "image_cleanup.log"

# Ensure log directory exists
LOG_FILE.parent.mkdir(exist_ok=True)


def log(message: str):
    """Log to file and print."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def is_junk_file(file_path: Path) -> tuple[bool, str]:
    """
    Determine if a file is junk.

    Returns:
        (is_junk, reason)
    """
    if not file_path.is_file():
        return False, ""

    file_size = file_path.stat().st_size
    file_name = file_path.name.lower()

    # SVG files = emoji reactions
    if file_name.endswith('.svg'):
        return True, "emoji SVG"

    # Very small files (<30KB) = avatars, tiny icons
    if file_size < 30_000:
        return True, f"tiny file ({file_size/1024:.1f}KB)"

    # Small files (30-50KB) with hash patterns = likely avatars
    if 30_000 <= file_size < 50_000:
        # Check for Discord avatar hash pattern: long-hash-short-hash.png
        if '-' in file_name:
            parts = file_name.split('-')
            if len(parts) >= 2 and len(parts[0]) > 25:
                return True, f"avatar pattern ({file_size/1024:.1f}KB)"

    # GIF files < 100KB = likely reaction GIFs
    if file_name.endswith('.gif') and file_size < 100_000:
        return True, f"small GIF ({file_size/1024:.1f}KB)"

    # Files with specific emoji/icon patterns in name
    junk_patterns = ['emoji', 'avatar', 'reaction', 'icon']
    if any(pattern in file_name for pattern in junk_patterns):
        return True, f"junk pattern in name"

    return False, ""


def cleanup():
    """Run cleanup process."""
    if not IMAGE_DIR.exists():
        log(f"❌ Directory not found: {IMAGE_DIR}")
        return

    # Scan for junk files
    files = list(IMAGE_DIR.iterdir())
    junk_files = []

    for file in files:
        is_junk, reason = is_junk_file(file)
        if is_junk:
            junk_files.append((file, reason))

    if not junk_files:
        log(f"✅ No junk files found ({len(files)} total files)")
        return

    # Delete junk files
    deleted_count = 0
    deleted_size = 0

    for file, reason in junk_files:
        try:
            size = file.stat().st_size
            file.unlink()
            deleted_count += 1
            deleted_size += size
        except Exception as e:
            log(f"⚠️  Failed to delete {file.name}: {e}")

    # Log results
    log(f"🗑️  Deleted {deleted_count} junk files ({deleted_size/(1024*1024):.2f} MB)")
    log(f"   Remaining: {len(files) - deleted_count} files")

    # Show sample of what was deleted
    if deleted_count > 0 and deleted_count <= 10:
        log("   Deleted files:")
        for file, reason in junk_files[:10]:
            log(f"     • {file.name[:50]} - {reason}")
    elif deleted_count > 10:
        log(f"   Sample deleted files (showing 5 of {deleted_count}):")
        for file, reason in junk_files[:5]:
            log(f"     • {file.name[:50]} - {reason}")


if __name__ == "__main__":
    log("=" * 60)
    log("Starting Discord image cleanup...")
    cleanup()
    log("Cleanup complete")
