import argparse
import sys

from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui.login_form_handler import LoginFormHandler
from RaspPiReader.ui.database_settings_form_handler import DatabaseSettingsFormHandler
from RaspPiReader.libs.database import Database

def Main():
    app = QtWidgets.QApplication(sys.argv)
    demo_mode = pool.config('demo', bool, False)

    if demo_mode:
        # Set demo mode flag in pool
        pool.set('demo', True)
    else:
        db_username = pool.config('db_username', str, '')
        db_password = pool.config('db_password', str, '')
        db_server = pool.config('db_server', str, '')
        db_name = pool.config('db_name', str, '')
        database_url = f"mssql+pyodbc://{db_username}:{db_password}@{db_server}/{db_name}?driver=ODBC+Driver+17+for+SQL+Server"
        
        try:
            db = Database(database_url)
            db.create_tables()
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Database Connection Error", str(e))
            dlg = DatabaseSettingsFormHandler()
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                db_username = pool.config('db_username', str, '')
                db_password = pool.config('db_password', str, '')
                db_server = pool.config('db_server', str, '')
                db_name = pool.config('db_name', str, '')
                database_url = f"mssql+pyodbc://{db_username}:{db_password}@{db_server}/{db_name}?driver=ODBC+Driver+17+for+SQL+Server"
                db = Database(database_url)
                db.create_tables()
            else:
                sys.exit(1)

    login_form = LoginFormHandler()
    login_form.show()
    app.exec_()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', type=bool, default=False)
    parser.add_argument('--demo', type=bool, default=False)
    args = parser.parse_args()
    pool.set('debug', args.debug)
    pool.set('demo', args.demo)
    Main()