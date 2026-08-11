import hashlib
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, text
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker
import models

# 1. Connect to MySQL server without database first to ensure the database exists
BASE_URL = "mysql+pymysql://root:12345@localhost:3308/"
DATABASE_NAME = "cricket_db"

print("Connecting to MySQL server at localhost...")
try:
    temp_engine = create_engine(BASE_URL)
    with temp_engine.connect() as conn:
        # Commit to avoid transaction block errors when creating database
        conn.execute(text("commit"))
        # Check if database exists
        databases = conn.execute(text("SHOW DATABASES")).fetchall()
        db_exists = any(db[0] == DATABASE_NAME for db in databases)
        
        if not db_exists:
            print(f"Database '{DATABASE_NAME}' not found. Creating database...")
            conn.execute(text(f"CREATE DATABASE {DATABASE_NAME}"))
            print(f"Database '{DATABASE_NAME}' created successfully!")
        else:
            print(f"Database '{DATABASE_NAME}' already exists.")
    temp_engine.dispose()
except Exception as e:
    print(f"Error connecting to MySQL or creating database: {e}")
    print("Please make sure MySQL is running on localhost (default root with no password).")
    exit(1)

# 2. Connect to the cricket_db database and create tables
DATABASE_URL = f"mysql+pymysql://root:12345@localhost:3308/{DATABASE_NAME}"
engine = create_engine(DATABASE_URL)

try:
    print("Creating tables defined in models.py...")
    models.Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
except Exception as e:
    print(f"Error creating tables: {e}")
    exit(1)

# 3. Seed default admin user
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    admin_exists = db.query(models.Admin).filter(models.Admin.username == 'admin').first()
    if not admin_exists:
        print("Creating default admin account...")
        # main.py uses sha256 to hash passwords: hashlib.sha256(password.encode()).hexdigest()
        hashed_password = hashlib.sha256("admin123".encode()).hexdigest()
        default_admin = models.Admin(username="admin", password=hashed_password)
        db.add(default_admin)
        db.commit()
        print("Default admin created successfully!")
        print("Credentials -> Username: admin | Password: admin123")
    else:
        print("Admin account already exists.")
except Exception as e:
    print(f"Error seeding default admin: {e}")
    db.rollback()
finally:
    db.close()
    engine.dispose()

print("Database initialization complete!")
