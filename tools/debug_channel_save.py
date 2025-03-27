import os
import sys
import logging
import sqlite3

# Add the parent directory to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='channel_debug.log',
    filemode='w'
)
logger = logging.getLogger('channel_save_debug')

def check_database_connection():
    """Verify database connection and check if channels table exists."""
    try:
        logger.info("Attempting to connect to database")
        db_path = os.path.join(parent_dir, 'local_database.db')
        logger.info(f"Database path: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if channels table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plc_channels'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            logger.info("Channels table exists in database")
            
            # Check table structure
            cursor.execute("PRAGMA table_info(plc_channels)")
            columns = cursor.fetchall()
            logger.info(f"Table columns: {columns}")
            
            # Count number of records
            cursor.execute("SELECT COUNT(*) FROM plc_channels")
            count = cursor.fetchone()[0]
            logger.info(f"Number of channel records: {count}")
            
            # Sample some data
            cursor.execute("SELECT * FROM plc_channels LIMIT 5")
            sample = cursor.fetchall()
            logger.info(f"Sample channel data: {sample}")
        else:
            logger.error("Channels table does not exist in the database!")
            
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False

def simulate_channel_save(channel_data):
    """Simulate saving channel data to debug the process."""
    try:
        logger.info(f"Attempting to save channel data: {channel_data}")
        
        db_path = os.path.join(parent_dir, 'local_database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # This is a generic example - adjust the SQL according to your actual schema
        sql = """INSERT OR REPLACE INTO plc_channels 
                 (name, address, data_type, read_interval, enabled) 
                 VALUES (?, ?, ?, ?, ?)"""
        
        logger.info(f"Executing SQL: {sql}")
        cursor.execute(sql, (
            channel_data.get('name', 'test_channel'),
            channel_data.get('address', '0'),
            channel_data.get('data_type', 'integer'),
            channel_data.get('read_interval', 1000),
            channel_data.get('enabled', 1),
            channel_data.get('decimal_point', 0)
        ))
        
        conn.commit()
        logger.info("Channel data saved successfully")
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to save channel data: {str(e)}")
        return False

def check_ui_refresh():
    """Check if the UI is properly refreshing after save."""
    logger.info("Checking UI refresh mechanism")
    # This would depend on your specific UI implementation
    # You might need to trace through your UI code to see how it refreshes
    logger.info("You should manually check if the UI is calling refresh methods after save")
    
    # Suggestions for UI debugging
    logger.info("UI Debugging suggestions:")
    logger.info("1. Add print statements in UI refresh methods")
    logger.info("2. Check if data load functions are called after save")
    logger.info("3. Verify that the UI is binding to the correct data source")

if __name__ == "__main__":
    logger.info("=== Starting Channel Save Debugging ===")
    
    # Check database
    if check_database_connection():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed - fix this before proceeding")
        sys.exit(1)
    
    # Test saving a sample channel
    test_channel = {
        'name': 'DEBUG_TEST_CHANNEL',
        'address': '100',
        'data_type': 'integer',
        'read_interval': 1000,
        'enabled': 1
    }
    
    if simulate_channel_save(test_channel):
        logger.info("Test channel save successful")
    else:
        logger.error("Test channel save failed")
    
    # Check UI refresh
    check_ui_refresh()
    
    logger.info("=== Channel Save Debugging Complete ===")
    logger.info("Check channel_debug.log for detailed results")
    print("Debug complete. See channel_debug.log for results.")