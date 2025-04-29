from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal
from RaspPiReader import pool
from RaspPiReader.ui.new_cycle import Ui_NewCycle
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler
from datetime import datetime  
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData
from RaspPiReader.libs.cycle_finalization import finalize_cycle
from PyQt5.QtWidgets import QMessageBox, QPushButton
import logging
import os

logger = logging.getLogger(__name__)

class NewCycleHandler(QtWidgets.QWidget):
    """
    NewCycleHandler encapsulates the logic for managing a cycle.
    When a cycle starts, the timing is reset and recorded.
    When a cycle stops, the elapsed time is logged, a CycleData record is created,
    and reports (CSV and PDF) are generated via finalize_cycle.
    """
    # Signal to notify when a cycle starts
    start_cycle_signal = pyqtSignal()
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
        
        # Initialize cycle status
        self.cycle_active = False
        
        # Find the green Start Cycle button in the default program selection step
        self.greenStartButton = self.findChild(QPushButton, "greenStartButton")
        if self.greenStartButton:
            self.greenStartButton.clicked.connect(self.onGreenStartButtonClicked)
            logger.info("Found and connected the green Start Cycle button")
        else:
            # If not found by direct name, try to find by text content
            for child in self.findChildren(QPushButton):
                if "Start Cycle" in child.text():
                    child.clicked.connect(self.onGreenStartButtonClicked)
                    self.greenStartButton = child
                    logger.info(f"Found green Start Cycle button with text: {child.text()}")
                    break
            
            if not self.greenStartButton:
                logger.warning("Green Start Cycle button not found - boolean reading may not activate correctly")

    def onGreenStartButtonClicked(self):
        """
        Handler for the green Start Cycle button in the default program selection step.
        This is the key method that should trigger boolean reading and cycle timer start.
        """
        logger.info("Green Start Cycle button clicked in default program selection")
        
        # Get the main form
        main_form = pool.get("main_form")
        if not main_form:
            logger.error("Main form not found in pool")
            QMessageBox.critical(self, "Error", "Main form not found. Cannot start cycle.")
            return
            
        # Set the cycle start time
        self.cycle_start_time = datetime.now()
        
        # Start the cycle timer
        if hasattr(main_form, "start_cycle_timer"):
            main_form.start_cycle_timer(self.cycle_start_time)
        else:
            logger.error("Main form does not have start_cycle_timer method")
            QMessageBox.critical(self, "Error", "Cannot start cycle timer. Please restart the application.")
            return
            
        # Emit the signal to start boolean reading
        self.start_cycle_signal.emit()
        
        # Update UI to indicate that boolean reading is active
        if hasattr(self.parent(), "boolean_group_box"):
            self.parent().boolean_group_box.setTitle("Boolean Data (Reading Active)")
        
        QMessageBox.information(self, "Cycle Started", 
            "Cycle started successfully. Live data monitoring is now active.")
            
    def reset_timing(self):
        """
        Reset all timing-related variables to their initial state.
        """
        self.cycle_start_time = None
        self.cycle_end_time = None
        self.core_temp_above_setpoint_time = 0
        self.pressure_drop_core_temp = None
        logger.info("Cycle timing reset: all timing variables set to initial state")

    def start_cycle(self):
        """
        Start a new cycle: reset timing, record start time, set up cycle,
        launch work order form, and enable channel/boolean display.
        Note: Live timer reading (and logging) will only be started after final input.
        """
        logger.info("Start Cycle button clicked - launching Work Order Form")
        self.reset_timing()
        self.cycle_start_time = None  # Don't set start time yet - wait for green button
        pool.set("current_cycle", self)
        self.cycle_active = True
        
        # Launch work order form for further user input.
        self.work_order_form = WorkOrderFormHandler()
        self.work_order_form.show()

        # Enable channel/boolean updates (without starting the timer).
        main_form = pool.get("main_form")
        if main_form:
            # Call a method that updates channel labels or boolean displays continuously.
            if hasattr(main_form, "enable_channel_updates"):
                main_form.enable_channel_updates()
            else:
                logger.info("Channel updates enabled (default behavior).")
        else:
            logger.warning("Main form not available to enable channel updates.")

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
        self.cycle_active = False
        
        # Stop boolean reading if main form has the method
        main_form = pool.get("main_form")
        if main_form and hasattr(main_form, "stop_boolean_reading"):
            main_form.stop_boolean_reading()
            logger.info("Boolean reading stopped")
        
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
                program_number = pool.config("program_number", int, 1),
                core_temp_setpoint = pool.config("core_temp_setpoint", float, 0.0),
                cool_down_temp = pool.config("cool_down_temp", float, 0.0),
                temp_ramp = pool.config("temp_ramp", float, 0.0),
                dwell_time = pool.config("dwell_time", float, 0.0),
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
            
    def cancel_cycle(self):
        """
        Cancel the active cycle without finalizing reports.
        This method stops boolean reading, resets timings, clears the cycle state and serial numbers,
        making the system ready for a new cycle.
        """
        if self.cycle_active:
            logger.info("Cancelling active cycle due to window close during serial number entry stage.")
            self.reset_timing()
            pool.set("current_cycle", None)
            self.cycle_active = False

            main_form = pool.get("main_form")
            if main_form and hasattr(main_form, "stop_boolean_reading"):
                main_form.stop_boolean_reading()
                logger.info("Boolean reading stopped on cycle cancel.")
            self.serial_numbers = []
        else:
            logger.info("No active cycle to cancel.")

    def closeEvent(self, event):
        """
        Override the close event to cancel an active cycle if the window is closed
        during the serial number entry stage.
        """
        if self.cycle_active:
            # Cancel the cycle without finalizing
            self.cancel_cycle()
            logger.info("NewCycleHandler window closed: active cycle cancelled, state reset for new cycle.")
        event.accept()
