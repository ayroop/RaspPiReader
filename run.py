
import sys
import os
import argparse
import time
import logging
from PyQt5 import QtWidgets

from RaspPiReader import pool
from RaspPiReader.ui.login_form_handler import LoginFormHandler
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.sync import SyncThread
from RaspPiReader.libs.demo_data_reader import data as demo_data
from RaspPiReader.libs.plc_communication import initialize_plc_communication_async
from RaspPiReader.libs.logging_config import setup_logging
from RaspPiReader.ui.splash_screen import SplashScreen

def setup_application():
    """Setup application configurations and logging"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting RaspPiReader application")
    return logger

def process_arguments():
    """Process command line arguments"""
    parser = argparse.ArgumentParser(description="RaspPiReader - PLC Data Reader Application")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--demo', action='store_true', help='Run in demo mode')
    args = parser.parse_args()
    pool.set('debug', args.debug)
    pool.set('demo', args.demo)
    return args

def initialize_components(logger, args):
    """Initialize application components"""
    demo_mode = pool.config('demo', bool, False) or args.demo
    pool.set('demo', demo_mode)
    logger.info(f"Demo mode: {demo_mode}")

    logger.info("Initializing local database...")
    db = Database("sqlite:///local_database.db")
    db.create_tables()

    # Start PLC initialization in background to avoid blocking startup
    logger.info("Starting PLC communication initialization in background...")

    def plc_init_callback(success, error):
        if success:
            logger.info("PLC communication initialized successfully")
            # Start the connection monitor in the main thread
            from RaspPiReader.libs.plc_communication import connection_monitor, ConnectionMonitor
            if connection_monitor is None:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    connection_monitor = ConnectionMonitor(app)
                    connection_monitor.start(30000)  # check every 30 seconds
        else:
            logger.error(f"Failed to initialize PLC communication: {error}")

    # Start initialization in background with the corrected callback signature
    initialize_plc_communication_async(plc_init_callback)

    return db

def start_sync_thread(logger):
    """Start the database sync thread"""
    logger.info("Starting database sync thread...")
    sync_thread = SyncThread()
    sync_thread.start()
    logger.info("Database sync thread started")
    return sync_thread

def show_splash_screen(logger):
    """Show the splash screen with a progress bar"""
    logger.info("Launching splash screen...")
    splash = SplashScreen()
    splash.show()

    for i in range(101):
        QtWidgets.QApplication.processEvents()
        splash.progress_bar.setValue(i)
        time.sleep(0.02)

    return splash

def Main():
    """Main application entry point"""
    logger = setup_application()
    args = process_arguments()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    app = QtWidgets.QApplication(sys.argv)

    try:
        initialize_components(logger, args)
        start_sync_thread(logger)
        splash = show_splash_screen(logger)

        logger.info("Launching login form...")
        login_form = LoginFormHandler()
        splash.finish(login_form)
        login_form.show()

        return app.exec_()
    except Exception as e:
        logger.error(f"Error during application startup: {e}", exc_info=True)
        error_dialog = QtWidgets.QMessageBox()
        error_dialog.setIcon(QtWidgets.QMessageBox.Critical)
        error_dialog.setWindowTitle("Application Error")
        error_dialog.setText("An error occurred during application startup.")
        error_dialog.setDetailedText(str(e))
        error_dialog.exec_()
        return 1

if __name__ == "__main__":
    sys.exit(Main())
