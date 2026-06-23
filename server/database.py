from sqlmodel import create_engine, SQLModel, Session
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
# Ensure data directory exists
os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)

db_path = os.path.join(base_dir, "data", "chat.db")
sqlite_url = f"sqlite:///{db_path}"

engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
