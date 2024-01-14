import os
import re
import json
import asyncio
import aiofiles
from aiohttp import ClientSession
from dotenv import load_dotenv

load_dotenv()

discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
json_death_messages = os.getenv('JSON_DEATH_MESSAGES')
json_user_whitelist = os.getenv('JSON_USER_WHITELIST')
log_file_path = os.getenv('LOG_FILE_PATH')

# Set debug flag (change to False to disable debug output)
debug = False

last_position = 0
last_inode = 0
last_size = 0

processed_lines = set()

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
    return '|'.join(map(re.escape, death_messages))

async def load_user_whitelist():
    data = await read_json_file(json_user_whitelist)
    whitelist_names = [user.get('name', '') for user in data]
    return '|'.join(map(re.escape, whitelist_names))

async def process_log_line(line):
    if line not in processed_lines:
        print(f"Found matching line in log: {line.strip()}")
        payload = {'content': line.strip()}
        await write_to_discord_webhook(payload)
        processed_lines.add(line)

async def follow_log():
    global last_position, last_inode, last_size, processed_lines
    while True:
        try:
            current_inode = os.stat(log_file_path).st_ino
            current_size = os.stat(log_file_path).st_size

            if last_inode != current_inode or last_size > current_size:
                # File has been rotated or truncated, reset position and processed lines
                last_position = current_size
                last_inode = current_inode
                last_size = current_size
                processed_lines = set()  # Reset processed lines
                await asyncio.sleep(1)  # Sleep to avoid rapid checking :(

            async with aiofiles.open(log_file_path, 'r') as log_file:
                await log_file.seek(last_position)
                lines = await log_file.readlines()
                if not lines:
                    await asyncio.sleep(0.1)
                    continue

                death_messages_pattern = await load_death_messages()
                whitelist_pattern = await load_user_whitelist()

                for line in lines:
                    if (
                        re.search(death_messages_pattern, line, re.IGNORECASE) and
                        re.search(whitelist_pattern, line, re.IGNORECASE)
                    ):
                        yield line

                last_position = await log_file.tell()
                last_size = current_size

        except FileNotFoundError:
            # Log file not found, reset position and processed lines
            last_position = 0
            processed_lines = set()  # Reset processed lines
            await asyncio.sleep(1)  # Sleep to avoid rapid checking - computer is fast
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(1)  # Sleep to avoid rapid checking

async def main():
    async for line in follow_log():
        if line.strip():
            if debug:
                print(f"Debug: Matched line - {line.strip()}")
            await process_log_line(line)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Script terminated.")
