from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, AlarmMapping
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def configure_alarms():
    db = Database("sqlite:///local_database.db")
    
    # Define alarm configurations for each channel
    alarm_configs = {
        "CH1": {
            "default_text": "CH1 Alarm",
            "mappings": {
                1: "CH1 Low Pressure",
                2: "CH1 High Pressure",
                3: "CH1 Vacuum Leak",
                4: "CH1 Sensor Fault",
                5: "CH1 Communication Error",
                6: "CH1 Over Temperature",
                7: "CH1 Under Temperature",
                8: "CH1 System Error"
            }
        },
        "CH2": {
            "default_text": "CH2 Alarm",
            "mappings": {
                1: "CH2 Low Pressure",
                2: "CH2 High Pressure",
                3: "CH2 Vacuum Leak",
                4: "CH2 Sensor Fault",
                5: "CH2 Communication Error",
                6: "CH2 Over Temperature",
                7: "CH2 Under Temperature",
                8: "CH2 System Error"
            }
        },
        "CH3": {
            "default_text": "CH3 Alarm",
            "mappings": {
                1: "CH3 Low Pressure",
                2: "CH3 High Pressure",
                3: "CH3 Vacuum Leak",
                4: "CH3 Sensor Fault",
                5: "CH3 Communication Error",
                6: "CH3 Over Temperature",
                7: "CH3 Under Temperature",
                8: "CH3 System Error"
            }
        },
        "CH4": {
            "default_text": "CH4 Alarm",
            "mappings": {
                1: "CH4 Low Pressure",
                2: "CH4 High Pressure",
                3: "CH4 Vacuum Leak",
                4: "CH4 Sensor Fault",
                5: "CH4 Communication Error",
                6: "CH4 Over Temperature",
                7: "CH4 Under Temperature",
                8: "CH4 System Error"
            }
        }
    }
    
    try:
        # Clear existing alarms and mappings
        db.session.query(AlarmMapping).delete()
        db.session.query(Alarm).delete()
        
        # Create new alarms and mappings
        for channel, config in alarm_configs.items():
            # Create alarm
            alarm = Alarm(channel=channel, alarm_text=config["default_text"])
            db.session.add(alarm)
            db.session.flush()  # Get the alarm ID
            
            # Create mappings
            for value, message in config["mappings"].items():
                mapping = AlarmMapping(
                    alarm_id=alarm.id,
                    value=value,
                    message=message
                )
                db.session.add(mapping)
        
        # Commit changes
        db.session.commit()
        logger.info("Successfully configured alarms with best practices")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error configuring alarms: {e}")
        raise

if __name__ == "__main__":
    configure_alarms() 