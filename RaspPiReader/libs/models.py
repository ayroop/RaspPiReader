from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    settings = Column(Boolean, default=False)
    search = Column(Boolean, default=False)
    user_mgmt_page = Column(Boolean, default=False)
    role = Column(String, default="Operator")

class PLCCommSettings(Base):
    __tablename__ = 'plc_comm_settings'
    id = Column(Integer, primary_key=True)
    comm_mode = Column(String, nullable=False)
    tcp_host = Column(String, nullable=True)
    tcp_port = Column(Integer, nullable=True)
    com_port = Column(String, nullable=True)  # Using com_port instead of rtu_port
    baudrate = Column(Integer, nullable=True)
    bytesize = Column(Integer, nullable=True)
    parity = Column(String, nullable=True)
    stopbits = Column(Float, nullable=True)
    timeout = Column(Float, nullable=True)

class DatabaseSettings(Base):
    __tablename__ = 'database_settings'
    id = Column(Integer, primary_key=True)
    db_username = Column(String, nullable=False)
    db_password = Column(String, nullable=False)
    db_server = Column(String, nullable=False)
    db_name = Column(String, nullable=False)

class OneDriveSettings(Base):
    __tablename__ = 'onedrive_settings'
    id = Column(Integer, primary_key=True)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False)
    update_interval = Column(Integer, nullable=False)

class GeneralConfigSettings(Base):
    __tablename__ = 'general_config_settings'
    id = Column(Integer, primary_key=True)
    baudrate = Column(Integer, nullable=False)
    parity = Column(String, nullable=False)
    databits = Column(Integer, nullable=False)
    stopbits = Column(Float, nullable=False)
    reading_address = Column(String, nullable=False)
    register_read_type = Column(String, nullable=False)
    port = Column(String, nullable=False)
    left_v_label = Column(String, nullable=False)
    right_v_label = Column(String, nullable=False)
    h_label = Column(String, nullable=False)
    time_interval = Column(Float, nullable=False)
    panel_time_interval = Column(Float, nullable=False)
    accuarate_data_time = Column(Float, nullable=False)
    signin_status = Column(Boolean, nullable=False)
    signin_email = Column(String, nullable=False)
    csv_file_path = Column(String, nullable=False)
    csv_delimiter = Column(String, nullable=False)
    gdrive_update_interval = Column(Integer, nullable=False)
    core_temp_channel = Column(Integer, nullable=False)
    pressure_channel = Column(Integer, nullable=False)
    scale_range = Column(Integer, nullable=False, default=1000)

class ChannelConfigSettings(Base):
    __tablename__ = 'channel_config_settings'
    id = Column(Integer, primary_key=True)
    address = Column(Integer, nullable=False)
    label = Column(String, nullable=False)
    pv = Column(Integer, nullable=False)
    sv = Column(Integer, nullable=False)
    sp = Column(Integer, nullable=False)
    limit_low = Column(Integer, nullable=False)
    limit_high = Column(Integer, nullable=False)
    decimal_point = Column(Integer, nullable=False)
    scale = Column(Boolean, nullable=False)
    axis_direction = Column(String, nullable=False)
    color = Column(String, nullable=False)
    active = Column(Boolean, nullable=False)
    min_scale_range = Column(Integer, nullable=False)
    max_scale_range = Column(Integer, nullable=False)

class CycleData(Base):
    __tablename__ = 'cycle_data'
    id = Column(Integer, primary_key=True)
    order_id = Column(String, nullable=False)
    cycle_id = Column(String, nullable=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    stop_time = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", backref="cycle_data")
    quantity = Column(Integer, nullable=True)
    status = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    core_temp_setpoint = Column(Float, nullable=True)
    cool_down_temp = Column(Float, nullable=True)
    dwell_time = Column(String, nullable=True)
    set_pressure = Column(Float, nullable=True)
    maintain_vacuum = Column(Boolean, nullable=True)
    initial_set_cure_temp = Column(Float, nullable=True)
    final_set_cure_temp = Column(Float, nullable=True)
    pdf_report_path = Column(String, nullable=True)
    html_report_path = Column(String, nullable=True)

class CycleSerialNumber(Base):
    __tablename__ = 'cycle_serial_numbers'
    id = Column(Integer, primary_key=True)
    cycle_id = Column(Integer, ForeignKey('cycle_data.id'), nullable=False)
    serial_number = Column(String, nullable=False)
    cycle = relationship("CycleData", backref="serials")

class DemoData(Base):
    __tablename__ = 'demo_data'
    id = Column(Integer, primary_key=True)
    column1 = Column(String, nullable=False)
    column2 = Column(String, nullable=False)
    column3 = Column(String, nullable=False)
    column4 = Column(String, nullable=False)
    column5 = Column(String, nullable=False)
    column6 = Column(String, nullable=False)
    column7 = Column(String, nullable=False)
    column8 = Column(String, nullable=False)
    column9 = Column(String, nullable=False)
    column10 = Column(String, nullable=False)
    column11 = Column(String, nullable=False)
    column12 = Column(String, nullable=False)
    column13 = Column(String, nullable=False)
    column14 = Column(String, nullable=False)

class BooleanStatus(Base):
    __tablename__ = 'boolean_status'
    id = Column(Integer, primary_key=True)
    address = Column(Integer, nullable=False)
    status = Column(Boolean, nullable=False)

class PlotData(Base):
    __tablename__ = 'plot_data'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    channel = Column(String, nullable=False)
    value = Column(Float, nullable=False)
class DefaultProgram(Base):
    __tablename__ = 'default_programs'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, index=True)
    program_number = Column(Integer, nullable=False)  # Values: 1,2,3,4
    order_number = Column(String, nullable=False)
    cycle_id = Column(String, nullable=False)
    quantity = Column(String, nullable=False)
    size = Column(String, nullable=False)
    cycle_location = Column(String, nullable=False)
    dwell_time = Column(String, nullable=False)
    cool_down_temp = Column(String, nullable=False)
    core_temp_setpoint = Column(String, nullable=False)
    temp_ramp = Column(String, nullable=False)
    set_pressure = Column(String, nullable=False)
    maintain_vacuum = Column(String, nullable=False)
    initial_set_cure_temp = Column(String, nullable=False)
    final_set_cure_temp = Column(String, nullable=False)

class Alarm(Base):
    __tablename__ = 'alarms'
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False, unique=True)  # e.g. "100"
    alarm_text = Column(String, nullable=False)

class BooleanAddress(Base):
    __tablename__ = 'boolean_addresses'
    id = Column(Integer, primary_key=True)
    address = Column(Integer, nullable=False)
    label = Column(String, nullable=False)