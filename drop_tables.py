from sqlalchemy import create_engine
from RaspPiReader.libs.models import Base

def drop_tables(database_url):
    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    print("Tables dropped successfully.")

if __name__ == "__main__":
    drop_tables("sqlite:///local_database.db")