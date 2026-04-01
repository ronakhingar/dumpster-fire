#!/usr/bin/env python3
"""Check exact channel names"""

import discord
import os
from dotenv import load_dotenv

load_dotenv()

TARGET_CHANNELS = ["stock-alerts", "day-trade-alerts", "swings"]

class CheckClient(discord.Client):
    async def on_ready(self):
        print(f"\n✅ Logged in as: {self.user.name}\n")

        for guild in self.guilds:
            if guild.name == "The Traveling Trader":
                print(f"📁 Server: {guild.name}\n")

                print("Looking for these channels:")
                for target in TARGET_CHANNELS:
                    print(f"  - {target}")
                print()

                print("Matching channels found:")
                for channel in guild.text_channels:
                    if any(target in channel.name for target in TARGET_CHANNELS):
                        print(f"  ✅ Channel name: '{channel.name}'")
                        print(f"     Display:      #{channel.name}")
                        print(f"     ID:           {channel.id}")
                        print()

        await self.close()

client = CheckClient()
token = os.getenv("DISCORD_BOT_TOKEN")
client.run(token)
