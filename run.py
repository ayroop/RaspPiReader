from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui.login_form_handler import LoginFormHandler
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.sync import SyncThread

def Main():
    app = QtWidgets.QApplication(sys.argv)
    demo_mode = pool.config('demo', bool, False)

    if demo_mode:
        pool.set('demo', True)
    else:
        # Ensure local SQLite database is initialized
        local_db = Database("sqlite:///local_database.db")
        local_db.create_tables()

        # Start the sync thread
        sync_thread = SyncThread(interval=60)  # Sync every 60 seconds
        sync_thread.start()

    login_form = LoginFormHandler()
    login_form.show()
    app.exec_()

if __name__ == "__main__":
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', type=bool, default=False)
    parser.add_argument('--demo', type=bool, default=False)
    args = parser.parse_args()
    pool.set('debug', args.debug)
    pool.set('demo', args.demo)
    Main()