from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from RaspPiReader.libs.models import Base, User

class Database:
    def __init__(self, database_url):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def add_user(self, user):
        self.session.add(user)
        self.session.commit()

    def get_user(self, username):
        return self.session.query(User).filter_by(username=username).first()

    def get_users(self):
        return self.session.query(User).all()

    def sync_to_azure(self, azure_db_url):
        azure_engine = create_engine(azure_db_url)
        AzureSession = sessionmaker(bind=azure_engine)
        azure_session = AzureSession()
        users = self.get_users()
        for user in users:
            azure_session.merge(user)
        azure_session.commit()