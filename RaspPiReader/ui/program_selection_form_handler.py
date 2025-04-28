from PyQt5 import QtWidgets, QtCore
from datetime import datetime
import traceback
from RaspPiReader.ui.program_selection_form import Ui_ProgramSelectionForm
from RaspPiReader.ui.start_cycle_form_handler import StartCycleFormHandler
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, DefaultProgram, User, CycleSerialNumber
from RaspPiReader import pool
from RaspPiReader.libs.plc_communication import write_holding_register
import logging

logger = logging.getLogger(__name__)

class ProgramSelectionFormHandler(QtWidgets.QWidget):
    def __init__(self, work_order, serial_numbers, quantity, parent=None):
        super(ProgramSelectionFormHandler, self).__init__(parent)
        self.ui = Ui_ProgramSelectionForm()
        self.ui.setupUi(self)
        self.work_order = work_order
        self.quantity = quantity
        self.serial_numbers = serial_numbers
        self.db = Database("sqlite:///local_database.db")
        self.selected_program = None
        
        logger.info(f"ProgramSelectionFormHandler initiated with quantity: {self.quantity}")
        self.setWindowTitle(f"Select Program for Order: {work_order}")
        self.resize(1200, 800)
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                border: 2px solid #CCCCCC;
                border-radius: 5px;
                margin-top: 1ex;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QLabel {
                font-size: 14px;
            }
        """)
        
        # Connect program selection buttons
        self.ui.selectProgram1Button.clicked.connect(lambda: self.select_program(1))
        self.ui.selectProgram2Button.clicked.connect(lambda: self.select_program(2))
        self.ui.selectProgram3Button.clicked.connect(lambda: self.select_program(3))
        self.ui.selectProgram4Button.clicked.connect(lambda: self.select_program(4))
        
        # Connect start and cancel buttons
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.cancelButton.clicked.connect(self.on_cancel)
        
        # Load program information
        self.load_program_info()
    
    def load_program_info(self):
        """Load and display information for all four programs"""
        current_user = pool.get("current_user")
        for program_num in range(1, 5):
            default_program = self.db.session.query(DefaultProgram).filter_by(
                username=current_user, program_number=program_num
            ).first()
            
            info_label = getattr(self.ui, f"program{program_num}InfoLabel")
            if default_program:
                info_text = f"""
                <div style="font-family:Arial; font-size:14px; margin:10px;">
                    <table border="1" cellspacing="0" cellpadding="4" style="border-collapse: collapse; width:100%;">
                        <tr style="background-color:#f0f0f0;">
                            <th align="left">Field</th>
                            <th align="left">Value</th>
                        </tr>
                        <tr><td>Size</td><td>{default_program.size or 'N/A'}</td></tr>
                        <tr><td>Cycle Location</td><td>{default_program.cycle_location or 'N/A'}</td></tr>
                        <tr><td>Dwell Time</td><td>{default_program.dwell_time or 'N/A'}</td></tr>
                        <tr><td>Cool Down Temperature</td><td>{default_program.cool_down_temp or 'N/A'}°C</td></tr>
                        <tr><td>Core Temperature Setpoint</td><td>{default_program.core_temp_setpoint or 'N/A'}°C</td></tr>
                        <tr><td>Temperature Ramp</td><td>{default_program.temp_ramp or 'N/A'}°C/min</td></tr>
                        <tr><td>Set Pressure</td><td>{default_program.set_pressure or 'N/A'} kPa</td></tr>
                        <tr><td>Maintain Vacuum</td><td>{default_program.maintain_vacuum or 'N/A'} %</td></tr>
                        <tr><td>Initial Set Cure Temperature</td><td>{default_program.initial_set_cure_temp or 'N/A'}°C</td></tr>
                        <tr><td>Final Set Cure Temperature</td><td>{default_program.final_set_cure_temp or 'N/A'}°C</td></tr>
                    </table>
                </div>
                """
            else:
                info_text = f"""
                <div style="font-family:Arial; font-size:14px; margin:10px;">
                    <p>No default settings found for Program {program_num}.</p>
                </div>
                """
            
            info_label.setTextFormat(QtCore.Qt.RichText)
            info_label.setText(info_text)
    
    def select_program(self, program_number):
        """Handle program selection and update UI accordingly"""
        # Reset all program group boxes
        for i in range(1, 5):
            group_box = getattr(self.ui, f"program{i}GroupBox")
            group_box.setStyleSheet("QGroupBox { border: 2px solid #CCCCCC; }")
        
        # Highlight selected program
        selected_group_box = getattr(self.ui, f"program{program_number}GroupBox")
        selected_group_box.setStyleSheet("QGroupBox { border: 2px solid #007bff; }")
        
        self.selected_program = program_number
        
        # Write the selected program number to the PLC
        try:
            plc_address = pool.config('selected_program_address', int, 100)  # Default address if not configured
            write_holding_register(plc_address, program_number)
            logger.info(f"Selected program {program_number} written to PLC address {plc_address}")
        except Exception as e:
            logger.error(f"Error writing to PLC: {e}")
            QtWidgets.QMessageBox.warning(
                self, "PLC Communication Error",
                f"Could not update PLC with selected program: {str(e)}"
            )
    
    def start_cycle(self):
        if not self.selected_program:
            QtWidgets.QMessageBox.warning(
                self, "Warning", "Please select a program before starting the cycle."
            )
            return
            
        logger.info(f"Start Cycle button pressed for Program {self.selected_program}")
        current_user = pool.get("current_user")
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=self.selected_program
        ).first()
        
        if not default_program:
            QtWidgets.QMessageBox.warning(
                self, "Warning", f"No default program found for Program {self.selected_program}"
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

            if not new_cycle.cycle_id or new_cycle.cycle_id.strip() in ["", "N/A"]:
                from RaspPiReader.ui.default_program_form import DefaultProgramForm
                new_cycle.cycle_id = DefaultProgramForm().generate_cycle_id()

            self.db.session.add(new_cycle)
            self.db.session.commit()
            self.cycle_record = new_cycle

            pool.set_config("cycle_id", new_cycle.cycle_id)
            pool.set("current_cycle", new_cycle)

            valid_serials = [sn.strip() for sn in self.serial_numbers if sn.strip()]
            inserted_serials = set()
            if valid_serials:
                for sn in valid_serials:
                    if sn in inserted_serials:
                        logger.warning(f"Serial number {sn} already processed in this cycle. Skipping duplicate insertion.")
                        continue
                    existing_serial = self.db.session.query(CycleSerialNumber).filter_by(cycle_id=new_cycle.id, serial_number=sn).first()
                    if existing_serial:
                        logger.warning(f"Serial number {sn} already exists in cycle {new_cycle.id}. Skipping insertion.")
                        inserted_serials.add(sn)
                        continue
                    record = CycleSerialNumber(cycle_id=new_cycle.id, serial_number=sn)
                    self.db.session.add(record)
                    inserted_serials.add(sn)
                    logger.info(f"Added serial number {sn} to cycle {new_cycle.id}")
            else:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                placeholder = f"PLACEHOLDER_{new_cycle.id}_{timestamp}"
                try:
                    record = CycleSerialNumber(cycle_id=new_cycle.id, serial_number=placeholder)
                    self.db.session.add(record)
                    logger.info(f"Using unique placeholder serial number: {placeholder}")
                except Exception as e:
                    logger.error(f"Error inserting placeholder serial number: {e}")

            self.db.session.commit()
            logger.info(f"New cycle created: Order {self.work_order}, Program {self.selected_program}, Quantity {self.quantity}, {len(self.serial_numbers)} serial numbers")
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

        if main_form:
            current_cycle = pool.get("current_cycle")
            if not hasattr(current_cycle, "id"):
                current_cycle = self.cycle_record
                pool.set("current_cycle", current_cycle)
            current_cycle_id = current_cycle.id if current_cycle is not None else None
            main_form.viz_manager.start_visualization(current_cycle_id)
            main_form.start_boolean_reading()
            logger.info("Cycle and visualization started")
        else:
            logger.error("Main form not found in pool; cannot start visualization and boolean data reading.")

        QtWidgets.QMessageBox.information(self, "Success", "Cycle started successfully!")
        self.close()

    def on_cancel(self):
        """Handle form cancellation"""
        logger.info("Program selection form cancelled")
        
        # Reset menu items in main form
        main_form = pool.get('main_form')
        if main_form:
            main_form.actionStart.setEnabled(True)
            main_form.actionStop.setEnabled(False)
        
        # Clear any cycle data that might have been set
        pool.set("current_cycle", None)
        
        # Close the form
        self.close()
