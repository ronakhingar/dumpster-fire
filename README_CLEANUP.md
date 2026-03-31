# Discord Export Cleanup Scripts

## Available Cleanup Scripts

### 1. **cleanup_daytrade_strict.py** ⭐ STRICT CLEANUP
**Purpose:** Strict cleanup for day-trade-alerts - only keeps files with valid prefixes

**Keeps:**
- Files starting with `image-`
- Files starting with `Screenshot`

**Removes:**
- All hash-named files (even large ones)
- Numbered files
- Random named files
- Everything without the valid prefixes

**Usage:**
```bash
cd /Users/rhingar/Projects/dumpster-fire
python3 cleanup_daytrade_strict.py
```

**Best for:** day-trade-alerts directory (clean named files only)

---

### 2. **cleanup_swings_strict.py** ⭐ STRICT CLEANUP
**Purpose:** Strict cleanup for swings - only keeps files with valid prefixes

**Keeps:**
- Files starting with `image-`
- Files starting with `Screenshot`

**Removes:**
- All hash-named files (even large ones)
- Numbered files
- Random named files
- Everything without the valid prefixes

**Usage:**
```bash
cd /Users/rhingar/Projects/dumpster-fire
python3 cleanup_swings_strict.py
```

**Best for:** swings directory (clean named files only)

---

### 3. **cleanup_daytrade_images.py**
**Purpose:** General cleanup - removes small junk files

**Removes:**
- Files < 30KB (emojis, avatars)
- Small hash files 30-50KB
- SVG emojis
- Small GIFs < 100KB

**Keeps:**
- All files > 50KB regardless of name

**Usage:**
```bash
cd /Users/rhingar/Projects/dumpster-fire
python3 cleanup_daytrade_images.py
```

**Best for:** First pass cleanup to remove obvious junk

---

### 4. **cleanup_swings_images.py**
**Purpose:** General cleanup for swings - removes small junk files (same logic as #3)

**Usage:**
```bash
cd /Users/rhingar/Projects/dumpster-fire
python3 cleanup_swings_images.py
```

---

## Quick Reference

**Strict cleanup (only image-* and Screenshot*):**
```bash
# Day-trade-alerts
python3 cleanup_daytrade_strict.py

# Swings
python3 cleanup_swings_strict.py
```

**General cleanup (remove junk, keep all large files):**
```bash
# Day-trade-alerts
python3 cleanup_daytrade_images.py

# Swings
python3 cleanup_swings_images.py
```

---

## Current Clean Directories

After strict cleanup:

1. **day-trade-alerts**: 201 files (image-* and Screenshot* only)
2. **swings**: 320 files (image-* and Screenshot* only)
3. **DISCORD_.html_Files**: 722 files (original, size-based cleanup)

**Total: 1,243 clean chart images with proper naming**

---

## Recommended Workflow

For any new Discord export:

1. **First pass** - Remove obvious junk:
   ```bash
   python3 cleanup_[directory]_images.py
   ```

2. **Second pass** - Strict cleanup (only keep image-* and Screenshot*):
   ```bash
   python3 cleanup_[directory]_strict.py
   ```

This ensures you keep only properly named trading charts.
