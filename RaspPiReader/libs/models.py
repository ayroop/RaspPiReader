from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    settings = Column(Boolean, default=False)
    search = Column(Boolean, default=False)
    user_mgmt_page = Column(Boolean, default=False)

class PLCCommSettings(Base):
    __tablename__ = 'plc_comm_settings'
    id = Column(Integer, primary_key=True)
    comm_mode = Column(String, nullable=False)
    tcp_host = Column(String, nullable=False)
    tcp_port = Column(Integer, nullable=False)
    com_port = Column(String, nullable=False)

class DatabaseSettings(Base):
    __tablename__ = 'database_settings'
    id = Column(Integer, primary_key=True)
    db_username = Column(String, nullable=False)
    db_password = Column(String, nullable=False)
    db_server = Column(String, nullable=False)
    db_name = Column(String, nullable=False)