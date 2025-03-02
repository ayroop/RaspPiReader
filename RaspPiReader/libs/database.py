from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from RaspPiReader.libs.models import (
    Base, User, PLCCommSettings, DatabaseSettings, OneDriveSettings,
    GeneralConfigSettings, ChannelConfigSettings, CycleData, DemoData,
    BooleanStatus, PlotData, DefaultProgram, Alarm
)

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
        try:
            self.session.add(cycle_data)
            self.session.commit()
            return True
        except RecursionError:
            self.session.rollback()
            logging.error("RecursionError in database operation - check model definitions")
            return False
        except Exception as e:
            self.session.rollback()
            logging.error(f"Error adding cycle data: {e}")
            return False

    def get_cycle_data(self):
        return self.session.query(CycleData).all()

    def search_serial_number(self, sn):
        """
        Search for a serial number in the database.
        Returns the cycle data record containing the serial number if found, None otherwise.
        """
        try:
            cycles = self.session.query(CycleData).all()
            for cycle in cycles:
                if cycle.serial_numbers and sn in cycle.serial_numbers.split(','):
                    return cycle
        except Exception as e:
            logger.error(f"Error searching for serial number: {e}")
        return None

    def check_duplicate_serial(self, sn):
        """
        Check if the provided serial number 'sn' already exists
        in any CycleData record.
        """
        try:
            cycles = self.session.query(CycleData).all()
            for cycle in cycles:
                if cycle.serial_numbers and sn in cycle.serial_numbers.split(','):
                    return True
        except Exception as e:
            logger.error(f"Error checking for duplicate serial: {e}")
        return False

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
        azure_session.commit()

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
        azure_session.commit()

        # Sync DatabaseSettings
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
        azure_session.commit()

        # Sync OneDriveSettings
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
        azure_session.commit()

        # Sync GeneralConfigSettings
        general_config_settings = self.session.query(GeneralConfigSettings).first()
        if general_config_settings:
            azure_general_config_settings = azure_session.query(GeneralConfigSettings).first()
            if not azure_general_config_settings:
                azure_general_config_settings = GeneralConfigSettings(
                    key=general_config_settings.key,
                    value=general_config_settings.value
                )
                azure_session.add(azure_general_config_settings)
            else:
                azure_general_config_settings.key = general_config_settings.key
                azure_general_config_settings.value = general_config_settings.value
        azure_session.commit()

        # Sync ChannelConfigSettings
        channel_config_settings = self.session.query(ChannelConfigSettings).all()
        for channel_config in channel_config_settings:
            azure_channel_config = azure_session.query(ChannelConfigSettings).filter_by(id=channel_config.id).first()
            if not azure_channel_config:
                azure_channel_config = ChannelConfigSettings(
                    id=channel_config.id,
                    name=channel_config.name,
                    address=channel_config.address,
                    pv=channel_config.pv,
                    sv=channel_config.sv,
                    set_point=channel_config.set_point,
                    low_limit=channel_config.low_limit,
                    high_limit=channel_config.high_limit,
                    dec_point=channel_config.dec_point,
                    scale=channel_config.scale
                )
                azure_session.add(azure_channel_config)
            else:
                azure_channel_config.name = channel_config.name
                azure_channel_config.address = channel_config.address
                azure_channel_config.pv = channel_config.pv
                azure_channel_config.sv = channel_config.sv
                azure_channel_config.set_point = channel_config.set_point
                azure_channel_config.low_limit = channel_config.low_limit
                azure_channel_config.high_limit = channel_config.high_limit
                azure_channel_config.dec_point = channel_config.dec_point
                azure_channel_config.scale = channel_config.scale
        azure_session.commit()

        # Sync CycleData
        cycle_data = self.session.query(CycleData).all()
        for cycle in cycle_data:
            azure_cycle = azure_session.query(CycleData).filter_by(id=cycle.id).first()
            if not azure_cycle:
                azure_cycle = CycleData(
                    id=cycle.id,
                    order_id=cycle.order_id,
                    cycle_id=cycle.cycle_id,
                    quantity=cycle.quantity,
                    size=cycle.size,
                    cycle_location=cycle.cycle_location,
                    dwell_time=cycle.dwell_time,
                    cool_down_temp=cycle.cool_down_temp,
                    core_temp_setpoint=cycle.core_temp_setpoint,
                    temp_ramp=cycle.temp_ramp,
                    set_pressure=cycle.set_pressure,
                    maintain_vacuum=cycle.maintain_vacuum,
                    initial_set_cure_temp=cycle.initial_set_cure_temp,
                    final_set_cure_temp=cycle.final_set_cure_temp,
                    created_at=cycle.created_at
                )
                azure_session.add(azure_cycle)
            else:
                azure_cycle.order_id = cycle.order_id
                azure_cycle.cycle_id = cycle.cycle_id
                azure_cycle.quantity = cycle.quantity
                azure_cycle.size = cycle.size
                azure_cycle.cycle_location = cycle.cycle_location
                azure_cycle.dwell_time = cycle.dwell_time
                azure_cycle.cool_down_temp = cycle.cool_down_temp
                azure_cycle.core_temp_setpoint = cycle.core_temp_setpoint
                azure_cycle.temp_ramp = cycle.temp_ramp
                azure_cycle.set_pressure = cycle.set_pressure
                azure_cycle.maintain_vacuum = cycle.maintain_vacuum
                azure_cycle.initial_set_cure_temp = cycle.initial_set_cure_temp
                azure_cycle.final_set_cure_temp = cycle.final_set_cure_temp
                azure_cycle.created_at = cycle.created_at
        azure_session.commit()

        # Sync DemoData
        demo_data = self.session.query(DemoData).all()
        for demo in demo_data:
            azure_demo = azure_session.query(DemoData).filter_by(id=demo.id).first()
            if not azure_demo:
                azure_demo = DemoData(
                    id=demo.id,
                    column1=demo.column1,
                    column2=demo.column2,
                    column3=demo.column3,
                    column4=demo.column4,
                    column5=demo.column5,
                    column6=demo.column6,
                    column7=demo.column7,
                    column8=demo.column8,
                    column9=demo.column9,
                    column10=demo.column10,
                    column11=demo.column11,
                    column12=demo.column12,
                    column13=demo.column13,
                    column14=demo.column14
                )
                azure_session.add(azure_demo)
            else:
                azure_demo.column1 = demo.column1
                azure_demo.column2 = demo.column2
                azure_demo.column3 = demo.column3
                azure_demo.column4 = demo.column4
                azure_demo.column5 = demo.column5
                azure_demo.column6 = demo.column6
                azure_demo.column7 = demo.column7
                azure_demo.column8 = demo.column8
                azure_demo.column9 = demo.column9
                azure_demo.column10 = demo.column10
                azure_demo.column11 = demo.column11
                azure_demo.column12 = demo.column12
                azure_demo.column13 = demo.column13
                azure_demo.column14 = demo.column14
        azure_session.commit()

        # Sync BooleanStatus
        boolean_status = self.session.query(BooleanStatus).all()
        for status in boolean_status:
            azure_status = azure_session.query(BooleanStatus).filter_by(id=status.id).first()
            if not azure_status:
                azure_status = BooleanStatus(
                    id=status.id,
                    address=status.address,
                    value=status.value
                )
                azure_session.add(azure_status)
            else:
                azure_status.address = status.address
                azure_status.value = status.value
        azure_session.commit()

        # Sync PlotData
        plot_data = self.session.query(PlotData).all()
        for plot in plot_data:
            azure_plot = azure_session.query(PlotData).filter_by(id=plot.id).first()
            if not azure_plot:
                azure_plot = PlotData(
                    id=plot.id,
                    timestamp=plot.timestamp,
                    value=plot.value
                )
                azure_session.add(azure_plot)
            else:
                azure_plot.timestamp = plot.timestamp
                azure_plot.value = plot.value
        azure_session.commit()

        # Sync DefaultProgram
        default_programs = self.session.query(DefaultProgram).all()
        for program in default_programs:
            azure_program = azure_session.query(DefaultProgram).filter_by(id=program.id).first()
            if not azure_program:
                azure_program = DefaultProgram(
                    id=program.id,
                    username=program.username,
                    program_number=program.program_number,
                    order_number=program.order_number,
                    cycle_id=program.cycle_id,
                    quantity=program.quantity,
                    size=program.size,
                    cycle_location=program.cycle_location,
                    dwell_time=program.dwell_time,
                    cool_down_temp=program.cool_down_temp,
                    core_temp_setpoint=program.core_temp_setpoint,
                    temp_ramp=program.temp_ramp,
                    set_pressure=program.set_pressure,
                    maintain_vacuum=program.maintain_vacuum,
                    initial_set_cure_temp=program.initial_set_cure_temp,
                    final_set_cure_temp=program.final_set_cure_temp
                )
                azure_session.add(azure_program)
            else:
                azure_program.username = program.username
                azure_program.program_number = program.program_number
                azure_program.order_number = program.order_number
                azure_program.cycle_id = program.cycle_id
                azure_program.quantity = program.quantity
                azure_program.size = program.size
                azure_program.cycle_location = program.cycle_location
                azure_program.dwell_time = program.dwell_time
                azure_program.cool_down_temp = program.cool_down_temp
                azure_program.core_temp_setpoint = program.core_temp_setpoint
                azure_program.temp_ramp = program.temp_ramp
                azure_program.set_pressure = program.set_pressure
                azure_program.maintain_vacuum = program.maintain_vacuum
                azure_program.initial_set_cure_temp = program.initial_set_cure_temp
                azure_program.final_set_cure_temp = program.final_set_cure_temp
        azure_session.commit()

        # Sync Alarm
        alarms = self.session.query(Alarm).all()
        for alarm in alarms:
            azure_alarm = azure_session.query(Alarm).filter_by(id=alarm.id).first()
            if not azure_alarm:
                azure_alarm = Alarm(
                    id=alarm.id,
                    address=alarm.address,
                    alarm_text=alarm.alarm_text
                )
                azure_session.add(azure_alarm)
            else:
                azure_alarm.address = alarm.address
                azure_alarm.alarm_text = alarm.alarm_text
        azure_session.commit()