import threading
import time
import logging
from RaspPiReader import pool
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import DatabaseSettings

logger = logging.getLogger(__name__)

class SyncThread(threading.Thread):
    def __init__(self, interval=60):
        super().__init__()
        self.interval = interval
        self.daemon = True  # Set as daemon so it exits when main thread exits
        self.local_db = Database("sqlite:///local_database.db")
        
        # Initialize azure_db_url based on database settings
        self.azure_db_url = None
        self._load_db_settings()
        
        logger.info(f"Sync thread initialized with interval: {interval} seconds")
    
    def _load_db_settings(self):
        """Load database settings and create Azure DB URL"""
        try:
            db_settings = self.local_db.session.query(DatabaseSettings).first()
            if db_settings:
                logger.info("Database settings found for Azure sync")
                # Ensure all required fields are present
                if (db_settings.db_username and db_settings.db_password and
                        db_settings.db_server and db_settings.db_name):
                    self.azure_db_url = (
                        f"mssql+pyodbc://{db_settings.db_username}:{db_settings.db_password}@"
                        f"{db_settings.db_server}/{db_settings.db_name}?"
                        f"driver=ODBC+Driver+17+for+SQL+Server"
                    )
                    logger.info(f"Azure DB URL created for server: {db_settings.db_server}")
                else:
                    logger.warning("Incomplete database settings, Azure sync disabled")
                    self.azure_db_url = None
            else:
                logger.warning("No database settings found, Azure sync disabled")
                self.azure_db_url = None
        except Exception as e:
            logger.error(f"Error loading database settings: {e}")
            self.azure_db_url = None
    def run(self):
        """Main thread loop that synchronizes data to Azure"""
        logger.info("Sync thread started")
        while True:
            try:
                if self.azure_db_url:
                    logger.info("Attempting to sync data to Azure...")
                    self.local_db.sync_to_azure(self.azure_db_url)
                    logger.info("Sync to Azure completed successfully")
                else:
                    logger.warning("Azure DB URL not configured, sync skipped")
                    # Try to load settings again in case they were added after thread started
                    self._load_db_settings()
            except Exception as e:
                logger.error(f"Sync to Azure failed: {e}")
            
            # Wait for next sync interval
            time.sleep(self.interval)