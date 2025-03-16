
from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui.new_cycle import Ui_NewCycle
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler
from datetime import datetime  
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData
from RaspPiReader.libs.cycle_finalization import finalize_cycle
from PyQt5.QtWidgets import QMessageBox
import logging

logger = logging.getLogger(__name__)

class NewCycleHandler(QtWidgets.QWidget):
    """
    NewCycleHandler encapsulates the logic for managing a cycle.
    When a cycle starts, the timing is reset and recorded.
    When a cycle stops, the elapsed time is logged, a CycleData record is created,
    and reports (CSV and PDF) are generated via finalize_cycle.
    """
    def __init__(self, parent=None):
        super(NewCycleHandler, self).__init__(parent)
        self.ui = Ui_NewCycle()
        self.ui.setupUi(self)
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.stopCycleButton.clicked.connect(self.stop_cycle)
        # Initialize serial_numbers. They should be set as the cycle proceeds.
        self.serial_numbers = []

        # Initialize timing variables
        self.reset_timing()

    def reset_timing(self):
        self.cycle_start_time = None
        self.cycle_end_time = None
        logger.info("Cycle timing reset: cycle_start_time and cycle_end_time set to None")

    def start_cycle(self):
        """
        Start a new cycle: reset timing values, record the start time, 
        set this handler in the global pool, and launch the work order form.
        """
        logger.info("Start Cycle button clicked - launching Work Order Form")
        self.reset_timing()
        self.cycle_start_time = datetime.now()
        pool.set("current_cycle", self)
        self.work_order_form = WorkOrderFormHandler()
        self.work_order_form.show()

    def stop_cycle(self):
        """
        Stop the cycle: record the end time, calculate duration, create a CycleData
        instance from settings stored in the pool, attempt to generate reports, and show a message.
        """
        logger.info("Stop Cycle button clicked")
        if self.cycle_start_time is not None:
            self.cycle_end_time = datetime.now()
            duration = self.cycle_end_time - self.cycle_start_time
            logger.info(f"Cycle stopped; duration: {str(duration).split('.')[0]}")
        else:
            logger.warning("Cycle start time not set; cannot compute duration")
            # If start time is not set, there is no valid cycle so return
            QMessageBox.warning(self, "Cycle Error", "No cycle was started. Cannot stop cycle.")
            return

        # Clear the current cycle from the global pool
        pool.set("current_cycle", None)
        
        try:
            # Import CycleData
            from RaspPiReader.libs.models import CycleData
            # Build a CycleData record using values from the pool or defaults.
            # Note: maintain_vacuum is converted by first converting to int then to bool.
            cycle_data = CycleData(
                order_id = pool.config("order_id", str, "Unknown"),
                cycle_id = pool.config("cycle_id", str, "Unknown"),
                start_time = self.cycle_start_time,
                stop_time = self.cycle_end_time,
                quantity = pool.get("quantity") or 0,
                cycle_location = pool.config("cycle_location", str, "Unknown"),
                core_temp_setpoint = pool.config("core_temp_setpoint", float, 0.0),
                cool_down_temp = pool.config("cool_down_temp", float, 0.0),
                temp_ramp = pool.config("temp_ramp", float, 0.0),
                dwell_time = pool.config("dwell_time", str, "0"),
                set_pressure = pool.config("set_pressure", float, 0.0),
                # The maintain_vacuum value is expected to be numeric (e.g., 0 or 1)
                maintain_vacuum = bool(int(pool.config("maintain_vacuum", int, 0))),
                initial_set_cure_temp = pool.config("initial_set_cure_temp", float, 0.0),
                final_set_cure_temp = pool.config("final_set_cure_temp", float, 0.0),
                user_id = pool.config("user_id", int, 1)
            )
            
            # Save the cycle_data record to the database.
            db = Database("sqlite:///local_database.db")
            db.session.add(cycle_data)
            db.session.commit()
            
            # Obtain serial numbers for this cycle (if any)
            serial_numbers = self.serial_numbers if self.serial_numbers else []
            
            # Generate reports using finalize_cycle.
            pdf_filename, csv_filename = finalize_cycle(cycle_data, serial_numbers)
            logger.info(f"Reports generated: PDF: {pdf_filename}, CSV: {csv_filename}")
            
            # Show success message.
            QMessageBox.information(self, "Cycle Finalized",
                f"Cycle reports generated successfully.\nPDF: {pdf_filename}\nCSV: {csv_filename}")
        except Exception as e:
            logger.error(f"Error finalizing cycle: {e}")
            QMessageBox.critical(self, "Finalization Error", f"Error finalizing cycle: {str(e)}")
