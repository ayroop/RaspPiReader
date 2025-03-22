import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_plc_schema():
    """Add simulation_mode column to plc_comm_settings table if it doesn't exist"""
    logger.info("Updating PLC communication settings schema...")
    
    try:
        # Connect to the database
        conn = sqlite3.connect("local_database.db")
        cursor = conn.cursor()
        
        # Check if simulation_mode column exists
        cursor.execute("PRAGMA table_info(plc_comm_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'simulation_mode' not in columns:
            logger.info("Adding simulation_mode column to plc_comm_settings table")
            cursor.execute("ALTER TABLE plc_comm_settings ADD COLUMN simulation_mode BOOLEAN DEFAULT 0")
            conn.commit()
            logger.info("Schema updated successfully!")
        else:
            logger.info("simulation_mode column already exists, no update needed")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating schema: {e}")
        return False

if __name__ == "__main__":
    update_plc_schema()