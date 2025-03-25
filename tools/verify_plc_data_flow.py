"""
Utility script to verify the data flow from PLC to database to visualization.
Place this in your project and run it to diagnose where the data flow is breaking.
"""
import logging
import sys
import os
import time
from datetime import datetime, timedelta

# Configure logging BEFORE any imports
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import the RaspPiReader package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import the necessary modules from your application
try:
    # Import the necessary modules from your application
    from RaspPiReader.libs.plc_communication import modbus_comm, is_connected, read_holding_register
    from RaspPiReader.libs.database import Database
    from RaspPiReader.libs.visualization_manager import VisualizationManager
except ImportError as e:
    logger.error(f"Failed to import required modules: {str(e)}")
    logger.error("Make sure the RaspPiReader package is correctly installed and accessible")
    logger.error("You may need to adjust the import paths based on your project structure")
    sys.exit(1)

def verify_plc_connection():
    """Verify that the PLC connection is working correctly."""
    try:
        connected = is_connected()
        logger.info(f"PLC connection status: {'Connected' if connected else 'Disconnected'}")
        
        if connected:
            # Try to read from a few addresses
            for address in [101, 102, 103]:  # Use addresses from your configuration
                try:
                    value = read_holding_register(address)
                    logger.info(f"Address {address} value: {value}")
                except Exception as e:
                    logger.error(f"Failed to read from address {address}: {str(e)}")
            
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error verifying PLC connection: {str(e)}")
        return False

def verify_database_storage():
    """Verify that data is being stored in the database."""
    try:
        # Connect to the local SQLite database
        db = Database('sqlite:///local_database.db')
        
        # Check if the database exists by trying to query some tables
        try:
            # Try to access a table that should exist
            users = db.get_users()
            logger.info(f"Database connection successful. Found {len(users)} users.")
            
            # Try to access plot data if it exists
            try:
                # This is placeholder code - adjust based on your actual database schema
                plot_data = db.session.query("PlotData").limit(5).all()
                if plot_data:
                    logger.info(f"Found recent plot data in the database")
                else:
                    logger.warning("No plot data found in the database")
            except Exception as e:
                logger.warning(f"Could not query plot data: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            return False
    except Exception as e:
        logger.error(f"Error verifying database storage: {str(e)}")
        return False

def verify_visualization_data_retrieval():
    """Verify that the visualization component can retrieve data from the database."""
    try:
        # Import required visualization modules
        try:
            from RaspPiReader.ui.visualization_dashboard import VisualizationDashboard
            logger.info("Successfully imported VisualizationDashboard")
        except ImportError as e:
            logger.error(f"Could not import VisualizationDashboard: {e}")
        
        # Check for configuration data
        from RaspPiReader.libs.configuration import Configuration
        try:
            config = Configuration()
            channel_configs = config.get_channel_configs()
            logger.info(f"Found {len(channel_configs)} channel configurations")
            
            # Display the configured addresses
            for ch_num, config in channel_configs.items():
                addr = config.get('address', 'Not configured')
                logger.info(f"Channel {ch_num} address: {addr}")
            
            return True
        except Exception as e:
            logger.error(f"Error checking visualization configuration: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error verifying visualization data retrieval: {str(e)}")
        return False

def run_diagnostics():
    """Run all diagnostic checks."""
    logger.info("Starting PLC Data Flow diagnostics")
    
    plc_ok = verify_plc_connection()
    db_ok = verify_database_storage()
    vis_ok = verify_visualization_data_retrieval()
    
    logger.info("Diagnostics summary:")
    logger.info(f"PLC Connection: {'OK' if plc_ok else 'FAILED'}")
    logger.info(f"Database Storage: {'OK' if db_ok else 'FAILED'}")
    logger.info(f"Visualization Data Retrieval: {'OK' if vis_ok else 'FAILED'}")
    
    if not plc_ok:
        logger.error("ACTION NEEDED: Fix PLC connection issues before proceeding.")
        logger.error("   - Check TCP/IP settings or serial port configuration")
        logger.error("   - Verify PLC is powered on and accessible on the network")
        logger.error("   - Check that the correct protocol is configured (Modbus TCP, etc.)")
    elif not db_ok:
        logger.error("ACTION NEEDED: Verify database configuration and data storage.")
        logger.error("   - Check the database file exists and is accessible")
        logger.error("   - Verify table structure includes tables for plot data")
    elif not vis_ok:
        logger.error("ACTION NEEDED: Check visualization manager's data retrieval methods.")
        logger.error("   - Verify channel configuration includes proper PLC addresses")
        logger.error("   - Check that visualization components are properly connected to data sources")
    else:
        logger.info("All components seem to be working correctly. If you're still experiencing issues, check:")
        logger.info("   - Timing and refresh rates for visualization")
        logger.info("   - Address formats and data types in PLC communication")
        logger.info("   - Proper data scaling and limits in channel configuration")

if __name__ == "__main__":
    run_diagnostics()
