from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from RaspPiReader.libs.models import Base, User, PLCCommSettings, DatabaseSettings, OneDriveSettings, GeneralConfigSettings, ChannelConfigSettings, CycleData, DemoData, BooleanStatus, PlotData

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

    def add_cycle_data(self, cycle_data):
        self.session.add(cycle_data)
        self.session.commit()

    def get_cycle_data(self):
        return self.session.query(CycleData).all()

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

        # Sync channel configuration settings
        channel_config_settings = self.session.query(ChannelConfigSettings).all()
        for channel_config in channel_config_settings:
            azure_session.merge(channel_config)

        # Sync cycle data
        cycle_data = self.get_cycle_data()
        for cycle in cycle_data:
            azure_session.merge(cycle)

        azure_session.commit()

        # Sync demo data
        demo_data = self.session.query(DemoData).all()
        for record in demo_data:
            azure_session.merge(record)
        
        azure_session.commit()

        # Sync boolean status
        boolean_statuses = self.session.query(BooleanStatus).all()
        for status in boolean_statuses:
            azure_session.merge(status)

        # Sync plot data
        plot_data = self.session.query(PlotData).all()
        for data in plot_data:
            azure_session.merge(data)

        azure_session.commit()