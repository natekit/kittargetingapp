"""
Fix column sizes for demographic data.
The current columns are too small for the actual data.
"""

from sqlalchemy import text
from app.db import get_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_column_sizes():
    """Fix column sizes to accommodate the actual data."""
    logger.info("Fixing column sizes for demographic data...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Fix location column - increase from VARCHAR(10) to VARCHAR(50)
        logger.info("Fixing location column size...")
        db.execute(text("ALTER TABLE creators ALTER COLUMN location TYPE VARCHAR(50)"))
        
        # Fix interests column - change from VARCHAR to TEXT
        logger.info("Fixing interests column type...")
        db.execute(text("ALTER TABLE creators ALTER COLUMN interests TYPE TEXT"))
        
        # Fix gender_skew column - increase from VARCHAR(20) to VARCHAR(50)
        logger.info("Fixing gender_skew column size...")
        db.execute(text("ALTER TABLE creators ALTER COLUMN gender_skew TYPE VARCHAR(50)"))
        
        # Fix age_range column - increase from VARCHAR(10) to VARCHAR(20)
        logger.info("Fixing age_range column size...")
        db.execute(text("ALTER TABLE creators ALTER COLUMN age_range TYPE VARCHAR(20)"))
        
        # Also fix advertiser columns
        logger.info("Fixing advertiser column sizes...")
        db.execute(text("ALTER TABLE advertisers ALTER COLUMN target_location TYPE VARCHAR(50)"))
        db.execute(text("ALTER TABLE advertisers ALTER COLUMN target_interests TYPE TEXT"))
        db.execute(text("ALTER TABLE advertisers ALTER COLUMN target_gender_skew TYPE VARCHAR(50)"))
        db.execute(text("ALTER TABLE advertisers ALTER COLUMN target_age_range TYPE VARCHAR(20)"))
        
        # Commit changes
        db.commit()
        logger.info("✅ Column sizes fixed successfully!")
        
        # Verify the changes
        logger.info("Verifying column sizes...")
        result = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = 'creators' 
            AND column_name IN ('age_range', 'gender_skew', 'location', 'interests')
            ORDER BY column_name
        """)).fetchall()
        
        logger.info("Updated creator column sizes:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[1]}{f'({row[2]})' if row[2] else ''}")
        
        logger.info("✅ Column size fix completed!")
        
    except Exception as e:
        logger.error(f"❌ Column size fix failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_column_sizes()
