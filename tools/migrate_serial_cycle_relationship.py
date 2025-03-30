import os
import sys
import logging
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, Float, MetaData, Table, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Add the parent directory to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

from RaspPiReader.libs.database import get_engine, get_session

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_if_column_exists(engine, table_name, column_name):
    """
    Check if a column exists in a table
    """
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    if table_name in metadata.tables:
        table = metadata.tables[table_name]
        return column_name in table.columns
    
    return False

def migrate_database():
    """
    Migrate the database to add the serial_number_id column to the cycle_data table
    """
    logger.info("Starting database migration for serial-cycle relationship")
    
    try:
        engine = get_engine()
        
        # Check if serial_number_id column already exists in cycle_data table
        if not check_if_column_exists(engine, 'cycle_data', 'serial_number_id'):
            logger.info("Adding serial_number_id column to cycle_data table")
            
            # Create a MetaData instance
            metadata = MetaData()
            metadata.reflect(bind=engine)
            
            # Get the cycle_data table
            cycle_data_table = metadata.tables['cycle_data']
            
            # Use a connection context manager instead of engine.execute()
            with engine.connect() as connection:
                # Execute the ALTER TABLE statement to add the serial_number_id column
                connection.execute(
                    text(f"ALTER TABLE {cycle_data_table.name} ADD COLUMN serial_number_id INTEGER")
                )
                connection.commit()
            
                # Add foreign key constraint (optional, depending on your database)
                try:
                    connection.execute(
                        text(f"ALTER TABLE {cycle_data_table.name} ADD CONSTRAINT fk_serial_number "
                             f"FOREIGN KEY (serial_number_id) REFERENCES cycle_serial_numbers(id)")
                    )
                    connection.commit()
                    logger.info("Added foreign key constraint to serial_number_id column")
                except Exception as e:
                    logger.warning(f"Could not add foreign key constraint: {str(e)}")
                    logger.warning("The column was added but without a foreign key constraint")
            
                # Add an index to improve query performance
                try:
                    connection.execute(
                        text(f"CREATE INDEX idx_cycle_data_serial_number_id ON {cycle_data_table.name} (serial_number_id)")
                    )
                    connection.commit()
                    logger.info("Added index on serial_number_id column")
                except Exception as e:
                    logger.warning(f"Could not add index on serial_number_id column: {str(e)}")
            
            logger.info("Successfully added serial_number_id column to cycle_data table")
        else:
            logger.info("serial_number_id column already exists in cycle_data table")
            
            # Check if index exists and create if needed
            with engine.connect() as connection:
                try:
                    result = connection.execute(
                        text("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='idx_cycle_data_serial_number_id'")
                    ).scalar()
                    
                    if result == 0:
                        connection.execute(text("CREATE INDEX idx_cycle_data_serial_number_id ON cycle_data (serial_number_id)"))
                        connection.commit()
                        logger.info("Added missing index on serial_number_id column")
                except Exception as e:
                    logger.warning(f"Error checking/creating index: {str(e)}")
        
        # Now update existing data if needed
        update_existing_data(engine)
        
        # Verify the migration
        with engine.connect() as connection:
            count_total = connection.execute(text("SELECT COUNT(*) FROM cycle_data")).scalar()
            count_assigned = connection.execute(text("SELECT COUNT(*) FROM cycle_data WHERE serial_number_id IS NOT NULL")).scalar()
            
            if count_total > 0:
                percentage = (count_assigned / count_total) * 100
            else:
                percentage = 0
                
            logger.info(f"Migration summary: {count_assigned} of {count_total} cycles have serial numbers assigned ({percentage:.1f}%)")
        
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error migrating database: {str(e)}")
        raise

def update_existing_data(engine):
    """
    Update existing data to set cycle-serial relationships based on available data
    """
    logger.info("Updating existing data to establish cycle-serial relationships")
    
    session = get_session()
    
    try:
        # Use a connection context manager instead of engine.execute()
        with engine.connect() as connection:
            # For each cycle, set its serial_number_id to the id of any associated serial number
            # from the cycle_serial_numbers table
            result = connection.execute(
                text("""
                UPDATE cycle_data cd
                SET serial_number_id = (
                    SELECT csn.id 
                    FROM cycle_serial_numbers csn 
                    WHERE csn.cycle_id = cd.id
                    LIMIT 1
                )
                WHERE cd.serial_number_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM cycle_serial_numbers csn 
                    WHERE csn.cycle_id = cd.id
                )
                """)
            )
            connection.commit()
            
            # Get the number of rows affected (in SQLAlchemy 2.0, rowcount might be -1 in some cases)
            affected_rows = result.rowcount if result.rowcount > 0 else "Unknown number of"
            logger.info(f"Updated {affected_rows} cycle records with serial number relationships")
            
            # Check for any remaining unassigned cycles
            count_result = connection.execute(text("SELECT COUNT(*) FROM cycle_data WHERE serial_number_id IS NULL")).scalar()
        if count_result > 0:
            logger.warning(f"There are still {count_result} cycles without an assigned serial number")
        else:
            logger.info("All cycles have been successfully assigned to serial numbers")
            
    except Exception as e:
        logger.error(f"Error updating existing data: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    migrate_database()
