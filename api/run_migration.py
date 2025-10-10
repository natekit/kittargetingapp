"""
Run database migration to add smart matching enhancements.
This script will add the missing columns and tables.
"""

import os
import sys
from sqlalchemy import text
from app.db import get_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run the database migration manually."""
    logger.info("Starting database migration...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Check if columns already exist
        logger.info("Checking existing columns...")
        
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'creators' 
            AND column_name IN ('age_range', 'gender_skew', 'location', 'interests')
        """)).fetchall()
        
        existing_columns = [row[0] for row in result]
        logger.info(f"Existing demographic columns: {existing_columns}")
        
        # Add missing columns to creators table
        columns_to_add = [
            ('age_range', 'VARCHAR(10)'),
            ('gender_skew', 'VARCHAR(20)'),
            ('location', 'VARCHAR(10)'),
            ('interests', 'TEXT')
        ]
        
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                logger.info(f"Adding column: {column_name}")
                db.execute(text(f"ALTER TABLE creators ADD COLUMN {column_name} {column_type}"))
            else:
                logger.info(f"Column {column_name} already exists")
        
        # Add target demographic fields to advertisers table
        logger.info("Checking advertiser columns...")
        
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'advertisers' 
            AND column_name IN ('target_age_range', 'target_gender_skew', 'target_location', 'target_interests')
        """)).fetchall()
        
        existing_advertiser_columns = [row[0] for row in result]
        logger.info(f"Existing advertiser demographic columns: {existing_advertiser_columns}")
        
        advertiser_columns_to_add = [
            ('target_age_range', 'VARCHAR(10)'),
            ('target_gender_skew', 'VARCHAR(20)'),
            ('target_location', 'VARCHAR(10)'),
            ('target_interests', 'TEXT')
        ]
        
        for column_name, column_type in advertiser_columns_to_add:
            if column_name not in existing_advertiser_columns:
                logger.info(f"Adding advertiser column: {column_name}")
                db.execute(text(f"ALTER TABLE advertisers ADD COLUMN {column_name} {column_type}"))
            else:
                logger.info(f"Advertiser column {column_name} already exists")
        
        # Create topics table
        logger.info("Creating topics table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS topics (
                topic_id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        # Create keywords table
        logger.info("Creating keywords table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS keywords (
                keyword_id SERIAL PRIMARY KEY,
                keywords TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        # Create creator_topics table
        logger.info("Creating creator_topics table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS creator_topics (
                creator_id INTEGER REFERENCES creators(creator_id),
                topic_id INTEGER REFERENCES topics(topic_id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (creator_id, topic_id)
            )
        """))
        
        # Create creator_keywords table
        logger.info("Creating creator_keywords table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS creator_keywords (
                creator_id INTEGER REFERENCES creators(creator_id),
                keyword_id INTEGER REFERENCES keywords(keyword_id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (creator_id, keyword_id)
            )
        """))
        
        # Create creator_similarities table
        logger.info("Creating creator_similarities table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS creator_similarities (
                creator_a_id INTEGER REFERENCES creators(creator_id),
                creator_b_id INTEGER REFERENCES creators(creator_id),
                similarity_type VARCHAR(20) NOT NULL,
                similarity_score NUMERIC(5,4) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (creator_a_id, creator_b_id, similarity_type),
                CONSTRAINT check_different_creators CHECK (creator_a_id != creator_b_id),
                CONSTRAINT check_similarity_range CHECK (similarity_score >= 0 AND similarity_score <= 1)
            )
        """))
        
        # Commit all changes
        db.commit()
        logger.info("✅ Migration completed successfully!")
        
        # Verify the changes
        logger.info("\nVerifying migration...")
        
        # Check creator columns
        result = db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'creators' 
            AND column_name IN ('age_range', 'gender_skew', 'location', 'interests')
            ORDER BY column_name
        """)).fetchall()
        
        logger.info("Creator demographic columns:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[1]}")
        
        # Check new tables
        tables = ['topics', 'keywords', 'creator_topics', 'creator_keywords', 'creator_similarities']
        for table in tables:
            try:
                count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                logger.info(f"✅ {table}: {count} records")
            except Exception as e:
                logger.error(f"❌ {table}: {e}")
        
        logger.info("\n🎉 Database migration completed successfully!")
        logger.info("You can now upload creator CSVs with demographic data and use smart matching!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
