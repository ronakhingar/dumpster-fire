#!/usr/bin/env python3
"""
Process swing trade charts with OCR to extract TP/SL levels.
"""

import json
from pathlib import Path
from discord_chart_processor import extract_enhanced_chart_levels

SWINGS_DIR = Path("/Users/rhingar/Projects/dumpster-fire/discord_history/swings")

# Find the _Files directory
FILES_DIR = None
for item in SWINGS_DIR.iterdir():
    if item.is_dir() and item.name.endswith("_Files"):
        FILES_DIR = item
        break

if not FILES_DIR:
    print("✗ Could not find _Files directory")
    exit(1)

print()
print("="*70)
print("  PROCESSING SWING TRADE CHARTS")
print("="*70)
print(f"\n📂 Directory: {FILES_DIR.name}")
print()

# Find all image files
image_files = sorted(FILES_DIR.glob("*.png"))
image_files.extend(sorted(FILES_DIR.glob("*.jpg")))

print(f"📊 Found {len(image_files)} chart images")
print()

# Process charts
results = []
high_confidence_count = 0
medium_confidence_count = 0
low_confidence_count = 0

print("Processing charts...")
print()

for i, chart_path in enumerate(image_files):
    # Show progress every 50 charts
    if i % 50 == 0 and i > 0:
        print(f"  Processed {i}/{len(image_files)}...")

    # Extract levels
    result = extract_enhanced_chart_levels(str(chart_path))

    result['filename'] = chart_path.name
    result['path'] = str(chart_path)

    confidence = result.get('confidence', 0)

    if confidence >= 0.7:
        high_confidence_count += 1
    elif confidence >= 0.4:
        medium_confidence_count += 1
    else:
        low_confidence_count += 1

    results.append(result)

print(f"  Processed {len(image_files)}/{len(image_files)}... Done!")
print()

# Summary
print("="*70)
print("  EXTRACTION SUMMARY")
print("="*70)
print()
print(f"Total charts processed: {len(image_files)}")
print(f"  High confidence (0.7+): {high_confidence_count}")
print(f"  Medium confidence (0.4-0.7): {medium_confidence_count}")
print(f"  Low confidence (<0.4): {low_confidence_count}")
print()

# Show high-confidence extractions
high_conf_results = [r for r in results if r.get('confidence', 0) >= 0.7]

if high_conf_results:
    print(f"📊 HIGH-CONFIDENCE EXTRACTIONS ({len(high_conf_results)} charts)")
    print("="*70)
    print()

    for i, result in enumerate(high_conf_results[:10]):
        print(f"Chart {i+1}: {result['filename'][:60]}")
        print(f"  Confidence: {result['confidence']:.2f}")

        if result.get('all_prices'):
            prices = result['all_prices']
            print(f"  Price range: ${min(prices):.2f} - ${max(prices):.2f}")

        if result.get('take_profit'):
            tp_list = result['take_profit'][:5]  # Show first 5
            tp_str = ', '.join([f"${x:.2f}" for x in tp_list])
            if len(result['take_profit']) > 5:
                tp_str += f" + {len(result['take_profit'])-5} more"
            print(f"  ✓ Take Profit: {tp_str}")

        if result.get('stop_loss'):
            sl_list = result['stop_loss'][:3]  # Show first 3
            sl_str = ', '.join([f"${x:.2f}" for x in sl_list])
            if len(result['stop_loss']) > 3:
                sl_str += f" + {len(result['stop_loss'])-3} more"
            print(f"  ✓ Stop Loss: {sl_str}")

        print()

    if len(high_conf_results) > 10:
        print(f"  ... and {len(high_conf_results) - 10} more high-confidence results")
        print()

# Save results
output_file = SWINGS_DIR / "chart_extraction_results.json"
with open(output_file, 'w') as f:
    json.dump({
        'total_charts': len(image_files),
        'high_confidence_count': high_confidence_count,
        'medium_confidence_count': medium_confidence_count,
        'low_confidence_count': low_confidence_count,
        'results': results
    }, f, indent=2)

print()
print(f"✅ Results saved to: {output_file}")
print()
print("="*70)
