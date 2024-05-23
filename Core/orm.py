from sqlalchemy import create_engine, Column, String, Integer, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "---"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class OnlineUser(Base):
    __tablename__ = "online_list"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(255), unique=True, index=True, nullable=False, comment='UUID')
    identities = Column(String(255), nullable=False, comment='身份')

class Session(Base):
    __tablename__ = "session_list"

    service_uuid = Column(String(255), primary_key=True, index=True, nullable=False, comment='控制端UUID')
    client_uuid = Column(String(255), primary_key=True, index=True, nullable=False, comment='客户UUID')

Base.metadata.create_all(bind=engine)
