from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from RaspPiReader.libs.models import Base, User, PLCCommSettings, DatabaseSettings, OneDriveSettings, GeneralConfigSettings

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

        # Sync users
        users = self.get_users()
        for user in users:
            azure_session.merge(user)

        # Sync PLC communication settings
        plc_settings = self.session.query(PLCCommSettings).first()
        if plc_settings:
            azure_session.merge(plc_settings)

        # Sync database settings
        db_settings = self.session.query(DatabaseSettings).first()
        if db_settings:
            azure_session.merge(db_settings)

        # Sync OneDrive settings
        onedrive_settings = self.session.query(OneDriveSettings).first()
        if onedrive_settings:
            azure_session.merge(onedrive_settings)

        # Sync general configuration settings
        general_config_settings = self.session.query(GeneralConfigSettings).first()
        if general_config_settings:
            azure_session.merge(general_config_settings)

        azure_session.commit()