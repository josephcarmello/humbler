#!/usr/bin/env python3
import sqlite3
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "deaths.db")
TABLE_NAME = "deaths"

def reset_seasonal(season_number: int):
    column_name = f"season_{season_number}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(f"PRAGMA table_info({TABLE_NAME});")
    columns = [col[1] for col in cursor.fetchall()]
    if column_name not in columns:
        print(f"Column '{column_name}' not found in table '{TABLE_NAME}'.")
        conn.close()
        sys.exit(1)

    update_query = f"""
        UPDATE {TABLE_NAME}
        SET death_count = death_count - {column_name},
            {column_name} = 0;
    """
    cursor.execute(update_query)
    conn.commit()

    print(f"Successfully reset '{column_name}' to 0 and adjusted 'death_count' accordingly.")

    conn.close()



if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reset_seasonal.py <season_number>")
        sys.exit(1)

    try:
        season_num = int(sys.argv[1])
    except ValueError:
        print("The argument must be a number (e.g. 7).")
        sys.exit(1)

    reset_seasonal(season_num)

