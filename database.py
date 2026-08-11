from sqlalchemy import create_engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker

# Database configuration corresponding to includes/db_connect.php
DATABASE_URL = "mysql+pymysql://root:12345@localhost:3308/cricket_db"

engine = create_engine(
    DATABASE_URL, 
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
