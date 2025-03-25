import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import User

# Determine the project root (folder next to run.py) and construct the database URL
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
db_path = os.path.join(project_root, "local_database.db")
db_url = f"sqlite:///{db_path}"

def add_admin_user():
    # Initialize database and create tables if they don't exist
    db = Database(db_url)
    db.create_tables()

    admin_user = db.get_user("admin")
    if not admin_user:
        admin_user = User(username="admin", password="admin", settings=True, search=True, user_mgmt_page=True)
        db.add_user(admin_user)
        print("Admin user added.")
    else:
        print("Admin user already exists.")

if __name__ == "__main__":
    add_admin_user()