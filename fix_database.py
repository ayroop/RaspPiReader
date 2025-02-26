import sqlite3
import os
import sys

def fix_database():
    """Simple fix for database to avoid logging recursion errors"""
    print("Starting database fix...")
    
    try:
        # Backup existing database
        db_path = "local_database.db"
        if os.path.exists(db_path):
            backup_path = f"{db_path}.bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            print(f"Backing up database to {backup_path}")
            import shutil
            shutil.copy2(db_path, backup_path)
        
        # Connect directly to the database
        conn = sqlite3.connect("local_database.db")
        cursor = conn.cursor()
        
        # Check if plc_comm_settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plc_comm_settings'")
        if cursor.fetchone():
            print("Dropping existing plc_comm_settings table")
            cursor.execute("DROP TABLE plc_comm_settings")
        
        # Create fresh table with proper fields
        print("Creating new plc_comm_settings table")
        cursor.execute("""
        CREATE TABLE plc_comm_settings (
            id INTEGER PRIMARY KEY,
            comm_mode TEXT NOT NULL,
            tcp_host TEXT,
            tcp_port INTEGER,
            com_port TEXT,
            baudrate INTEGER,
            bytesize INTEGER,
            parity TEXT,
            stopbits REAL,
            timeout REAL
        )
        """)
        
        conn.commit()
        conn.close()
        print("Database fixed successfully!")
        
    except Exception as e:
        print(f"Error fixing database: {e}")
        return False
    
    return True

if __name__ == "__main__":
    fix_database()