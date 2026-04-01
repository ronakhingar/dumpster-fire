#!/usr/bin/env python3
"""
Discord Chart OCR & Level Extraction

Extracts trading levels from chart screenshots:
- TP (Take Profit) levels - typically marked in GREEN
- SL (Stop Loss) levels - typically marked in RED
- Entry levels - typically marked with horizontal lines
- Support/Resistance zones

Uses:
1. OCR (pytesseract) for text extraction
2. Computer vision (OpenCV) for color detection
3. Pattern matching for price levels
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    import cv2
    import numpy as np
    from PIL import Image
    import pytesseract
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False
    print("⚠ Chart OCR dependencies not installed.")
    print("   Install with: pip install opencv-python pillow pytesseract")


def extract_chart_levels(image_path: str) -> Dict:
    """
    Extract trading levels from chart screenshot.

    Returns dict with:
        - entry: float or None
        - stop_loss: float or None
        - take_profit: list of floats
        - support: list of floats
        - resistance: list of floats
        - confidence: float (0.0 - 1.0)
        - method: 'ocr', 'color_detection', 'hybrid'
    """
    if not DEPS_AVAILABLE:
        return {
            "entry": None,
            "stop_loss": None,
            "take_profit": [],
            "support": [],
            "resistance": [],
            "confidence": 0.0,
            "method": "unavailable",
            "error": "OCR dependencies not installed"
        }

    result = {
        "entry": None,
        "stop_loss": None,
        "take_profit": [],
        "support": [],
        "resistance": [],
        "confidence": 0.0,
        "method": "hybrid"
    }

    try:
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            result["error"] = "Failed to load image"
            return result

        # Method 1: Color-based detection
        color_levels = detect_levels_by_color(img)
        result.update(color_levels)

        # Method 2: OCR text extraction
        ocr_levels = extract_text_levels(image_path)

        # Merge results (prioritize color detection, supplement with OCR)
        if not result["stop_loss"] and ocr_levels.get("stop_loss"):
            result["stop_loss"] = ocr_levels["stop_loss"]

        if not result["take_profit"] and ocr_levels.get("take_profit"):
            result["take_profit"] = ocr_levels["take_profit"]

        # Calculate confidence
        confidence_score = 0.0
        if result["stop_loss"]:
            confidence_score += 0.4
        if result["take_profit"]:
            confidence_score += 0.4
        if result["entry"]:
            confidence_score += 0.2

        result["confidence"] = min(confidence_score, 1.0)

    except Exception as e:
        result["error"] = str(e)
        result["confidence"] = 0.0

    return result


def detect_levels_by_color(img: np.ndarray) -> Dict:
    """
    Detect TP/SL levels by color zones.

    Green zones → Take Profit
    Red zones → Stop Loss
    """
    result = {
        "stop_loss": None,
        "take_profit": [],
        "entry": None
    }

    try:
        # Convert BGR to HSV for better color detection
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Define color ranges
        # Green (Take Profit): Hue 40-80, Saturation > 100, Value > 100
        green_lower = np.array([40, 100, 100])
        green_upper = np.array([80, 255, 255])

        # Red (Stop Loss): Hue 0-10 or 170-180, Saturation > 100, Value > 100
        red_lower1 = np.array([0, 100, 100])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([170, 100, 100])
        red_upper2 = np.array([180, 255, 255])

        # Create masks
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
        red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        # Find horizontal lines in each color zone
        # These represent price levels

        # Green zones (Take Profit)
        tp_levels = find_horizontal_lines(green_mask, img.shape[0])
        if tp_levels:
            result["take_profit"] = tp_levels

        # Red zones (Stop Loss)
        sl_levels = find_horizontal_lines(red_mask, img.shape[0])
        if sl_levels:
            result["stop_loss"] = sl_levels[0]  # Take first (usually only one SL)

    except Exception as e:
        print(f"  ⚠ Color detection error: {e}")

    return result


def find_horizontal_lines(mask: np.ndarray, img_height: int) -> List[float]:
    """
    Find horizontal lines in a binary mask.
    Returns y-coordinates as percentage of image height.
    """
    lines = []

    # Horizontal line detection
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    detected = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Find contours
    contours, _ = cv2.findContours(detected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > img_height * 0.3:  # Line must span at least 30% of width
            # Convert y-coordinate to percentage
            y_pct = y / img_height
            lines.append(y_pct)

    return sorted(lines)


def extract_text_levels(image_path: str) -> Dict:
    """
    Extract price levels using OCR on text in image.

    Looks for patterns like:
    - "TP: 6500"
    - "SL: 6550"
    - "Entry: 6525"
    - "$6500"
    """
    result = {
        "stop_loss": None,
        "take_profit": [],
        "entry": None
    }

    try:
        # Load image with PIL for pytesseract
        img = Image.open(image_path)

        # Run OCR
        text = pytesseract.image_to_string(img)

        # Extract price levels
        levels = extract_price_levels_from_text(text)

        # Map to TP/SL based on labels
        for label, value in levels.items():
            label_lower = label.lower()

            if 'tp' in label_lower or 'target' in label_lower or 'profit' in label_lower:
                if value not in result["take_profit"]:
                    result["take_profit"].append(value)
            elif 'sl' in label_lower or 'stop' in label_lower:
                if not result["stop_loss"]:
                    result["stop_loss"] = value
            elif 'entry' in label_lower or 'enter' in label_lower:
                if not result["entry"]:
                    result["entry"] = value

    except Exception as e:
        print(f"  ⚠ OCR error: {e}")

    return result


def extract_price_levels_from_text(text: str) -> Dict[str, float]:
    """
    Extract labeled price levels from OCR text.

    Patterns:
        "TP: 6500" → {"TP": 6500}
        "Stop Loss: $6550" → {"Stop Loss": 6550}
    """
    levels = {}

    # Pattern: Label: $XXX.XX or Label: XXXX
    patterns = [
        (r'(TP|Take\s*Profit|Target)\s*[:\-]?\s*\$?(\d{2,5}\.?\d{0,2})', 'TP'),
        (r'(SL|Stop\s*Loss|Stop)\s*[:\-]?\s*\$?(\d{2,5}\.?\d{0,2})', 'SL'),
        (r'(Entry|Enter)\s*[:\-]?\s*\$?(\d{2,5}\.?\d{0,2})', 'Entry'),
    ]

    for pattern, label_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                value = float(match.group(2).replace(',', ''))
                if 100 < value < 100000:  # Reasonable price range
                    levels[label_type] = value
            except ValueError:
                continue

    return levels


def save_annotated_chart(image_path: str, levels: Dict, output_path: str = None):
    """
    Save chart with detected levels annotated.

    Useful for debugging and verification.
    """
    if not DEPS_AVAILABLE:
        return None

    try:
        img = cv2.imread(image_path)
        if img is None:
            return None

        height, width = img.shape[:2]

        # Draw TP levels (green)
        for tp in levels.get("take_profit", []):
            if isinstance(tp, float) and 0 < tp < 1:  # If percentage
                y = int(tp * height)
                cv2.line(img, (0, y), (width, y), (0, 255, 0), 2)
                cv2.putText(img, f"TP: {tp:.2%}", (10, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Draw SL level (red)
        if levels.get("stop_loss"):
            sl = levels["stop_loss"]
            if isinstance(sl, float) and 0 < sl < 1:
                y = int(sl * height)
                cv2.line(img, (0, y), (width, y), (0, 0, 255), 2)
                cv2.putText(img, "SL", (10, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Draw entry level (blue)
        if levels.get("entry"):
            entry = levels["entry"]
            if isinstance(entry, float) and 0 < entry < 1:
                y = int(entry * height)
                cv2.line(img, (0, y), (width, y), (255, 0, 0), 2)
                cv2.putText(img, "Entry", (10, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        # Save annotated image
        if not output_path:
            output_path = image_path.replace('.png', '_annotated.png')

        cv2.imwrite(output_path, img)
        print(f"  ✓ Annotated chart saved: {output_path}")

        return output_path

    except Exception as e:
        print(f"  ✗ Annotation error: {e}")
        return None


def process_chart_from_notification(notification_data: Dict) -> Dict:
    """
    Process chart attachment from Discord notification.

    Args:
        notification_data: Dict with 'attachments' key containing image paths

    Returns:
        Extracted levels dict
    """
    attachments = notification_data.get('attachments', [])

    if not attachments:
        return {"error": "No attachments"}

    # Process first image attachment (charts are usually first)
    chart_path = attachments[0]

    if not Path(chart_path).exists():
        return {"error": f"Chart file not found: {chart_path}"}

    print(f"  📊 Processing chart: {Path(chart_path).name}")

    levels = extract_chart_levels(chart_path)

    # Save annotated version for verification
    if levels.get("confidence", 0) > 0.5:
        annotated_path = save_annotated_chart(chart_path, levels)
        levels["annotated_chart"] = annotated_path

    return levels


# ═══ TESTING ═══════════════════════════════════════════════════════════════

def test_chart_ocr():
    """Test chart OCR on sample images."""

    print("\n" + "═" * 70)
    print("  CHART OCR TEST")
    print("═" * 70)

    # Test with sample chart (create test if needed)
    test_chart = Path(__file__).parent / "test_data" / "sample_chart.png"

    if not test_chart.exists():
        print(f"\n  ⚠ Test chart not found: {test_chart}")
        print("     Create test chart at: test_data/sample_chart.png")
        return

    print(f"\n  Processing: {test_chart.name}")

    levels = extract_chart_levels(str(test_chart))

    print(f"\n  Results:")
    print(f"    Confidence: {levels['confidence']:.2f}")
    print(f"    Method: {levels['method']}")
    print(f"    Entry: {levels.get('entry', 'Not detected')}")
    print(f"    Stop Loss: {levels.get('stop_loss', 'Not detected')}")
    print(f"    Take Profit: {levels.get('take_profit', 'Not detected')}")

    if levels.get('confidence', 0) > 0.5:
        print(f"\n  ✓ Chart analyzed successfully")

        # Save annotated version
        save_annotated_chart(str(test_chart), levels)

    else:
        print(f"\n  ⚠ Low confidence - check chart quality")

    if levels.get('error'):
        print(f"  Error: {levels['error']}")


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        test_chart_ocr()
    elif "--deps" in sys.argv:
        print("Installing chart OCR dependencies...")
        os.system("pip install opencv-python pillow pytesseract")
        print("\n✓ Dependencies installed")
        print("\nNote: pytesseract requires Tesseract OCR engine:")
        print("  macOS: brew install tesseract")
        print("  Linux: apt-get install tesseract-ocr")
    else:
        print("Discord Chart OCR")
        print("Usage:")
        print("  python3 discord_chart_ocr.py --test    # Test on sample chart")
        print("  python3 discord_chart_ocr.py --deps    # Install dependencies")
        print("")
        print("Dependencies:")
        print("  pip install opencv-python pillow pytesseract")
        print("  brew install tesseract  # macOS")
