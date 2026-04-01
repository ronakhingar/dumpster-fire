#!/usr/bin/env python3
"""
Clean up junk images from swings Discord export.

Removes:
- Small files (< 50KB) - emojis, avatars, reactions
- SVG files (vector emojis)
- GIF files < 100KB (reaction GIFs)
"""

import shutil
from pathlib import Path
from datetime import datetime

SWINGS_DIR = Path("/Users/rhingar/Projects/dumpster-fire/discord_history/swings")
FILES_DIR = None

# Find the _Files directory
for item in SWINGS_DIR.iterdir():
    if item.is_dir() and item.name.endswith("_Files"):
        FILES_DIR = item
        break

if not FILES_DIR:
    print("✗ Could not find _Files directory")
    exit(1)

print(f"📂 Cleaning: {FILES_DIR.name}")
print(f"   Path: {FILES_DIR}")
print()

def is_junk_file(file_path: Path) -> tuple[bool, str]:
    """
    Determine if a file is junk.

    Returns: (is_junk, reason)
    """
    size_kb = file_path.stat().st_size / 1024
    ext = file_path.suffix.lower()
    name = file_path.name.lower()

    # SVG files are always emoji reactions
    if ext == '.svg':
        return True, f"SVG emoji ({size_kb:.1f}KB)"

    # Very small files (< 30KB) are avatars/tiny icons
    if size_kb < 30:
        return True, f"Too small ({size_kb:.1f}KB)"

    # Small PNG/JPG files (30-50KB) with hash patterns are likely avatars
    if 30 <= size_kb < 50 and ext in ['.png', '.jpg', '.jpeg']:
        # Check if filename is just a hash (no descriptive name)
        if len(file_path.stem) >= 30:  # Long hash-like names
            return True, f"Small hash file ({size_kb:.1f}KB)"

    # GIF files < 100KB are usually reaction GIFs
    if ext == '.gif' and size_kb < 100:
        return True, f"Small GIF ({size_kb:.1f}KB)"

    # Emoji in filename
    if any(word in name for word in ['emoji', 'reaction', 'avatar', 'icon']):
        return True, f"Emoji/avatar keyword ({size_kb:.1f}KB)"

    return False, ""


def cleanup_junk_files():
    """Remove junk files from swings export."""

    if not FILES_DIR.exists():
        print("✗ Files directory not found")
        return

    # Count files
    all_files = list(FILES_DIR.glob("*"))
    image_files = [f for f in all_files if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']]

    print(f"📊 Found {len(image_files)} image files")
    print()

    # Categorize
    junk_files = []
    chart_files = []

    for file_path in image_files:
        is_junk, reason = is_junk_file(file_path)

        if is_junk:
            junk_files.append((file_path, reason))
        else:
            chart_files.append(file_path)

    print(f"  Junk files: {len(junk_files)}")
    print(f"  Chart files: {len(chart_files)}")
    print()

    # Show sample junk
    print("Sample junk files:")
    for file_path, reason in junk_files[:10]:
        print(f"  ✗ {file_path.name[:50]:<50} - {reason}")
    if len(junk_files) > 10:
        print(f"  ... and {len(junk_files) - 10} more")
    print()

    # Delete junk
    print("Deleting junk files...")
    deleted_count = 0

    for file_path, reason in junk_files:
        try:
            file_path.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"  ⚠ Failed to delete {file_path.name}: {e}")

    print(f"✅ Deleted {deleted_count} junk files")
    print(f"✅ Kept {len(chart_files)} clean chart files")
    print()

    # Show sample charts
    print("Sample chart files (kept):")
    for file_path in chart_files[:10]:
        size_kb = file_path.stat().st_size / 1024
        print(f"  ✓ {file_path.name[:50]:<50} - {size_kb:.1f}KB")
    if len(chart_files) > 10:
        print(f"  ... and {len(chart_files) - 10} more")


if __name__ == "__main__":
    print()
    print("="*70)
    print("  SWINGS DISCORD EXPORT CLEANUP")
    print("="*70)
    print()

    cleanup_junk_files()

    print()
    print("="*70)
    print("  CLEANUP COMPLETE")
    print("="*70)
