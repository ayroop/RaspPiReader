from RaspPiReader.libs.database import Database

def create_tables():
    db = Database("sqlite:///local_database.db")
    db.create_tables()
    print("Tables created successfully.")

if __name__ == "__main__":
    create_tables()