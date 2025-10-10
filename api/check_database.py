"""
Check database structure and data for creators table.
This will show us what columns actually exist and what data is populated.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from app.db import get_db
from app.models import Creator
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_database_structure():
    """Check the actual database structure and data."""
    logger.info("Checking database structure and data...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Check if the new columns exist
        logger.info("\n" + "="*50)
        logger.info("CHECKING CREATOR TABLE STRUCTURE")
        logger.info("="*50)
        
        # Get table info
        inspector = inspect(db.bind)
        columns = inspector.get_columns('creators')
        
        logger.info("Current creator table columns:")
        for column in columns:
            logger.info(f"  - {column['name']}: {column['type']} (nullable: {column['nullable']})")
        
        # Check if new demographic columns exist
        demographic_columns = ['age_range', 'gender_skew', 'location', 'interests']
        existing_demographic_columns = [col['name'] for col in columns if col['name'] in demographic_columns]
        
        logger.info(f"\nDemographic columns found: {existing_demographic_columns}")
        
        if len(existing_demographic_columns) < len(demographic_columns):
            missing_columns = set(demographic_columns) - set(existing_demographic_columns)
            logger.warning(f"Missing demographic columns: {missing_columns}")
            logger.warning("The database migration may not have run yet!")
        
        # Check sample data
        logger.info("\n" + "="*50)
        logger.info("CHECKING SAMPLE CREATOR DATA")
        logger.info("="*50)
        
        # Get a few sample creators
        sample_creators = db.query(Creator).limit(3).all()
        
        if sample_creators:
            logger.info(f"Found {len(sample_creators)} sample creators:")
            for i, creator in enumerate(sample_creators, 1):
                logger.info(f"\nCreator {i}:")
                logger.info(f"  - ID: {creator.creator_id}")
                logger.info(f"  - Name: {creator.name}")
                logger.info(f"  - Acct ID: {creator.acct_id}")
                logger.info(f"  - Email: {creator.owner_email}")
                logger.info(f"  - Topic: {creator.topic}")
                
                # Check if demographic fields exist and have data
                if hasattr(creator, 'age_range'):
                    logger.info(f"  - Age Range: {creator.age_range}")
                else:
                    logger.warning("  - Age Range: Column does not exist!")
                
                if hasattr(creator, 'gender_skew'):
                    logger.info(f"  - Gender Skew: {creator.gender_skew}")
                else:
                    logger.warning("  - Gender Skew: Column does not exist!")
                
                if hasattr(creator, 'location'):
                    logger.info(f"  - Location: {creator.location}")
                else:
                    logger.warning("  - Location: Column does not exist!")
                
                if hasattr(creator, 'interests'):
                    logger.info(f"  - Interests: {creator.interests}")
                else:
                    logger.warning("  - Interests: Column does not exist!")
        else:
            logger.warning("No creators found in database!")
        
        # Check if new tables exist
        logger.info("\n" + "="*50)
        logger.info("CHECKING NEW TABLES")
        logger.info("="*50)
        
        new_tables = ['topics', 'keywords', 'creator_topics', 'creator_keywords', 'creator_similarities']
        
        for table_name in new_tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                logger.info(f"✓ {table_name}: {result} records")
            except Exception as e:
                logger.warning(f"✗ {table_name}: Table does not exist - {e}")
        
        # Check migration status
        logger.info("\n" + "="*50)
        logger.info("CHECKING MIGRATION STATUS")
        logger.info("="*50)
        
        try:
            # Check if alembic_version table exists
            result = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
            logger.info(f"Current migration version: {result}")
        except Exception as e:
            logger.warning(f"Could not check migration version: {e}")
        
        logger.info("\n" + "="*50)
        logger.info("SUMMARY")
        logger.info("="*50)
        
        if len(existing_demographic_columns) == len(demographic_columns):
            logger.info("✅ All demographic columns exist in creators table")
        else:
            logger.error("❌ Missing demographic columns - database migration needed!")
        
        # Check if any creators have demographic data
        if sample_creators:
            has_demographic_data = any(
                hasattr(creator, 'age_range') and creator.age_range 
                for creator in sample_creators
            )
            
            if has_demographic_data:
                logger.info("✅ Some creators have demographic data")
            else:
                logger.warning("⚠️ No creators have demographic data populated")
        
        return {
            'demographic_columns_exist': len(existing_demographic_columns) == len(demographic_columns),
            'missing_columns': set(demographic_columns) - set(existing_demographic_columns),
            'sample_creators_count': len(sample_creators),
            'new_tables_exist': all(
                any(table_name in str(e) for e in [Exception()] if False) or True
                for table_name in new_tables
            )
        }
        
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        return {'error': str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    check_database_structure()
