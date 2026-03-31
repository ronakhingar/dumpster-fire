#!/usr/bin/env python3
"""
macOS Desktop Notification Helper

Sends native macOS notifications using osascript.
"""

import subprocess
import sys
from typing import Optional


def send_notification(
    title: str,
    message: str,
    subtitle: Optional[str] = None,
    sound: bool = True
) -> bool:
    """
    Send a macOS desktop notification.

    Args:
        title: Notification title
        message: Notification message body
        subtitle: Optional subtitle
        sound: Whether to play notification sound

    Returns:
        True if successful, False otherwise
    """
    # Escape quotes for AppleScript
    title = title.replace('"', '\\"')
    message = message.replace('"', '\\"')

    # Build AppleScript
    script = f'display notification "{message}" with title "{title}"'

    if subtitle:
        subtitle = subtitle.replace('"', '\\"')
        script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'

    if sound:
        script += ' sound name "Submarine"'

    try:
        subprocess.run(
            ['osascript', '-e', script],
            check=True,
            capture_output=True,
            timeout=5
        )
        return True
    except Exception as e:
        print(f"Failed to send notification: {e}", file=sys.stderr)
        return False


def notify_opportunities(count: int, details: str = ""):
    """Send notification about trade opportunities found."""
    if count == 0:
        return

    if count == 1:
        title = "🎯 1 Trade Opportunity Found"
    else:
        title = f"🎯 {count} Trade Opportunities Found"

    message = details if details else "Check your report for details"

    send_notification(title, message, sound=True)


def notify_error(error_msg: str):
    """Send notification about an error."""
    send_notification("⚠️ Trading Monitor Error", error_msg, sound=True)


if __name__ == "__main__":
    # Test notification
    if len(sys.argv) > 1:
        send_notification("Test Notification", " ".join(sys.argv[1:]))
    else:
        send_notification(
            "Dumpster Fire Monitor",
            "Notification system is working!",
            subtitle="Test notification"
        )
