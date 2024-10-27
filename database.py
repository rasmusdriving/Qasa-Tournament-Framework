from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import time

def get_db_engine(retries=3, delay=1):
    for attempt in range(retries):
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,  # Add connection health check
                pool_recycle=3600,   # Recycle connections after 1 hour
                connect_args={
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5
                }
            )
            return engine
        except OperationalError as e:
            if attempt == retries - 1:
                raise e
            time.sleep(delay)

engine = get_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
