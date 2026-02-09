#databaseملف
from sqlmodel import SQLModel, create_engine, Session
from models import Parking_Reservations

sqlite_file_name = "parking.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
