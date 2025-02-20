import csv
import os
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import DemoData

data = []
db = Database("sqlite:///local_database.db")

# Load data from the database
demo_data = db.session.query(DemoData).all()
if demo_data:
    data = [[record.column1, record.column2, record.column3, record.column4, record.column5, record.column6, record.column7, record.column8, record.column9, record.column10, record.column11, record.column12, record.column13, record.column14] for record in demo_data]
else:
    demo_file_path = os.path.join(os.getcwd(), "demo.csv")
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