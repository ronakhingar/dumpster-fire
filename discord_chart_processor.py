#!/usr/bin/env python3
"""
Enhanced Discord Chart Processor

Links chart images to Discord messages and extracts TP/SL levels.

Key improvements:
1. Reads price levels from y-axis (right side of chart)
2. Detects colored zones (green = TP, red = SL)
3. Correlates zones with price levels
4. Links charts to messages by timestamp proximity
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

try:
    import cv2
    import numpy as np
    from PIL import Image
    import pytesseract
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False

ET = ZoneInfo("America/New_York")
BASE_DIR = Path(__file__).parent
CHARTS_DIR = BASE_DIR / "discord_history" / "DISCORD_.html_Files"
SIGNALS_HISTORY = BASE_DIR / "journal" / "discord_signals_history.jsonl"


def extract_price_from_yaxis(image_path: str) -> List[float]:
    """
    Extract price levels from the y-axis (right side) of TradingView charts.

    TradingView charts have price labels on the right edge.
    """
    if not DEPS_AVAILABLE:
        return []

    try:
        img = cv2.imread(image_path)
        if img is None:
            return []

        height, width = img.shape[:2]

        # Focus on right 15% of image (where price axis usually is)
        right_margin = int(width * 0.85)
        yaxis_region = img[:, right_margin:]

        # Convert to PIL for OCR
        yaxis_pil = Image.fromarray(cv2.cvtColor(yaxis_region, cv2.COLOR_BGR2RGB))

        # OCR with config for better number recognition
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,$'
        text = pytesseract.image_to_string(yaxis_pil, config=custom_config)

        # Extract numbers (prices)
        prices = []
        for line in text.split('\n'):
            # Remove commas and dollar signs
            line_clean = line.replace(',', '').replace('$', '').strip()

            # Try to parse as float
            try:
                price = float(line_clean)
                # Reasonable price range for stocks
                if 10 < price < 10000:
                    prices.append(price)
            except ValueError:
                continue

        return sorted(set(prices))

    except Exception as e:
        print(f"  ⚠ Y-axis extraction error: {e}")
        return []


def detect_colored_zones(image_path: str) -> Dict[str, List[Tuple[float, float]]]:
    """
    Detect colored rectangular zones in chart (TP/SL zones).

    Returns:
        {"green_zones": [(y_start_pct, y_end_pct), ...],
         "red_zones": [(y_start_pct, y_end_pct), ...]}
    """
    if not DEPS_AVAILABLE:
        return {"green_zones": [], "red_zones": []}

    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"green_zones": [], "red_zones": []}

        height, width = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Green zones (TP) - broader range for different chart themes
        green_lower = np.array([35, 50, 50])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)

        # Red zones (SL)
        red_lower1 = np.array([0, 50, 50])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([170, 50, 50])
        red_upper2 = np.array([180, 255, 255])
        red_mask = cv2.bitwise_or(
            cv2.inRange(hsv, red_lower1, red_upper1),
            cv2.inRange(hsv, red_lower2, red_upper2)
        )

        def find_zones(mask):
            """Find rectangular zones in mask."""
            # Morphology to connect nearby regions
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 50))
            closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Find contours
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            zones = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)

                # Filter: must be substantial size (at least 10% of image width/height)
                if w > width * 0.1 and h > height * 0.05:
                    y_start_pct = y / height
                    y_end_pct = (y + h) / height
                    zones.append((y_start_pct, y_end_pct))

            return zones

        return {
            "green_zones": find_zones(green_mask),
            "red_zones": find_zones(red_mask)
        }

    except Exception as e:
        print(f"  ⚠ Zone detection error: {e}")
        return {"green_zones": [], "red_zones": []}


def map_zones_to_prices(zones: List[Tuple[float, float]], prices: List[float],
                        chart_height_pixels: int) -> List[float]:
    """
    Map y-position zones to actual price levels.

    Args:
        zones: List of (y_start_pct, y_end_pct) tuples
        prices: List of prices from y-axis
        chart_height_pixels: Chart height in pixels

    Returns:
        List of price levels that fall within zones
    """
    if not prices or not zones:
        return []

    # Assume prices are sorted (top to bottom on chart = high to low price)
    # TradingView: top of chart = highest price, bottom = lowest price
    prices_sorted = sorted(prices, reverse=True)

    matched_prices = []
    for y_start_pct, y_end_pct in zones:
        # Map percentages to price range
        # Zone at top (low y_pct) = high prices
        # Zone at bottom (high y_pct) = low prices

        for price in prices_sorted:
            # Approximate: assume linear price scale
            # Find which prices fall in this zone
            price_pct = (max(prices) - price) / (max(prices) - min(prices))

            if y_start_pct <= price_pct <= y_end_pct:
                matched_prices.append(price)

    return sorted(set(matched_prices))


def extract_enhanced_chart_levels(image_path: str) -> Dict:
    """
    Enhanced chart level extraction combining multiple methods.

    Returns:
        {
            "take_profit": [price1, price2, ...],
            "stop_loss": [price1, ...],
            "support": [price1, ...],
            "resistance": [price1, ...],
            "all_prices": [all detected prices],
            "confidence": float,
            "method": "enhanced_hybrid"
        }
    """
    result = {
        "take_profit": [],
        "stop_loss": [],
        "support": [],
        "resistance": [],
        "all_prices": [],
        "confidence": 0.0,
        "method": "enhanced_hybrid"
    }

    if not DEPS_AVAILABLE:
        result["error"] = "Dependencies not available"
        return result

    try:
        # Step 1: Extract price levels from y-axis
        yaxis_prices = extract_price_from_yaxis(image_path)
        result["all_prices"] = yaxis_prices

        if not yaxis_prices:
            result["confidence"] = 0.1
            return result

        # Step 2: Detect colored zones
        img = cv2.imread(image_path)
        height = img.shape[0] if img is not None else 0

        zones = detect_colored_zones(image_path)

        # Step 3: Map zones to prices
        if zones["green_zones"]:
            tp_prices = map_zones_to_prices(zones["green_zones"], yaxis_prices, height)
            result["take_profit"] = tp_prices

        if zones["red_zones"]:
            sl_prices = map_zones_to_prices(zones["red_zones"], yaxis_prices, height)
            result["stop_loss"] = sl_prices

        # Step 4: Also try OCR for explicit TP/SL labels
        from discord_chart_ocr import extract_text_levels
        ocr_levels = extract_text_levels(image_path)

        # Merge OCR results
        if ocr_levels.get("take_profit") and not result["take_profit"]:
            result["take_profit"] = ocr_levels["take_profit"]

        if ocr_levels.get("stop_loss") and not result["stop_loss"]:
            result["stop_loss"] = ocr_levels["stop_loss"]

        # Calculate confidence
        confidence = 0.0
        if result["take_profit"]:
            confidence += 0.5
        if result["stop_loss"]:
            confidence += 0.3
        if result["all_prices"]:
            confidence += 0.2

        result["confidence"] = min(confidence, 1.0)

    except Exception as e:
        result["error"] = str(e)
        result["confidence"] = 0.0

    return result


def link_charts_to_messages() -> Dict[str, List[str]]:
    """
    Link chart images to Discord messages by timestamp proximity.

    Returns:
        {message_id: [chart_path1, chart_path2, ...], ...}
    """
    print("\n  📊 Linking charts to messages...")

    # Load messages
    messages = []
    if SIGNALS_HISTORY.exists():
        with open(SIGNALS_HISTORY) as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))

    # Get all charts with timestamps from filenames
    charts = []
    if CHARTS_DIR.exists():
        for chart_path in CHARTS_DIR.glob("*.png"):
            # Get file creation/modification time
            stat = chart_path.stat()
            charts.append({
                "path": str(chart_path),
                "timestamp": datetime.fromtimestamp(stat.st_mtime, tz=ET)
            })

    print(f"  Found {len(messages)} messages and {len(charts)} charts")

    # Link by timestamp proximity (within 5 minutes)
    links = {}
    for msg in messages:
        msg_id = msg.get("message_id") or msg.get("notification_id")
        if not msg_id:
            continue

        # Parse message timestamp
        try:
            msg_time_str = msg.get("source_timestamp") or msg.get("timestamp")
            msg_time = datetime.fromisoformat(msg_time_str)
            if msg_time.tzinfo is None:
                msg_time = msg_time.replace(tzinfo=ET)
        except:
            continue

        # Find charts within 5 minutes
        nearby_charts = []
        for chart in charts:
            time_diff = abs((chart["timestamp"] - msg_time).total_seconds())
            if time_diff < 300:  # 5 minutes
                nearby_charts.append(chart["path"])

        if nearby_charts:
            links[msg_id] = nearby_charts

    print(f"  ✓ Linked {len(links)} messages to charts")
    return links


def process_all_charts_and_update_signals():
    """
    Process all charts, link to messages, and update signal records with chart data.
    """
    print("\n" + "="*70)
    print("  DISCORD CHART INTEGRATION")
    print("="*70)

    # Link charts to messages
    chart_links = link_charts_to_messages()

    if not chart_links:
        print("\n  ⚠ No charts linked to messages")
        return

    # Process each linked chart
    updated_count = 0
    for msg_id, chart_paths in list(chart_links.items())[:10]:  # Test with first 10
        print(f"\n  Processing message {msg_id[:20]}...")

        for chart_path in chart_paths:
            print(f"    Chart: {Path(chart_path).name}")

            # Extract levels
            levels = extract_enhanced_chart_levels(chart_path)

            if levels.get("confidence", 0) > 0.3:
                print(f"    ✓ Confidence: {levels['confidence']:.2f}")
                print(f"      All prices: {levels.get('all_prices', [][:5])}")
                print(f"      Take Profit: {levels.get('take_profit', [])}")
                print(f"      Stop Loss: {levels.get('stop_loss', [])}")
                updated_count += 1
            else:
                print(f"    ✗ Low confidence: {levels.get('confidence', 0):.2f}")

    print(f"\n  ✅ Processed {updated_count} charts with useful data")
    print("="*70)


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        # Test on a specific chart
        test_chart = sys.argv[sys.argv.index("--test") + 1] if len(sys.argv) > sys.argv.index("--test") + 1 else None

        if test_chart:
            print(f"\n  Testing enhanced OCR on: {test_chart}")
            levels = extract_enhanced_chart_levels(test_chart)
            print(json.dumps(levels, indent=2))
        else:
            # Test linking
            process_all_charts_and_update_signals()

    elif "--link" in sys.argv:
        # Just create links
        links = link_charts_to_messages()
        print(json.dumps(list(links.items())[:5], indent=2))

    else:
        # Full processing
        process_all_charts_and_update_signals()
