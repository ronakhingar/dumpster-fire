#!/usr/bin/env python3
"""Quick script to list all Discord channels"""

import discord
import os
from dotenv import load_dotenv

load_dotenv()

class ListClient(discord.Client):
    async def on_ready(self):
        print(f"\n✅ Logged in as: {self.user.name}\n")

        for guild in self.guilds:
            print(f"📁 Server: {guild.name}")
            print(f"   Total channels: {len(guild.text_channels)}")
            print()

            for channel in guild.text_channels:
                print(f"   #{channel.name}")
            print()

        await self.close()

client = ListClient()
token = os.getenv("DISCORD_BOT_TOKEN")
client.run(token)
