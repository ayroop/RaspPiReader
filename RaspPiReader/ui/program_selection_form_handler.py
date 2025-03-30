from PyQt5 import QtWidgets, QtCore
from datetime import datetime
import traceback
from RaspPiReader.ui.program_selection_form import Ui_ProgramSelectionForm
from RaspPiReader.ui.start_cycle_form_handler import StartCycleFormHandler
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, DefaultProgram, User, CycleSerialNumber
from RaspPiReader import pool
import logging

logger = logging.getLogger(__name__)

class ProgramSelectionFormHandler(QtWidgets.QWidget):
    def __init__(self, work_order, serial_numbers, quantity, parent=None):
        super(ProgramSelectionFormHandler, self).__init__(parent)
        self.ui = Ui_ProgramSelectionForm()
        self.ui.setupUi(self)
        self.work_order = work_order
        self.quantity = quantity      # store user set quantity
        self.serial_numbers = serial_numbers  # list of (processed) serial numbers
        self.db = Database("sqlite:///local_database.db")
        logger.info(f"ProgramSelectionFormHandler initiated with quantity: {self.quantity}")
        self.setWindowTitle(f"Select Program for Order: {work_order}")
        self.resize(800, 600)
        self.setMinimumSize(800, 600)
        self.setStyleSheet("QWidget { font-size: 16px; }")
        if hasattr(self.ui, "programLabel"):
            self.ui.programLabel.setText("Select Program:")
        self.populate_program_combo()
        if hasattr(self.ui, "startCycleButton"):
            self.ui.startCycleButton.setText("Start Cycle")
        if hasattr(self.ui, "cancelButton"):
            self.ui.cancelButton.setText("Cancel")
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.cancelButton.clicked.connect(self.close)
        self.ui.programComboBox.currentIndexChanged.connect(self.update_program_info)
        self.update_program_info(self.ui.programComboBox.currentIndex())
    
    def populate_program_combo(self):
        if self.ui.programComboBox.count() == 0:
            self.ui.programComboBox.addItem("Program 1")
            self.ui.programComboBox.addItem("Program 2")
            self.ui.programComboBox.addItem("Program 3")
            self.ui.programComboBox.addItem("Program 4")
    
    def update_program_info(self, index):
        program_index = index + 1
        current_user = pool.get("current_user")
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=program_index
        ).first()

        if default_program:
            pool.set_config("cycle_location", default_program.cycle_location or "N/A")
            pool.set_config("dwell_time", default_program.dwell_time if default_program.dwell_time is not None else 0.0)
            pool.set_config("core_temp_setpoint", default_program.core_temp_setpoint if default_program.core_temp_setpoint is not None else 0.0)
            pool.set_config("cool_down_temp", default_program.cool_down_temp if default_program.cool_down_temp is not None else 0.0)
            pool.set_config("temp_ramp", default_program.temp_ramp if default_program.temp_ramp is not None else 0.0)
            pool.set_config("set_pressure", default_program.set_pressure if default_program.set_pressure is not None else 0.0)
            pool.set_config("maintain_vacuum", default_program.maintain_vacuum if default_program.maintain_vacuum is not None else 0.0)
            pool.set_config("initial_set_cure_temp", default_program.initial_set_cure_temp if default_program.initial_set_cure_temp is not None else 0.0)
            pool.set_config("final_set_cure_temp", default_program.final_set_cure_temp if default_program.final_set_cure_temp is not None else 0.0)
            pool.set_config("quantity", self.quantity)
            # Pass along any pre‐existing cycle_id (may be empty)
            pool.set_config("cycle_id", default_program.cycle_id if hasattr(default_program, "cycle_id") and default_program.cycle_id is not None else "")
            info_text = f"""
            <div style="font-family:Arial; font-size:16px; margin:10px;">
                <h3 style="margin-bottom:10px;">Program {program_index} Settings</h3>
                <table border="1" cellspacing="0" cellpadding="4" style="border-collapse: collapse; width:100%;">
                    <tr style="background-color:#f0f0f0;">
                        <th align="left">Field</th>
                        <th align="left">Value</th>
                    </tr>
                    <tr><td>Size</td><td>{default_program.size or 'N/A'}</td></tr>
                    <tr><td>Cycle ID</td><td>{default_program.cycle_id or 'N/A'}</td></tr>
                    <tr><td>Cycle Location</td><td>{default_program.cycle_location or 'N/A'}</td></tr>
                    <tr><td>Dwell Time</td><td>{default_program.dwell_time or 'N/A'}</td></tr>
                    <tr><td>Cool Down Temperature</td><td>{default_program.cool_down_temp or 'N/A'}°C</td></tr>
                    <tr><td>Core Temperature Setpoint</td><td>{default_program.core_temp_setpoint or 'N/A'}°C</td></tr>
                    <tr><td>Temperature Ramp</td><td>{default_program.temp_ramp or 'N/A'}°C/min</td></tr>
                    <tr><td>Set Pressure</td><td>{default_program.set_pressure or 'N/A'} kPa</td></tr>
                    <tr><td>Maintain Vacuum</td><td>{default_program.maintain_vacuum or 'N/A'} %</td></tr>
                    <tr><td>Initial Set Cure Temperature</td><td>{default_program.initial_set_cure_temp or 'N/A'}°C</td></tr>
                    <tr><td>Final Set Cure Temperature</td><td>{default_program.final_set_cure_temp or 'N/A'}°C</td></tr>
                    <tr><td>Quantity</td><td>{self.quantity}</td></tr>
                </table>
            </div>
            """
        else:
            info_text = f"""
            <div style="font-family:Arial; font-size:16px; margin:10px;">
                <h3>Program {program_index}</h3>
                <p>No default settings found for this program.</p>
            </div>
            """
        if hasattr(self.ui, "programInfoLabel"):
            self.ui.programInfoLabel.setMinimumWidth(500)
            self.ui.programInfoLabel.setMinimumHeight(400)
            self.ui.programInfoLabel.setTextFormat(QtCore.Qt.RichText)
            self.ui.programInfoLabel.setText(info_text)
    
    def start_cycle(self):
        logger.info("Start Cycle button pressed")
        program_index = self.ui.programComboBox.currentIndex() + 1
        current_user = pool.get("current_user")
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=program_index
        ).first()
        if not default_program:
            QtWidgets.QMessageBox.warning(
                self, "Warning", f"No default program found for Program {program_index}"
            )
            return

        user = self.db.session.query(User).filter_by(username=current_user).first()
        if not user:
            QtWidgets.QMessageBox.critical(self, "Database Error", "Logged-in user not found.")
            return

        try:
            core_temp_setpoint = float(default_program.core_temp_setpoint)
            cool_down_temp = float(default_program.cool_down_temp)
            set_pressure = float(default_program.set_pressure)
            maintain_vacuum = bool(int(default_program.maintain_vacuum))
            initial_set_cure_temp = float(default_program.initial_set_cure_temp)
            final_set_cure_temp = float(default_program.final_set_cure_temp)

            new_cycle = CycleData(
                order_id=self.work_order,
                quantity=self.quantity,
                core_temp_setpoint=core_temp_setpoint,
                cool_down_temp=cool_down_temp,
                set_pressure=set_pressure,
                maintain_vacuum=maintain_vacuum,
                initial_set_cure_temp=initial_set_cure_temp,
                final_set_cure_temp=final_set_cure_temp
            )
            new_cycle.user = user

            # Ensure cycle_id is valid. If missing, empty, or "N/A", generate a new one.
            if not new_cycle.cycle_id or new_cycle.cycle_id.strip() in ["", "N/A"]:
                from RaspPiReader.ui.default_program_form import DefaultProgramForm
                new_cycle.cycle_id = DefaultProgramForm().generate_cycle_id()

            self.db.session.add(new_cycle)
            self.db.session.commit()
            self.cycle_record = new_cycle

            # Immediately update the pool config so that later modules (e.g. reporting or visualization) see the correct cycle_id.
            pool.set_config("cycle_id", new_cycle.cycle_id)

            # Handle serial numbers properly
            valid_serials = [sn.strip() for sn in self.serial_numbers if sn.strip()]
            
            if valid_serials:
                # Insert all valid serial numbers, skipping duplicates
                for sn in valid_serials:
                    try:
                        # Check if the serial number already exists in the database
                        existing_serial = self.db.session.query(CycleSerialNumber).filter_by(serial_number=sn).first()
                        if existing_serial:
                            logger.warning(f"Serial number {sn} already exists. Skipping insertion.")
                            continue
                        
                        # Create a new CycleSerialNumber record and associate it with the current cycle
                        record = CycleSerialNumber(cycle_id=new_cycle.id, serial_number=sn)
                        self.db.session.add(record)
                        logger.info(f"Added serial number {sn} to cycle {new_cycle.id}")
                    except Exception as e:
                        logger.error(f"Error inserting serial number {sn}: {e}")
                        self.db.session.rollback()
                        QtWidgets.QMessageBox.critical(
                            self, "Database Error", f"Failed to save serial number {sn}: {str(e)}"
                        )
                        return  # Abort if there's an error
            else:
                # Generate a unique placeholder if no valid serial numbers are provided
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                placeholder = f"PLACEHOLDER_{new_cycle.id}_{timestamp}"
                try:
                    record = CycleSerialNumber(cycle_id=new_cycle.id, serial_number=placeholder)
                    self.db.session.add(record)
                    logger.info(f"Using unique placeholder serial number: {placeholder}")
                except Exception as e:
                    logger.error(f"Error inserting placeholder serial number: {e}")
            
            self.db.session.commit()
            logger.info(f"New cycle created: Order {self.work_order}, Program {program_index}, Quantity {self.quantity}, {len(self.serial_numbers)} serial numbers")
        except Exception as e:
            self.db.session.rollback()
            error_details = traceback.format_exc()
            logger.error(f"Database error creating cycle: {e}\n{error_details}")
            QtWidgets.QMessageBox.critical(
                self, "Database Error", f"Failed to create cycle: {str(e)}"
            )
            return

        start_cycle_form = pool.get("start_cycle_form")
        if start_cycle_form and hasattr(start_cycle_form, "start_cycle"):
            start_cycle_form.start_cycle()

        main_form = pool.get("main_form")
        if main_form:
            from datetime import datetime
            main_form.new_cycle_handler.cycle_start_time = datetime.now()
            if hasattr(main_form, "start_cycle_timer"):
                main_form.start_cycle_timer(main_form.new_cycle_handler.cycle_start_time)
            if hasattr(main_form, "set_cycle_start_register"):
                main_form.set_cycle_start_register(1)
            if hasattr(main_form, "update_cycle_info_pannel"):
                main_form.update_cycle_info_pannel(default_program)
            logger.info("Cycle timer started after program selection.")
        else:
            logger.warning("Main form not available for finalizing cycle start.")

        QtWidgets.QMessageBox.information(self, "Success", "Cycle started successfully!")
        self.close()
