#!/usr/bin/env python3
"""
Clean up junk images from day-trade-alerts Discord export.

Removes:
- Small files (< 50KB) - emojis, avatars, reactions
- SVG files (vector emojis)
- GIF files < 100KB (reaction GIFs)
"""

from pathlib import Path

DAYTRADE_DIR = Path("/Users/rhingar/Projects/dumpster-fire/discord_history/day-trade-alerts")

print()
print("="*70)
print("  DAY-TRADE-ALERTS DISCORD EXPORT CLEANUP")
print("="*70)
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


def cleanup_directory(files_dir: Path, label: str):
    """Remove junk files from a specific _Files directory."""

    if not files_dir.exists():
        print(f"  ⚠ Directory not found: {label}")
        return 0, 0

    print(f"📂 Processing: {label}")
    print(f"   Path: {files_dir.name}")
    print()

    # Get all image files
    image_files = []
    for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']:
        image_files.extend(files_dir.glob(f"*{ext}"))

    if not image_files:
        print(f"  ⚠ No image files found")
        print()
        return 0, 0

    print(f"  📊 Found {len(image_files)} image files")

    # Categorize
    junk_files = []
    chart_files = []

    for file_path in image_files:
        is_junk, reason = is_junk_file(file_path)

        if is_junk:
            junk_files.append((file_path, reason))
        else:
            chart_files.append(file_path)

    print(f"     Junk files: {len(junk_files)}")
    print(f"     Chart files: {len(chart_files)}")
    print()

    # Show sample junk
    if junk_files:
        print("  Sample junk files:")
        for file_path, reason in junk_files[:5]:
            print(f"    ✗ {file_path.name[:50]:<50} - {reason}")
        if len(junk_files) > 5:
            print(f"    ... and {len(junk_files) - 5} more")
        print()

    # Delete junk
    if junk_files:
        print("  Deleting junk files...")
        deleted_count = 0

        for file_path, reason in junk_files:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"    ⚠ Failed to delete {file_path.name}: {e}")

        print(f"  ✅ Deleted {deleted_count} junk files")
    else:
        print("  ✓ No junk files to delete")

    print(f"  ✅ Kept {len(chart_files)} clean chart files")
    print()

    # Show sample charts
    if chart_files:
        print("  Sample chart files (kept):")
        for file_path in chart_files[:5]:
            size_kb = file_path.stat().st_size / 1024
            print(f"    ✓ {file_path.name[:50]:<50} - {size_kb:.1f}KB")
        if len(chart_files) > 5:
            print(f"    ... and {len(chart_files) - 5} more")
    print()
    print("-"*70)
    print()

    return len(junk_files), len(chart_files)


# Find all _Files directories
files_dirs = list(DAYTRADE_DIR.glob("*_Files"))

if not files_dirs:
    print("✗ No _Files directories found")
    exit(1)

print(f"Found {len(files_dirs)} export directories")
print()

total_junk = 0
total_charts = 0

for files_dir in files_dirs:
    # Create a short label
    if "981926799212679248" in files_dir.name:
        label = "Export 1 (981926799212679248)"
    elif "1166801065623179355" in files_dir.name:
        label = "Export 2 (1166801065623179355)"
    else:
        label = files_dir.name[:60]

    junk, charts = cleanup_directory(files_dir, label)
    total_junk += junk
    total_charts += charts

print()
print("="*70)
print("  CLEANUP COMPLETE")
print("="*70)
print()
print(f"Total across all exports:")
print(f"  Junk removed: {total_junk}")
print(f"  Charts kept: {total_charts}")
print()
print("="*70)
