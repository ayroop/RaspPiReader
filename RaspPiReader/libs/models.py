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

# Add other models as needed