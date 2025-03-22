import sys, os
# Add the project root folder to sys.path (adjust the relative path as needed)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from RaspPiReader.libs.models import Base
from sqlalchemy import create_engine

def drop_tables(database_url):
    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    print("Tables dropped successfully.")

if __name__ == "__main__":
    drop_tables("sqlite:///local_database.db")