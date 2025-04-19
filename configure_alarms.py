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
        },
        "CH5": {
            "default_text": "CH5 Alarm",
            "mappings": {
                1: "CH5 Low Pressure",
                2: "CH5 High Pressure",
                3: "CH5 Vacuum Leak",
                4: "CH5 Sensor Fault",
                5: "CH5 Communication Error",
                6: "CH5 Over Temperature",
                7: "CH5 Under Temperature",
                8: "CH5 System Error"
            }
        },
        "CH6": {
            "default_text": "CH6 Alarm",
            "mappings": {
                1: "CH6 Low Pressure",
                2: "CH6 High Pressure",
                3: "CH6 Vacuum Leak",
                4: "CH6 Sensor Fault",
                5: "CH6 Communication Error",
                6: "CH6 Over Temperature",
                7: "CH6 Under Temperature",
                8: "CH6 System Error"
            }
        },
        "CH7": {
            "default_text": "CH7 Alarm",
            "mappings": {
                1: "CH7 Low Pressure",
                2: "CH7 High Pressure",
                3: "CH7 Vacuum Leak",
                4: "CH7 Sensor Fault",
                5: "CH7 Communication Error",
                6: "CH7 Over Temperature",
                7: "CH7 Under Temperature",
                8: "CH7 System Error"
            }
        },
        "CH8": {
            "default_text": "CH8 Alarm",
            "mappings": {
                1: "CH8 Low Pressure",
                2: "CH8 High Pressure",
                3: "CH8 Vacuum Leak",
                4: "CH8 Sensor Fault",
                5: "CH8 Communication Error",
                6: "CH8 Over Temperature",
                7: "CH8 Under Temperature",
                8: "CH8 System Error"
            }
        },
        "CH9": {
            "default_text": "CH9 Alarm",
            "mappings": {
                1: "CH9 Low Pressure",
                2: "CH9 High Pressure",
                3: "CH9 Vacuum Leak",
                4: "CH9 Sensor Fault",
                5: "CH9 Communication Error",
                6: "CH9 Over Temperature",
                7: "CH9 Under Temperature",
                8: "CH9 System Error"
            }
        },
        "CH10": {
            "default_text": "CH10 Alarm",
            "mappings": {
                1: "CH10 Low Pressure",
                2: "CH10 High Pressure",
                3: "CH10 Vacuum Leak",
                4: "CH10 Sensor Fault",
                5: "CH10 Communication Error",
                6: "CH10 Over Temperature",
                7: "CH10 Under Temperature",
                8: "CH10 System Error"
            }
        },
        "CH11": {
            "default_text": "CH11 Alarm",
            "mappings": {
                1: "CH11 Low Pressure",
                2: "CH11 High Pressure",
                3: "CH11 Vacuum Leak",
                4: "CH11 Sensor Fault",
                5: "CH11 Communication Error",
                6: "CH11 Over Temperature",
                7: "CH11 Under Temperature",
                8: "CH11 System Error"
            }
        },
        "CH12": {
            "default_text": "CH12 Alarm",
            "mappings": {
                1: "CH12 Low Pressure",
                2: "CH12 High Pressure",
                3: "CH12 Vacuum Leak",
                4: "CH12 Sensor Fault",
                5: "CH12 Communication Error",
                6: "CH12 Over Temperature",
                7: "CH12 Under Temperature",
                8: "CH12 System Error"
            }
        },
        "CH13": {
            "default_text": "CH13 Alarm",
            "mappings": {
                1: "CH13 Low Pressure",
                2: "CH13 High Pressure",
                3: "CH13 Vacuum Leak",
                4: "CH13 Sensor Fault",
                5: "CH13 Communication Error",
                6: "CH13 Over Temperature",
                7: "CH13 Under Temperature",
                8: "CH13 System Error"
            }
        },
        "CH14": {
            "default_text": "CH14 Alarm",
            "mappings": {
                1: "CH14 Low Pressure",
                2: "CH14 High Pressure",
                3: "CH14 Vacuum Leak",
                4: "CH14 Sensor Fault",
                5: "CH14 Communication Error",
                6: "CH14 Over Temperature",
                7: "CH14 Under Temperature",
                8: "CH14 System Error"
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