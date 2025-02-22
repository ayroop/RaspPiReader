from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from RaspPiReader.libs.models import Base, User, PLCCommSettings, DatabaseSettings, OneDriveSettings, GeneralConfigSettings, ChannelConfigSettings, CycleData, DemoData, BooleanStatus, PlotData, Product, DefaultProgram

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
            azure_user = azure_session.query(User).filter_by(username=user.username).first()
            if not azure_user:
                azure_user = User(
                    username=user.username,
                    password=user.password,
                    settings=user.settings,
                    search=user.search,
                    user_mgmt_page=user.user_mgmt_page
                )
                azure_session.add(azure_user)
            else:
                azure_user.password = user.password
                azure_user.settings = user.settings
                azure_user.search = user.search
                azure_user.user_mgmt_page = user.user_mgmt_page

        # Sync PLC communication settings
        plc_settings = self.session.query(PLCCommSettings).first()
        if plc_settings:
            azure_plc_settings = azure_session.query(PLCCommSettings).first()
            if not azure_plc_settings:
                azure_plc_settings = PLCCommSettings(
                    comm_mode=plc_settings.comm_mode,
                    tcp_host=plc_settings.tcp_host,
                    tcp_port=plc_settings.tcp_port,
                    com_port=plc_settings.com_port
                )
                azure_session.add(azure_plc_settings)
            else:
                azure_plc_settings.comm_mode = plc_settings.comm_mode
                azure_plc_settings.tcp_host = plc_settings.tcp_host
                azure_plc_settings.tcp_port = plc_settings.tcp_port
                azure_plc_settings.com_port = plc_settings.com_port

        # Sync database settings
        db_settings = self.session.query(DatabaseSettings).first()
        if db_settings:
            azure_db_settings = azure_session.query(DatabaseSettings).first()
            if not azure_db_settings:
                azure_db_settings = DatabaseSettings(
                    db_username=db_settings.db_username,
                    db_password=db_settings.db_password,
                    db_server=db_settings.db_server,
                    db_name=db_settings.db_name
                )
                azure_session.add(azure_db_settings)
            else:
                azure_db_settings.db_username = db_settings.db_username
                azure_db_settings.db_password = db_settings.db_password
                azure_db_settings.db_server = db_settings.db_server
                azure_db_settings.db_name = db_settings.db_name

        # Sync OneDrive settings
        onedrive_settings = self.session.query(OneDriveSettings).first()
        if onedrive_settings:
            azure_onedrive_settings = azure_session.query(OneDriveSettings).first()
            if not azure_onedrive_settings:
                azure_onedrive_settings = OneDriveSettings(
                    client_id=onedrive_settings.client_id,
                    client_secret=onedrive_settings.client_secret,
                    tenant_id=onedrive_settings.tenant_id,
                    update_interval=onedrive_settings.update_interval
                )
                azure_session.add(azure_onedrive_settings)
            else:
                azure_onedrive_settings.client_id = onedrive_settings.client_id
                azure_onedrive_settings.client_secret = onedrive_settings.client_secret
                azure_onedrive_settings.tenant_id = onedrive_settings.tenant_id
                azure_onedrive_settings.update_interval = onedrive_settings.update_interval

        # Sync general config settings
        general_config_settings = self.session.query(GeneralConfigSettings).first()
        if general_config_settings:
            azure_general_config_settings = azure_session.query(GeneralConfigSettings).first()
            if not azure_general_config_settings:
                azure_general_config_settings = GeneralConfigSettings(
                    # Add all fields from GeneralConfigSettings
                )
                azure_session.add(azure_general_config_settings)
            else:
                # Update all fields in GeneralConfigSettings
                pass

        # Sync channel config settings
        channel_config_settings = self.session.query(ChannelConfigSettings).all()
        for channel_config in channel_config_settings:
            azure_channel_config = azure_session.query(ChannelConfigSettings).filter_by(id=channel_config.id).first()
            if not azure_channel_config:
                azure_channel_config = ChannelConfigSettings(
                    # Add all fields from ChannelConfigSettings
                )
                azure_session.add(azure_channel_config)
            else:
                # Update all fields in ChannelConfigSettings
                pass

        # Sync cycle data
        cycle_data = self.get_cycle_data()
        for cycle in cycle_data:
            azure_cycle = azure_session.query(CycleData).filter_by(id=cycle.id).first()
            if not azure_cycle:
                azure_cycle = CycleData(
                    # Add all fields from CycleData
                )
                azure_session.add(azure_cycle)
            else:
                # Update all fields in CycleData
                pass

        # Sync demo data
        demo_data = self.session.query(DemoData).all()
        for demo in demo_data:
            azure_demo = azure_session.query(DemoData).filter_by(id=demo.id).first()
            if not azure_demo:
                azure_demo = DemoData(
                    # Add all fields from DemoData
                )
                azure_session.add(azure_demo)
            else:
                # Update all fields in DemoData
                pass

        # Sync boolean status
        boolean_status = self.session.query(BooleanStatus).all()
        for status in boolean_status:
            azure_status = azure_session.query(BooleanStatus).filter_by(id=status.id).first()
            if not azure_status:
                azure_status = BooleanStatus(
                    # Add all fields from BooleanStatus
                )
                azure_session.add(azure_status)
            else:
                # Update all fields in BooleanStatus
                pass

        # Sync plot data
        plot_data = self.session.query(PlotData).all()
        for plot in plot_data:
            azure_plot = azure_session.query(PlotData).filter_by(id=plot.id).first()
            if not azure_plot:
                azure_plot = PlotData(
                    # Add all fields from PlotData
                )
                azure_session.add(azure_plot)
            else:
                # Update all fields in PlotData
                pass

        # Sync products
        products = self.session.query(Product).all()
        for product in products:
            azure_product = azure_session.query(Product).filter_by(id=product.id).first()
            if not azure_product:
                azure_product = Product(
                    # Add all fields from Product
                )
                azure_session.add(azure_product)
            else:
                # Update all fields in Product
                pass

        # Sync default programs
        default_programs = self.session.query(DefaultProgram).all()
        for program in default_programs:
            azure_program = azure_session.query(DefaultProgram).filter_by(id=program.id).first()
            if not azure_program:
                azure_program = DefaultProgram(
                    # Add all fields from DefaultProgram
                )
                azure_session.add(azure_program)
            else:
                # Update all fields in DefaultProgram
                pass

        azure_session.commit()