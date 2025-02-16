from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import User

def add_admin_user():
    db = Database("sqlite:///local_database.db")
    admin_user = db.get_user("admin")
    if not admin_user:
        admin_user = User(username="admin", password="admin", settings=True, search=True, user_mgmt_page=True)
        db.add_user(admin_user)
        print("Admin user added.")
    else:
        print("Admin user already exists.")

if __name__ == "__main__":
    add_admin_user()