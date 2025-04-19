from RaspPiReader import pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def configure_alarm_addresses():
    # Configure alarm addresses for each channel
    # Using standard Modbus addresses starting from 300 for alarms
    alarm_addresses = {
        "CH1": 300,  # Base address for CH1 alarms
        "CH2": 301,  # Base address for CH2 alarms
        "CH3": 302,  # Base address for CH3 alarms
        "CH4": 303,  # Base address for CH4 alarms
    }
    
    try:
        # Configure each channel's alarm address
        for channel, address in alarm_addresses.items():
            pool.set_config(f'alarm/{channel}_address', address)
            logger.info(f"Configured {channel} alarm address to {address}")
        
        # Configure global alarm settings
        pool.set_config('alarm_addresses', list(alarm_addresses.values()))
        
        # Configure alarm check interval (in milliseconds)
        pool.set_config('alarm_check_interval', 1000)  # Check every second
        
        # Configure alarm persistence (how long to show cleared alarms)
        pool.set_config('alarm_persistence', 5000)  # Show cleared alarms for 5 seconds
        
        logger.info("Successfully configured alarm addresses")
        
        # Verify configuration
        logger.info("\nVerifying configuration:")
        for channel in alarm_addresses.keys():
            addr = pool.config(f'alarm/{channel}_address', int, 0)
            logger.info(f"{channel} alarm address: {addr}")
            
    except Exception as e:
        logger.error(f"Error configuring alarm addresses: {e}")
        raise

if __name__ == "__main__":
    configure_alarm_addresses() 