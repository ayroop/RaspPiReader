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
    
    # Process command line arguments
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)
    
    try:
        # Check if we're in demo mode
        demo_mode = pool.config('demo', bool, False) or args.demo
        pool.set('demo', demo_mode)
        
        # Check simulation mode - DO NOT DEFAULT TO TRUE!
        simulation_mode = pool.config('plc/simulation_mode', bool, False)
        logger.info(f"Simulation mode: {simulation_mode}")
        logger.info(f"Demo mode: {demo_mode}")
        
        # Initialize database
        logger.info("Initializing local database...")
        db = Database("sqlite:///local_database.db")
        db.create_tables()
        
        # Initialize PLC communication
        logger.info("Initializing PLC communication...")
        success = initialize_plc_communication()
        if success:
            logger.info("PLC communication initialized successfully")
        else:
            logger.error("Failed to initialize PLC communication")
        
        # Start database sync thread
        logger.info("Starting database sync thread...")
        sync_thread = SyncThread()
        sync_thread.start()
        logger.info("Database sync thread started")
        
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