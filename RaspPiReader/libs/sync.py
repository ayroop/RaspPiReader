import threading
import time
from RaspPiReader.libs.database import Database
from RaspPiReader import pool

class SyncThread(threading.Thread):
    def __init__(self, interval=60):
        super().__init__()
        self.interval = interval
        self.local_db = Database("sqlite:///local_database.db")
        self.azure_db_url = f"mssql+pyodbc://{pool.config('db_username')}:{pool.config('db_password')}@{pool.config('db_server')}/{pool.config('db_name')}?driver=ODBC+Driver+17+for+SQL+Server"

    def run(self):
        while True:
            try:
                self.local_db.sync_to_azure(self.azure_db_url)
            except Exception as e:
                print(f"Sync to Azure failed: {e}")
            time.sleep(self.interval)

# Start the sync thread
sync_thread = SyncThread(interval=60)  # Sync every 60 seconds
sync_thread.start()