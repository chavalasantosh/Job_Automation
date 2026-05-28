import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class AgentStatus(Base):
    __tablename__ = 'agents'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    status = Column(String, default="OFFLINE") # OFFLINE, STARTING, ACTIVE, CRASHED, SLEEPING
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    current_job_id = Column(String, nullable=True)
    uptime_seconds = Column(Integer, default=0)
    config = Column(JSON, nullable=True) # Per-agent configuration

class JobApplication(Base):
    __tablename__ = 'job_applications'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String, nullable=False)
    portal = Column(String, nullable=False)
    title = Column(String)
    company = Column(String)
    status = Column(String) # APPLIED, FAILED, SKIPPED, PENDING
    applied_at = Column(DateTime, default=datetime.datetime.utcnow)
    details = Column(JSON) # Extra info like answers given, logs specific to this job
    error_message = Column(Text, nullable=True)

class LogEntry(Base):
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    agent_name = Column(String, nullable=False)
    level = Column(String, nullable=False) # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    module = Column(String)

# Database Engine Setup
DATABASE_URL = "sqlite:///./nowcurry_enterprise.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database Initialized Architecturally.")
