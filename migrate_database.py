from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, CycleSerialNumber

def migrate_serial_numbers():
    db = Database("sqlite:///local_database.db")
    cycles = db.session.query(CycleData).filter(CycleData.serial_numbers.isnot(None)).all()
    for cycle in cycles:
        serial_list = [s.strip() for s in cycle.serial_numbers.split(',') if s.strip()]
        # Remove any existing CycleSerialNumber records first
        db.session.query(CycleSerialNumber).filter(CycleSerialNumber.cycle_id == cycle.id).delete()
        for sn in serial_list:
            record = CycleSerialNumber(cycle_id=cycle.id, serial_number=sn)
            db.session.add(record)
        # Optionally clear the comma-separated field:
        cycle.serial_numbers = ""
    db.session.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_serial_numbers()