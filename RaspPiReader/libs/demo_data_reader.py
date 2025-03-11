import csv
import os
import random
import time
import threading
from RaspPiReader import pool
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import DemoData

data = []
db = Database("sqlite:///local_database.db")

# Load data from the database
demo_data = db.session.query(DemoData).all()
if demo_data:
    data = [[record.column1, record.column2, record.column3, record.column4, record.column5, record.column6, record.column7, record.column8, record.column9, record.column10, record.column11, record.column12, record.column13, record.column14] for record in demo_data]
else:
    demo_file_path = os.path.join(os.getcwd(), "RaspPiReader", "demo.csv")
    if os.path.exists(demo_file_path):
        with open(demo_file_path) as file_name:
            file_read = csv.reader(file_name)
            data = list(file_read)
        # Save data to the database
        for row in data:
            demo_record = DemoData(
                column1=row[0], column2=row[1], column3=row[2], column4=row[3], column5=row[4], column6=row[5],
                column7=row[6], column8=row[7], column9=row[8], column10=row[9], column11=row[10], column12=row[11],
                column13=row[12], column14=row[13]
            )
            db.session.add(demo_record)
        db.session.commit()
    else:
        print(f"Warning: {demo_file_path} not found. Demo data will be empty.")

def load_demo_data():
    demo_file_path = os.path.join(os.getcwd(), "RaspPiReader", "demo.csv")
    data = []
    if os.path.exists(demo_file_path):
        with open(demo_file_path) as f:
            csv_reader = csv.reader(f)
            data = list(csv_reader)
    return data

def simulate_data_update():
    """Simulate data updates by setting random values to pool keys.
    These keys must match what MainFormHandler.read_live_data reads."""
    while True:
        # Vacuum gauge channels (KPa)
        for ch in range(1, 9):
            pool.set(f"vacuum_CH{ch}", random.uniform(0.0, 10.0))
        # Temperature channels (°C)
        for ch in range(9, 13):
            pool.set(f"temp_CH{ch}", random.uniform(20.0, 30.0))
        # Cylinder pressure & system vacuum
        pool.set("pressure_CH13", random.uniform(0.0, 5.0))
        pool.set("vacuum_CH14", random.uniform(0.0, 5.0))
        # (Optionally) update CSV delimiter and other config values
        pool.set("csv_delimiter", ",")
        # Sleep for 0.5 sec before next update
        time.sleep(0.5)

def start_demo_reader():
    """Starts the demo data update loop in a separate daemon thread."""
    demo_thread = threading.Thread(target=simulate_data_update, daemon=True)
    demo_thread.start()

# On module load, you could choose to start the demo reader.
if __name__ == "__main__":
    print("Starting demo data update simulation...")
    start_demo_reader()
    while True:
        # Just wait to keep the thread alive.
        time.sleep(1)