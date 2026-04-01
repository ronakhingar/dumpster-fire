#!/bin/bash
# Wrapper script for Discord monitor
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
/usr/bin/python3 -m discord.discord_monitor --loop
