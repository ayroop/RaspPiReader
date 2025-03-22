#!/usr/bin/env python3
"""
Migration script to add or update the plot_data table.
This adds support for storing visualization data linked to cycles.
"""

import os
import sys
import logging
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database connection
db_path = "sqlite:///local_database.db"
engine = create_engine(db_path)
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

def main():
    """Execute the migration"""
    logger.info("Starting plot_data table migration")
    
    # Check if table exists
    table_exists = engine.dialect.has_table(engine.connect(), "plot_data")
    
    if table_exists:
        logger.info("plot_data table exists, checking for cycle_id column")
        # Check if cycle_id column exists
        from sqlalchemy import inspect
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('plot_data')]
        
        if 'cycle_id' not in columns:
            logger.info("Adding cycle_id column to plot_data table")
            # Add cycle_id column
            engine.execute('ALTER TABLE plot_data ADD COLUMN cycle_id INTEGER')
            engine.execute('ALTER TABLE plot_data ADD FOREIGN KEY (cycle_id) REFERENCES cycle_data(id)')
            logger.info("Added cycle_id column to plot_data table")
        else:
            logger.info("cycle_id column already exists")
    else:
        logger.info("Creating plot_data table")
        # Create the table
        class PlotData(Base):
            __tablename__ = 'plot_data'
            id = Column(Integer, primary_key=True)
            timestamp = Column(DateTime, default=datetime.utcnow)
            channel = Column(String, nullable=False)
            value = Column(Float, nullable=False)
            cycle_id = Column(Integer, ForeignKey('cycle_data.id'), nullable=True)
        
        # Create the table
        Base.metadata.create_all(engine, tables=[PlotData.__table__])
        logger.info("Created plot_data table")
    
    logger.info("Migration completed successfully")

if __name__ == "__main__":
    main()