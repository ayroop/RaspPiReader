from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, QPushButton
from PyQt5.QtCore import Qt
import logging
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, AlarmMapping
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class AlarmSettingsForm(QDialog):
    def __init__(self, parent=None):
        super(AlarmSettingsForm, self).__init__(parent)
        self.setWindowTitle("Alarm Settings")
        self.setMinimumWidth(800)
        
        # Create main layout
        layout = QVBoxLayout(self)
        
        # Create table widget for alarms
        self.tableWidget = QtWidgets.QTableWidget()
        self.tableWidget.setColumnCount(4)
        self.tableWidget.setHorizontalHeaderLabels(["Channel", "Threshold Value", "Alarm Message", "Active"])
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tableWidget)

        # Create button layout
        button_layout = QHBoxLayout()
        
        # Add buttons
        self.addButton = QPushButton("Add")
        self.editButton = QPushButton("Edit")
        self.removeButton = QPushButton("Remove")
        self.saveButton = QPushButton("Save")
        
        button_layout.addWidget(self.addButton)
        button_layout.addWidget(self.editButton)
        button_layout.addWidget(self.removeButton)
        button_layout.addWidget(self.saveButton)
        
        layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(layout)
        
        # Initialize database
        self.db = Database("sqlite:///local_database.db")
        
        # Connect button signals
        self.addButton.clicked.connect(self.add_alarm)
        self.editButton.clicked.connect(self.edit_alarm)
        self.removeButton.clicked.connect(self.remove_alarm)
        self.saveButton.clicked.connect(self.save_settings)
        
        # Load existing settings
        self.load_settings()
    
    def add_alarm(self):
        """Add a new alarm to the database"""
        try:
            channel = self.channel_combo.currentText()
            threshold = self.threshold_spin.value()
            message = self.message_edit.text()
            
            if not channel or not message:
                QtWidgets.QMessageBox.warning(self, "Warning", "Please fill in all fields")
                return
            
            with Session(self.db.engine) as session:
                # Check if alarm exists for this channel
                alarm = session.query(Alarm).filter_by(channel=channel).first()
                if not alarm:
                    # Create new alarm if it doesn't exist
                    alarm = Alarm(channel=channel, active=True)
                    session.add(alarm)
                    session.flush()  # Get the alarm ID
                
                # Create new mapping
                mapping = AlarmMapping(
                    alarm_id=alarm.id,
                    threshold=threshold,
                    message=message,
                    value=1 if threshold < 0 else 2,  # 1 for low, 2 for high
                    active=True
                )
                session.add(mapping)
                session.commit()
                
                # Reload settings to show all alarms
                self.load_settings()
                
                # Clear input fields
                self.message_edit.clear()
                
                QtWidgets.QMessageBox.information(self, "Success", "Alarm added successfully")
                
        except Exception as e:
            logger.error(f"Error adding alarm: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to add alarm: {str(e)}")
    
    def edit_alarm(self):
        """Edit the selected alarm"""
        current_row = self.tableWidget.currentRow()
        if current_row >= 0:
            # Get current values
            channel = self.tableWidget.cellWidget(current_row, 0).currentText()
            threshold = self.tableWidget.cellWidget(current_row, 1).value()
            message = self.tableWidget.cellWidget(current_row, 2).text()
            active = self.tableWidget.cellWidget(current_row, 3).isChecked()
            
            # Create edit dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Edit Alarm")
            layout = QVBoxLayout(dialog)
            
            # Channel selection
            channel_layout = QHBoxLayout()
            channel_layout.addWidget(QLabel("Channel:"))
            channel_combo = QtWidgets.QComboBox()
            channel_combo.addItems([f"CH{i}" for i in range(1, 15)])
            channel_combo.setCurrentText(channel)
            channel_layout.addWidget(channel_combo)
            layout.addLayout(channel_layout)
            
            # Threshold value
            threshold_layout = QHBoxLayout()
            threshold_layout.addWidget(QLabel("Threshold:"))
            threshold_spin = QDoubleSpinBox()
            threshold_spin.setRange(-999999, 999999)
            threshold_spin.setDecimals(2)
            threshold_spin.setValue(threshold)
            threshold_layout.addWidget(threshold_spin)
            layout.addLayout(threshold_layout)
            
            # Message
            message_layout = QHBoxLayout()
            message_layout.addWidget(QLabel("Message:"))
            message_edit = QLineEdit()
            message_edit.setText(message)
            message_layout.addWidget(message_edit)
            layout.addLayout(message_layout)
            
            # Active checkbox
            active_check = QtWidgets.QCheckBox("Active")
            active_check.setChecked(active)
            layout.addWidget(active_check)
            
            # Buttons
            button_layout = QHBoxLayout()
            save_button = QPushButton("Save")
            cancel_button = QPushButton("Cancel")
            button_layout.addWidget(save_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # Connect signals
            save_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            
            if dialog.exec_() == QDialog.Accepted:
                # Update table with new values
                self.tableWidget.cellWidget(current_row, 0).setCurrentText(channel_combo.currentText())
                self.tableWidget.cellWidget(current_row, 1).setValue(threshold_spin.value())
                self.tableWidget.cellWidget(current_row, 2).setText(message_edit.text())
                self.tableWidget.cellWidget(current_row, 3).setChecked(active_check.isChecked())
    
    def remove_alarm(self):
        """Remove the selected alarm"""
        current_row = self.tableWidget.currentRow()
        if current_row >= 0:
            self.tableWidget.removeRow(current_row)
    
    def load_settings(self):
        """Load existing alarm settings from database"""
        try:
            with Session(self.db.engine) as session:
                # Get all channels that have alarms
                channels = session.query(Alarm.channel).distinct().all()
                self.tableWidget.setRowCount(len(channels))
                
                for row, (channel,) in enumerate(channels):
                    # Get all active mappings for this channel
                    alarm = session.query(Alarm).filter_by(channel=channel).first()
                    mappings = session.query(AlarmMapping).filter_by(
                        alarm_id=alarm.id,
                        active=True
                    ).all()
                    
                    if mappings:
                        # Create a formatted string showing all thresholds and messages
                        alarm_info = []
                        for mapping in mappings:
                            threshold_type = "Low" if mapping.value == 1 else "High"
                            alarm_info.append(f"{threshold_type} Threshold ({mapping.threshold:.2f}): {mapping.message}")
                        
                        # Add to table with channel info
                        self.tableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(str(channel)))
                        self.tableWidget.setItem(row, 1, QtWidgets.QTableWidgetItem("\n".join(alarm_info)))
                        
                        # Set row height to accommodate multiple lines
                        self.tableWidget.setRowHeight(row, len(alarm_info) * 25)  # 25 pixels per line
                    else:
                        # Show channel with no active alarms
                        self.tableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(str(channel)))
                        self.tableWidget.setItem(row, 1, QtWidgets.QTableWidgetItem("No active alarms"))
                        self.tableWidget.setRowHeight(row, 25)  # Default height for single line
                
            # Resize columns and rows to fit content
            self.tableWidget.resizeColumnsToContents()
            self.tableWidget.resizeRowsToContents()
            
            # Set word wrap for the alarm settings column
            self.tableWidget.setWordWrap(True)
            
        except Exception as e:
            logger.error(f"Error loading alarm settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load alarm settings: {str(e)}")
    
    def save_settings(self):
        """Save alarm settings to database"""
        try:
            with Session(self.db.engine) as session:
                # Clear existing alarms
                session.query(Alarm).delete()
                session.commit()
                
                # Save new alarms
                for row in range(self.tableWidget.rowCount()):
                    channel = self.tableWidget.cellWidget(row, 0).currentText()
                    threshold = self.tableWidget.cellWidget(row, 1).value()
                    alarm_text = self.tableWidget.cellWidget(row, 2).text()
                    active = self.tableWidget.cellWidget(row, 3).isChecked()
                    
                    # Validate required fields
                    if not channel:
                        raise ValueError(f"Channel is required for row {row + 1}")
                    if threshold is None:
                        raise ValueError(f"Threshold value is required for {channel}")
                    if not alarm_text:
                        raise ValueError(f"Alarm message is required for {channel}")
                    
                    # Create new alarm
                    alarm = Alarm(channel=channel, active=active)
                    session.add(alarm)
                    session.flush()  # Get the alarm ID
                    
                    # Create alarm mapping
                    mapping = AlarmMapping(
                        alarm_id=alarm.id,
                        threshold=threshold,
                        message=alarm_text,
                        value=1 if threshold < 0 else 2,  # 1 for low, 2 for high
                        active=True
                    )
                    session.add(mapping)
                
                # Commit all changes
                session.commit()
                logger.info("Alarm settings saved successfully")
                QtWidgets.QMessageBox.information(self, "Success", "Alarm settings saved successfully")
                
        except ValueError as e:
            session.rollback()
            logger.error(f"Validation error saving alarm settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save alarm settings: {str(e)}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving alarm settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save alarm settings: {str(e)}")