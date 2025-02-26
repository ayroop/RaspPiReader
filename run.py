import sys
import os
import argparse
import logging
from PyQt5 import QtWidgets

from RaspPiReader import pool
from RaspPiReader.ui.login_form_handler import LoginFormHandler
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.sync import SyncThread
from RaspPiReader.libs.demo_data_reader import data as demo_data
from RaspPiReader.libs.plc_communication import initialize_plc_communication
from RaspPiReader.libs.logging_config import setup_logging

def Main():
    """Main application entry point"""
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting RaspPiReader application")
    
    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)
    
    try:
        # Check if we're in demo mode
        demo_mode = pool.config('demo', bool, False) or args.demo
        if demo_mode:
            pool.set('demo', True)
            pool.set_config('plc/simulation_mode', True)  # Explicitly enable simulation in demo mode
            logger.info("Demo mode enabled: Using simulation for PLC communications")
        else:
            # Make sure simulation mode is explicitly disabled unless set otherwise
            simulation_mode = pool.config('plc/simulation_mode', bool, False)
            # Override simulation mode with the command line argument
            if args.debug:
                simulation_mode = True
                pool.set_config('plc/simulation_mode', True)
                logger.info("Debug mode enabled: Using simulation for PLC communications")
            
            logger.info(f"Simulation mode: {simulation_mode}")
        
        logger.info(f"Demo mode: {demo_mode}")

        if demo_mode:
            # Ensure demo data is loaded into the database
            logger.info("Loading demo data into the database...")
            demo_data  # This will trigger the loading of demo data
        else:
            # Ensure local SQLite database is initialized
            logger.info("Initializing local database...")
            local_db = Database("sqlite:///local_database.db")
            local_db.create_tables()

            # Initialize PLC communication with settings from database/config
            logger.info("Initializing PLC communication...")
            plc_initialized = initialize_plc_communication()
            if plc_initialized:
                logger.info("PLC communication initialized successfully")
            else:
                logger.warning("Failed to initialize PLC communication. Check settings.")

            # Start the sync thread
            logger.info("Starting database sync thread...")
            sync_thread = SyncThread(interval=60)  # Sync every 60 seconds
            sync_thread.daemon = True  # Make thread exit when main program exits
            sync_thread.start()
            logger.info("Database sync thread started")
            # Store the sync thread in the pool to prevent garbage collection
            pool.set('sync_thread', sync_thread)

        # Launch login form
        logger.info("Launching login form...")
        login_form = LoginFormHandler()
        login_form.show()
        
        # Execute application
        return app.exec_()
    except Exception as e:
        logger.error(f"Error during application startup: {e}", exc_info=True)
        # Show error message to user
        error_dialog = QtWidgets.QMessageBox()
        error_dialog.setIcon(QtWidgets.QMessageBox.Critical)
        error_dialog.setWindowTitle("Application Error")
        error_dialog.setText("An error occurred during application startup.")
        error_dialog.setDetailedText(str(e))
        error_dialog.exec_()
        return 1

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="RaspPiReader - PLC Data Reader Application")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--demo', action='store_true', help='Run in demo mode')
    args = parser.parse_args()
    
    # Store command line arguments in pool
    pool.set('debug', args.debug)
    pool.set('demo', args.demo)
    
    # Run the application
    sys.exit(Main())