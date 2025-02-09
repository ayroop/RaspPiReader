from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from RaspPiReader.libs.models import Base

class Database:
    def __init__(self, database_url):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def create_tables(self):
        Base.metadata.create_all(self.engine)

# Example usage:
# db = Database("mssql+pyodbc://<username>:<password>@<server_name>/<database_name>?driver=ODBC+Driver+17+for+SQL+Server")
# db.create_tables()