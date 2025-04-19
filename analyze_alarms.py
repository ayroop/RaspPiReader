from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, AlarmMapping
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_alarm_config():
    db = Database("sqlite:///local_database.db")
    
    # Check alarm channels
    alarms = db.session.query(Alarm).all()
    logger.info("\n=== Alarm Channel Configuration ===")
    for alarm in alarms:
        logger.info(f"Channel: {alarm.channel}")
        logger.info(f"Default Text: {alarm.alarm_text}")
        
        # Check mappings
        mappings = db.session.query(AlarmMapping).filter_by(alarm_id=alarm.id).all()
        logger.info("Mappings:")
        for mapping in mappings:
            logger.info(f"  Value {mapping.value}: {mapping.message}")
        logger.info("---")

if __name__ == "__main__":
    analyze_alarm_config() 