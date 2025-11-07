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

# --------------------------------------------------------------------------- #
#                              ENVIRONMENT SETUP
# --------------------------------------------------------------------------- #

load_dotenv()

minecraft_season = os.getenv("MINECRAFT_SEASON")
if not minecraft_season or not minecraft_season.isdigit():
    raise ValueError("MINECRAFT_SEASON environment variable must be a number")

discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
json_death_messages = os.getenv("JSON_DEATH_MESSAGES")
json_user_whitelist = os.getenv("JSON_USER_WHITELIST")
json_debug_bots = os.getenv("JSON_DEBUG_BOTS")
json_humbled_responses = os.getenv("JSON_HUMBLED_RESPONSES")
log_file_path = os.getenv("LOG_FILE_PATH")
db_file_path = os.getenv("DB_FILE_PATH", "deaths.db")

season_column = f"season_{minecraft_season}"
debug = False

# State variables
last_position = 0
last_inode = 0
last_size = 0
processed_lines = set()


# --------------------------------------------------------------------------- #
#                              DATABASE FUNCTIONS
# --------------------------------------------------------------------------- #

def initialize_database():
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deaths (
                username TEXT PRIMARY KEY,
                death_count INTEGER DEFAULT 0
            )
        """)

        cursor.execute("PRAGMA table_info(deaths)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        if season_column not in existing_columns:
            cursor.execute(f"ALTER TABLE deaths ADD COLUMN {season_column} INTEGER DEFAULT 0")

        conn.commit()


async def increment_death_count(username):
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO deaths (username, death_count, {season_column})
            VALUES (?, 1, 1)
            ON CONFLICT(username) DO UPDATE SET
                death_count = death_count + 1,
                {season_column} = {season_column} + 1
        """, (username,))
        cursor.execute(f"SELECT death_count, {season_column} FROM deaths WHERE username = ?", (username,))
        return cursor.fetchone()


async def get_death_count(username):
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {season_column} FROM deaths WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else 0


async def get_scoreboard():
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT username, {season_column} FROM deaths ORDER BY {season_column} DESC")
        scoreboard = cursor.fetchall()

    debug_bots = await load_debug_bots()
    debug_bot_names = {normalize_username(name) for name in debug_bots}

    filtered_scoreboard = [
        (username, deaths)
        for username, deaths in scoreboard
        if normalize_username(username) not in debug_bot_names
    ]

    return filtered_scoreboard


# --------------------------------------------------------------------------- #
#                              JSON / FILE HELPERS
# --------------------------------------------------------------------------- #

async def read_json_file(file_path):
    async with aiofiles.open(file_path, "r") as file:
        content = await file.read()
    return json.loads(content)


async def load_death_messages():
    data = await read_json_file(json_death_messages)
    return [re.escape(msg) for msg in data.get("deathMessages", [])]


async def load_humbled_responses():
    data = await read_json_file(json_humbled_responses)
    humbled_responses = data.get("humbledResponses", [])
    return random.choice(humbled_responses)


async def load_user_whitelist():
    data = await read_json_file(json_user_whitelist)
    return [re.escape(user.get("name", "")) for user in data]


async def load_debug_bots():
    data = await read_json_file(json_debug_bots)
    return [re.escape(user.get("name", "")) for user in data]


# --------------------------------------------------------------------------- #
#                              LOG PROCESSING
# --------------------------------------------------------------------------- #

def normalize_username(username: str):
    return re.sub(r"\\", "", username).lower()


def transform_line(line):
    """Remove timestamp and '[Server thread/INFO]:' portion."""
    return re.sub(r"^\[[\d+:]*\] \[Server thread/INFO\]: ", "", line)


async def write_to_discord_webhook(content):
    async with ClientSession() as session:
        async with session.post(discord_webhook_url, json=content):
            pass


async def process_log_line(line, whitelist_patterns, debug_bots):
    """Handle a single matched log line."""
    if "lost connection" in line.lower():
        return  # Ignore bot disconnect messages

    if line in processed_lines:
        return

    transformed_line = transform_line(line)
    combined_patterns = whitelist_patterns + debug_bots

    if any(transformed_line.lower().startswith(name.lower()) for name in combined_patterns):
        print(f"Found matching line in log: {line.strip()}")
        print(f"Sending to Discord: {transformed_line.strip()}")

        username = transformed_line.split()[0]
        death_count, season_count = await increment_death_count(username)
        humbled_response_text = await load_humbled_responses()

        payload = {
            "embeds": [
                {
                    "type": "rich",
                    "title": humbled_response_text.strip(),
                    "description": (
                        f"{transformed_line.strip()} "
                        f"(Season {minecraft_season} Deaths: {season_count}, Total Deaths: {death_count})"
                    ),
                    "color": 0xb7ff00,
                    "footer": {"text": "Brought to you by the Humbler gang."}
                }
            ]
        }

        await write_to_discord_webhook(payload)
        processed_lines.add(line)


async def follow_log():
    """Watch and yield new lines that match death + user patterns."""
    global last_position, last_inode, last_size, processed_lines

    death_messages_patterns = await load_death_messages()
    whitelist_patterns = await load_user_whitelist()
    debug_bots = await load_debug_bots()

    while True:
        try:
            stat = os.stat(log_file_path)
            current_inode, current_size = stat.st_ino, stat.st_size

            # Handle rotation/truncation
            if last_inode != current_inode or last_size > current_size:
                last_position, last_inode, last_size = current_size, current_inode, current_size
                processed_lines.clear()
                await asyncio.sleep(1)

            async with aiofiles.open(log_file_path, "r") as log_file:
                await log_file.seek(last_position)
                lines = await log_file.readlines()

                if not lines:
                    await asyncio.sleep(0.1)
                    continue

                for line in lines:
                    if "lost connection" in line.lower():
                        continue

                    if (
                        any(re.search(pattern, line, re.IGNORECASE) for pattern in death_messages_patterns)
                        and any(re.search(pattern, line, re.IGNORECASE) for pattern in whitelist_patterns + debug_bots)
                    ):
                        yield line

                last_position = await log_file.tell()
                last_size = current_size

        except FileNotFoundError:
            last_position = 0
            processed_lines.clear()
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
            whitelist_patterns = await load_user_whitelist()
            debug_bots = await load_debug_bots()
            await process_log_line(line, whitelist_patterns, debug_bots)


# --------------------------------------------------------------------------- #
#                              DISCORD BOT SETUP
# --------------------------------------------------------------------------- #

async def init_discord_bot():
    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        print("Error: DISCORD_TOKEN environment variable not set")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    humbler_group = app_commands.Group(name="humbler", description="Commands for the Humbler bot")

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user.name}")
        bot.tree.add_command(humbler_group)
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    # --- UPDATED SECTION STARTS HERE ---
    async def load_whitelist_players():
        """Load player names from the whitelist JSON file."""
        if not json_user_whitelist or not os.path.exists(json_user_whitelist):
            print(f"⚠️  Whitelist file not found: {json_user_whitelist}")
            return []
        try:
            async with aiofiles.open(json_user_whitelist, "r") as f:
                data = json.loads(await f.read())
                return [entry.get("name", "") for entry in data if "name" in entry]
        except Exception as e:
            print(f"⚠️  Error loading whitelist: {e}")
            return []

    @humbler_group.command(name="deaths", description="Check a player's death count for the current season")
    @app_commands.describe(player_name="The Minecraft username to look up")
    async def deaths_subcommand(interaction: discord.Interaction, player_name: str):
        death_count = await get_death_count(player_name)
        await interaction.response.send_message(
            f"{player_name} has died {death_count} time(s) in Season {minecraft_season}"
        )

    @deaths_subcommand.autocomplete("player_name")
    async def deaths_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete Minecraft usernames from the whitelist file."""
        players = await load_whitelist_players()
        if not current:
            return [app_commands.Choice(name=p, value=p) for p in players[:25]]
        matches = [p for p in players if current.lower() in p.lower()]
        return [app_commands.Choice(name=p, value=p) for p in matches[:25]]
    # --- UPDATED SECTION ENDS HERE ---

    @humbler_group.command(name="scoreboard", description="Display the death scoreboard for the current season")
    async def scoreboard_subcommand(interaction: discord.Interaction):
        scoreboard = await get_scoreboard()
        if not scoreboard:
            await interaction.response.send_message("The scoreboard is empty! No one has been humbled yet.")
            return

        response = f"Season {minecraft_season} Humbler Scoreboard\n"
        for i, (username, deaths) in enumerate(scoreboard, 1):
            response += f"{i}. **{username}**: {deaths} deaths\n"

        await interaction.response.send_message(response)

    await bot.start(discord_token)


# --------------------------------------------------------------------------- #
#                                  MAIN LOOP
# --------------------------------------------------------------------------- #

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

