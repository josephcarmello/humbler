#!/usr/bin/env python3
import asyncio
import json
import os
import random
import re
import sqlite3

import aiofiles
import discord
from aiohttp import ClientSession
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

minecraft_season = os.getenv('MINECRAFT_SEASON')
discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
json_death_messages = os.getenv('JSON_DEATH_MESSAGES')
json_user_whitelist = os.getenv('JSON_USER_WHITELIST')
json_debug_bots = os.getenv('JSON_DEBUG_BOTS')
json_humbled_responses = os.getenv('JSON_HUMBLED_RESPONSES')
log_file_path = os.getenv('LOG_FILE_PATH')
db_file_path = os.getenv('DB_FILE_PATH', 'deaths.db')  # Default to 'deaths.db' if not provided

debug = False

last_position = 0
last_inode = 0
last_size = 0
processed_lines = set()

def initialize_database():
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deaths (
                username TEXT PRIMARY KEY,
                death_count INTEGER DEFAULT 0,
                season_6 INTEGER DEFAULT 0
            )
        """)
        conn.commit()

async def increment_death_count(username):
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO deaths (username, death_count, season_6)
            VALUES (?, 1, 1)
            ON CONFLICT(username) DO UPDATE SET 
                death_count = death_count + 1,
                season_6 = season_6 + 1
        """, (username,))
        cursor.execute("SELECT death_count, season_6 FROM deaths WHERE username = ?", (username,))
        return cursor.fetchone()

async def read_json_file(file_path):
    async with aiofiles.open(file_path, 'r') as file:
        content = await file.read()
    return json.loads(content)

async def write_to_discord_webhook(content):
    async with ClientSession() as session:
        async with session.post(discord_webhook_url, json=content) as resp:
            pass

async def load_death_messages():
    data = await read_json_file(json_death_messages)
    death_messages = data.get('deathMessages', [])
    return [re.escape(msg) for msg in death_messages]

async def load_humbled_responses():
    data = await read_json_file(json_humbled_responses)
    humbled_responses = data.get('humbledResponses', [])
    return random.choice(humbled_responses)

async def load_user_whitelist():
    data = await read_json_file(json_user_whitelist)
    whitelist_names = [user.get('name', '') for user in data]
    return [re.escape(name) for name in whitelist_names]

async def load_debug_bots():
    data = await read_json_file(json_debug_bots)
    debug_bots = [user.get('name', '') for user in data]
    return [re.escape(name) for name in debug_bots]

def transform_line(line):
    # Remove timestamp and [Server thread/INFO]: portion
    line_without_info = re.sub(r'^\[[\d+:]*\] \[Server thread/INFO\]: ', '', line)
    return line_without_info

async def process_log_line(line):
    if "lost connection" in line.lower():
        return #fuckin bots

    if line not in processed_lines:
        transformed_line = transform_line(line)

        # Check if the transformed line starts with any name from the whitelist
        whitelist_patterns = await load_user_whitelist()
        debug_bots = await load_debug_bots()

        combined_patterns = whitelist_patterns + debug_bots

        if any(transformed_line.lower().startswith(name.lower()) for name in combined_patterns):
            print(f"Found matching line in log: {line.strip()}")
            print(f"Sending the following to Discord: {transformed_line.strip()}")

            username = transformed_line.split()[0]
            death_count, season_count = await increment_death_count(username)

            humbled_response_text = await load_humbled_responses()
            payload = {
                "embeds": [
                    {
                        "type": "rich",
                        "title": humbled_response_text.strip(),
                        "description": f"{transformed_line.strip()} (Season 6 Deaths: {season_count}, Total Deaths: {death_count})",
                        "color": 0xb7ff00,
                        "footer": {
                            "text": "Brought to you by the Humbler gang."
                        }
                    }
                ]
            }

            await write_to_discord_webhook(payload)
            processed_lines.add(line)

async def follow_log():
    global last_position, last_inode, last_size, processed_lines
    while True:
        try:
            current_inode = os.stat(log_file_path).st_ino
            current_size = os.stat(log_file_path).st_size

            if last_inode != current_inode or last_size > current_size:
                # File has been rotated or truncated
                last_position = current_size
                last_inode = current_inode
                last_size = current_size
                processed_lines = set()
                await asyncio.sleep(1)  # Sleep to avoid rapid checking :(

            async with aiofiles.open(log_file_path, 'r') as log_file:
                await log_file.seek(last_position)
                lines = await log_file.readlines()
                if not lines:
                    await asyncio.sleep(0.1)
                    continue

                death_messages_patterns = await load_death_messages()
                whitelist_patterns = await load_user_whitelist()
                debug_bots = await load_debug_bots()

                combined_patterns = whitelist_patterns + debug_bots

                for line in lines:
                    if "lost connection" in line.lower():
                        continue #fuckin bots

                    if (
                        any(re.search(pattern, line, re.IGNORECASE) for pattern in death_messages_patterns) and
                        any(re.search(pattern, line, re.IGNORECASE) for pattern in combined_patterns)
                    ):
                        yield line

                last_position = await log_file.tell()
                last_size = current_size

        except FileNotFoundError:
            last_position = 0
            processed_lines = set()
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(1)

async def log_processor():
    initialize_database()
    async for line in follow_log():
        if line.strip():
            if debug:
                print(f"Debug: Matched line - {line.strip()}")
            await process_log_line(line)

async def get_death_count(username):
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT season_6 FROM deaths WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else 0

async def get_scoreboard():
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, season_6 FROM deaths ORDER BY season_6 DESC")
        return cursor.fetchall()

async def death_command(ctx, player_name):
    death_count = await get_death_count(player_name)
    await ctx.send(f"{player_name} has died {death_count} times in Season 6")

async def scoreboard_command(ctx):
    scoreboard = await get_scoreboard()
    response = "Season 6 Scoreboard:\n"
    for i, (username, deaths) in enumerate(scoreboard, 1):
        response += f"{i}. {username}: {deaths} deaths\n"
    await ctx.send(response)

async def init_discord_bot():
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        print("Error: DISCORD_TOKEN environment variable not set")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="?????", intents=intents)
    humbler_group = app_commands.Group(name="humbler", description="Commands for the Humbler bot")

    @bot.event
    async def on_ready():
        print(f'Logged in as {bot.user.name}')
        bot.tree.add_command(humbler_group)
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    @humbler_group.command(name="deaths", description="Check a player's death count for the current season")
    @app_commands.describe(player_name="The Minecraft username to look up")
    async def deaths_subcommand(interaction, player_name):
        death_count = await get_death_count(player_name)
        await interaction.response.send_message(f"{player_name} has died {death_count} time(s) in Season 6")

    @humbler_group.command(name="scoreboard", description="Display the death scoreboard for the current season")
    async def scoreboard_subcommand(interaction):
        scoreboard = await get_scoreboard()
        if not scoreboard:
            await interaction.response.send_message("The scoreboard is empty! No one has been humbled yet")
            return

        response = "Season 6 Humbler Scoreboard\n"
        for i, (username, deaths) in enumerate(scoreboard, 1):
            response += f"{i}. {username}: {deaths} deaths\n"

        await interaction.response.send_message(response)
        
    await bot.start(discord_token)

async def main():
    await asyncio.gather(
        log_processor(),
        init_discord_bot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Script terminated")
