#!/usr/bin/env python3
import os
import re
import json
import urllib.request
import sys
import argparse

# Path to deathMessages.json relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "deathMessages.json")
WIKI_URL = "https://minecraft.wiki/w/Death_messages"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

if not sys.stdout.isatty():
    GREEN = RED = YELLOW = CYAN = RESET = ""

def fetch_wiki_content():
    print(f"{CYAN}Attempting to fetch death messages from Minecraft Wiki ({WIKI_URL})...{RESET}")
    req = urllib.request.Request(
        WIKI_URL,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"\n{RED}Error: Cloudflare or a network issue blocked the automatic download (Error: {e}){RESET}")
        print(f"{YELLOW}To run this script anyway, please do the following:")
        print(f"1. Open the Minecraft Wiki page in your web browser: {WIKI_URL}")
        print(f"2. Save the page source (or save page as HTML).")
        print(f"3. Run this script pointing to the saved file using the -f/--file flag:")
        print(f"   python3 {os.path.relpath(sys.argv[0])} --file /path/to/saved/page.html{RESET}\n")
        sys.exit(1)

def extract_messages(html_content):
    java_idx = html_content.find('id="Java_Edition"')
    bedrock_idx = html_content.find('id="Bedrock_Edition"')

    if java_idx == -1:
        print(f"{RED}Error: Could not locate the 'Java Edition' section in the HTML content.{RESET}")
        print(f"{YELLOW}If you used a saved web page, make sure you saved the complete HTML content.{RESET}")
        sys.exit(1)

    java_section = html_content[java_idx:bedrock_idx] if bedrock_idx != -1 else html_content[java_idx:]

    tags_pattern = re.compile(r'<(?:b|strong|td)[^>]*>(.*?)</(?:b|strong|td)>', re.DOTALL)
    raw_matches = tags_pattern.findall(java_section)

    death_messages = []
    for raw in raw_matches:
        # Strip internal tags
        cleaned = re.sub(r'<[^>]+>', '', raw)
        # Decode common HTML entities
        cleaned = cleaned.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&#95;', '_')
        cleaned = ' '.join(cleaned.split()).strip()

        is_msg = False
        if any(p in cleaned for p in ['<player>', '<entity>', '%1$s', '%2$s', '<player/mob>', '<killer>', '<mob>', '<accessory>', '<item>', '<block>', 'Intentional Game Design']):
            is_msg = True
        elif cleaned.startswith('death.attack.') or cleaned.startswith('death.fell.'):
            if not (cleaned.endswith('.item') or cleaned.endswith('.player') or cleaned.endswith('.player.player') or cleaned.startswith('death.fell.accident')):
                is_msg = True

        if is_msg and len(cleaned) < 200:
            death_messages.append(cleaned)

def normalize_msg(msg):
    msg = msg.replace('%1$s', '<player>')
    msg = msg.replace('%2$s', '<killer>')
    msg = msg.replace('%3$s', '<item/block>')

    msg = msg.replace('<entity>', '<player>')
    msg = msg.replace('<player/mob>', '<killer>')
    msg = msg.replace('<mob>', '<killer>')
    msg = msg.replace('<killer/accessory>', '<killer>')
    msg = msg.replace('<accessory>', '<item/block>')
    msg = msg.replace('<item>', '<item/block>')
    msg = msg.replace('<block>', '<item/block>')
    msg = msg.replace('<block name>', '<item/block>')

    return ' '.join(msg.split()).strip()

def generate_candidate(msg):
    candidate = normalize_msg(msg)
    candidate = candidate.replace('<player>', '')
    candidate = candidate.replace('<killer>', '')
    candidate = candidate.replace('<item/block>', '')

    candidate = candidate.strip(" .,!?'\"()[]{}")
    return ' '.join(candidate.split()).strip()

def is_matched(msg, patterns):
    instantiated = msg
    instantiated = instantiated.replace('<player>', 'Steve')
    instantiated = instantiated.replace('<killer>', 'Zombie')
    instantiated = instantiated.replace('<item/block>', 'Sword')

    for pattern in patterns:
        try:
            if re.search(pattern, instantiated):
                return True, pattern
        except Exception:
            if pattern in instantiated:
                return True, pattern
    return False, None

def main():
    parser = argparse.ArgumentParser(description="Check deathMessages.json against the Minecraft Wiki.")
    parser.add_argument("-j", "--json", default=DEFAULT_JSON_PATH, help="Path to deathMessages.json")
    parser.add_argument("-f", "--file", help="Path to a locally saved HTML file of the Minecraft Wiki Death Messages page")
    parser.add_argument("-w", "--write", action="store_true", help="Automatically write/add missing patterns to the json file")
    args = parser.parse_args()

    if not os.path.exists(args.json):
        print(f"{RED}Error: JSON file not found at {args.json}{RESET}")
        sys.exit(1)

    with open(args.json, "r", encoding="utf-8") as f:
        try:
            json_data = json.load(f)
        except Exception as e:
            print(f"{RED}Error parsing JSON file: {e}{RESET}")
            sys.exit(1)

    patterns = json_data.get("deathMessages", [])
    print(f"Loaded {len(patterns)} patterns from {args.json}")

    if args.file:
        if not os.path.exists(args.file):
            print(f"{RED}Error: Local HTML file not found at {args.file}{RESET}")
            sys.exit(1)
        print(f"{CYAN}Reading local HTML file: {args.file}{RESET}")
        with open(args.file, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = fetch_wiki_content()

    raw_messages = extract_messages(html_content)

    normalized_messages = sorted(list(set(normalize_msg(m) for m in raw_messages)))
    print(f"Found {len(normalized_messages)} unique death messages in the HTML source.")

    unmatched = []
    for msg in normalized_messages:
        matched, _ = is_matched(msg, patterns)
        if not matched:
            unmatched.append(msg)

    if not unmatched:
        print(f"\n{GREEN}All {len(normalized_messages)} Minecraft death messages are fully covered by your JSON file!{RESET}")
        sys.exit(0)

    print(f"\n{YELLOW}Found {len(unmatched)} unmatched death messages:{RESET}")
    suggested_additions = set()
    for u in unmatched:
        candidate = generate_candidate(u)
        print(f"- Message: {u}")
        print(f"  Suggested pattern: \"{candidate}\"")
        suggested_additions.add(candidate)

    if args.write:
        new_patterns = list(patterns)

        if "fell off a" in new_patterns:
            print(f"\nUpgrading \"fell off a\" to \"fell off\" for better vine/scaffolding coverage...")
            new_patterns[new_patterns.index("fell off a")] = "fell off"

        for candidate in sorted(suggested_additions):
            if candidate not in new_patterns:
                still_unmatched = False
                for u in unmatched:
                    matched, _ = is_matched(u, new_patterns)
                    if not matched:
                        temp_patterns = new_patterns + [candidate]
                        if is_matched(u, temp_patterns)[0]:
                            still_unmatched = True
                            break

                if still_unmatched or candidate.startswith("death."):
                    new_patterns.append(candidate)
                    print(f"Adding pattern: \"{candidate}\"")


        new_patterns = sorted(list(set(new_patterns)))
        json_data["deathMessages"] = new_patterns

        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
            f.write("\n")

        print(f"\n{GREEN}Successfully updated {args.json}! (Added/optimized patterns, total is now {len(new_patterns)}){RESET}")
    else:
        print(f"\n{CYAN}To automatically update the JSON file, run this script with the --write (or -w) flag:{RESET}")
        print(f"python3 {os.path.relpath(sys.argv[0])} --write")

if __name__ == "__main__":
    main()
