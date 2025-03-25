import sqlite3

# Path to your SQLite database file
db_path = "local_database.db"

# SQL commands to add the columns
alter_table_sql = [
    "ALTER TABLE channel_config_settings ADD COLUMN limit_low INTEGER DEFAULT 0;",
    "ALTER TABLE channel_config_settings ADD COLUMN limit_high INTEGER DEFAULT 100;"
]

try:
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Execute each SQL command
    for sql in alter_table_sql:
        cursor.execute(sql)
        print(f"Executed: {sql}")

    # Commit the changes
    conn.commit()
    print("Columns added successfully.")

except sqlite3.OperationalError as e:
    print(f"Error: {e}")
finally:
    # Close the connection
    conn.close()