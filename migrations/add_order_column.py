from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL").replace('postgres://', 'postgresql://')

def run_migration():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        # Add order column
        connection.execute(text("""
            ALTER TABLE matches 
            ADD COLUMN "order" INTEGER NOT NULL DEFAULT 0;
        """))
        
        # Initialize order based on position for existing matches
        connection.execute(text("""
            UPDATE matches 
            SET "order" = position 
            WHERE position IS NOT NULL;
        """))
        
        connection.commit()

if __name__ == "__main__":
    run_migration()
