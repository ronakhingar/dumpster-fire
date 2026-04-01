#!/usr/bin/env python3
"""
Strict cleanup for day-trade-alerts directory.

Only keeps files with these prefixes:
- image-
- Screenshot

Removes everything else (hash names, numbered files, etc.)
"""

from pathlib import Path

DAYTRADE_DIR = Path("/Users/rhingar/Projects/dumpster-fire/discord_history/day-trade-alerts")

print()
print("="*70)
print("  DAY-TRADE-ALERTS STRICT CLEANUP")
print("  (Only keep: image-* and Screenshot*)")
print("="*70)
print()


def should_keep_file(file_path: Path) -> tuple[bool, str]:
    """
    Determine if a file should be kept based on filename prefix.

    Returns: (should_keep, reason)
    """
    name = file_path.name

    # Keep files starting with "image-"
    if name.startswith("image-"):
        return True, "image- prefix"

    # Keep files starting with "Screenshot"
    if name.startswith("Screenshot"):
        return True, "Screenshot prefix"

    # Remove everything else
    size_kb = file_path.stat().st_size / 1024
    return False, f"No valid prefix ({size_kb:.1f}KB)"


def strict_cleanup_directory(files_dir: Path, label: str):
    """Remove files that don't match required prefixes."""

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
    keep_files = []
    remove_files = []

    for file_path in image_files:
        should_keep, reason = should_keep_file(file_path)

        if should_keep:
            keep_files.append((file_path, reason))
        else:
            remove_files.append((file_path, reason))

    print(f"     Keep: {len(keep_files)}")
    print(f"     Remove: {len(remove_files)}")
    print()

    # Show sample files to remove
    if remove_files:
        print("  Files to REMOVE:")
        for file_path, reason in remove_files[:10]:
            print(f"    ✗ {file_path.name[:50]:<50} - {reason}")
        if len(remove_files) > 10:
            print(f"    ... and {len(remove_files) - 10} more")
        print()

    # Show sample files to keep
    if keep_files:
        print("  Files to KEEP:")
        for file_path, reason in keep_files[:5]:
            size_kb = file_path.stat().st_size / 1024
            print(f"    ✓ {file_path.name[:50]:<50} - {size_kb:.1f}KB")
        if len(keep_files) > 5:
            print(f"    ... and {len(keep_files) - 5} more")
        print()

    # Delete unwanted files
    if remove_files:
        print("  Deleting files without valid prefix...")
        deleted_count = 0

        for file_path, reason in remove_files:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"    ⚠ Failed to delete {file_path.name}: {e}")

        print(f"  ✅ Deleted {deleted_count} files")
    else:
        print("  ✓ No files to delete")

    print(f"  ✅ Kept {len(keep_files)} files with valid prefixes")
    print()
    print("-"*70)
    print()

    return len(remove_files), len(keep_files)


# Find all _Files directories
files_dirs = list(DAYTRADE_DIR.glob("*_Files"))

if not files_dirs:
    print("✗ No _Files directories found")
    exit(1)

print(f"Found {len(files_dirs)} export directories")
print()

total_removed = 0
total_kept = 0

for files_dir in files_dirs:
    # Create a short label
    if "981926799212679248" in files_dir.name:
        label = "Export 1 (981926799212679248)"
    elif "1166801065623179355" in files_dir.name:
        label = "Export 2 (1166801065623179355)"
    else:
        label = files_dir.name[:60]

    removed, kept = strict_cleanup_directory(files_dir, label)
    total_removed += removed
    total_kept += kept

print()
print("="*70)
print("  STRICT CLEANUP COMPLETE")
print("="*70)
print()
print(f"Total across all exports:")
print(f"  Files removed: {total_removed}")
print(f"  Files kept: {total_kept} (image-* and Screenshot* only)")
print()
print("="*70)
