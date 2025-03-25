import sqlite3

# Path to SQLite database file
db_path = "local_database.db"

try:
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query the table schema
    cursor.execute("PRAGMA table_info(channel_config_settings);")
    columns = cursor.fetchall()

    print("Table Schema:")
    for column in columns:
        print(column)

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()