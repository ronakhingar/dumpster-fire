#!/usr/bin/env python3
"""
Robust Discord message parser that handles incomplete JSON.
Extracts individual message objects from the messages array.
"""

import json
import re
from pathlib import Path

HISTORY_FILE = Path("discord_history") / "day-trade-alerts" / \
    "The Traveling Trader - ➤ 𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐀𝐋𝐄𝐑𝐓 ⚡ - 🎯┃day-trade-alerts [981926799212679248].json"


def extract_messages_robust(file_path):
    """Extract messages by parsing line-by-line, properly tracking nesting."""
    messages = []
    current_message = []
    brace_level = 0
    in_messages_array = False
    message_started = False
    base_indent = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Check if we've entered the messages array
            if '"messages":' in line:
                in_messages_array = True
                continue

            if not in_messages_array:
                continue

            # Skip the opening bracket of messages array
            stripped = line.strip()
            if stripped == '[':
                continue

            # End of messages array
            if stripped.startswith(']'):
                break

            # Count braces
            open_braces = line.count('{')
            close_braces = line.count('}')

            # Detect start of new message (indented single {)
            if not message_started and stripped == '{':
                message_started = True
                current_message = [line]
                brace_level = 1
                # Determine indentation level for this message
                base_indent = len(line) - len(line.lstrip())
                continue

            if message_started:
                current_message.append(line)
                brace_level += (open_braces - close_braces)

                # Check if we've closed the message object
                # (back to base level with closing brace)
                current_indent = len(line) - len(line.lstrip())
                if brace_level == 0 and current_indent == base_indent and '}' in stripped:
                    # Complete message collected
                    message_text = ''.join(current_message)

                    # Clean up trailing comma
                    message_text = message_text.rstrip().rstrip(',').rstrip()

                    try:
                        msg = json.loads(message_text)
                        # Only keep if it has required fields (actual message, not nested object)
                        if 'id' in msg and 'type' in msg and 'timestamp' in msg:
                            messages.append(msg)
                    except json.JSONDecodeError as e:
                        # Skip malformed
                        pass

                    # Reset for next message
                    message_started = False
                    current_message = []
                    brace_level = 0

    return messages


if __name__ == "__main__":
    print("Parsing Discord messages...")
    messages = extract_messages_robust(HISTORY_FILE)
    print(f"Extracted {len(messages)} messages")

    # Save to simpler JSON file
    output_file = Path("discord_history") / "day-trade-alerts_parsed.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"messages": messages}, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {output_file}")

    # Show sample
    if messages:
        print(f"\nSample message:")
        print(f"  Author: {messages[0].get('author', {}).get('nickname', 'Unknown')}")
        print(f"  Content: {messages[0].get('content', '')[:100]}")
