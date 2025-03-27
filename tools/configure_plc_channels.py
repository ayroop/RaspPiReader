#!/usr/bin/env python
"""
PLC Channel Configuration Helper

This script helps configure the PLC channel addresses in the database.
Run this script to set up the vacuum gauge, temperature, pressure, and boolean addresses.
"""

import sys
import os
import sqlite3
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QPushButton, QWidget, QLabel, QHBoxLayout, QSpinBox, QLineEdit,
    QGroupBox, QFormLayout, QTabWidget, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import ChannelConfigSettings, BooleanAddress
from RaspPiReader import pool

class PLCConfigHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLC Channel Configuration Helper")
        self.resize(800, 600)
        
        # Initialize database
        self.db = Database("sqlite:///local_database.db")
        
        # Create main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.setup_channel_tab()
        self.setup_boolean_tab()
        self.setup_control_tab()
        
        # Add save button
        self.save_button = QPushButton("Save All Configurations")
        self.save_button.clicked.connect(self.save_all)
        self.main_layout.addWidget(self.save_button)
        
        # Load data from database
        self.load_data()
    
    def setup_channel_tab(self):
        channel_widget = QWidget()
        channel_layout = QVBoxLayout(channel_widget)
        
        # Vacuum gauges (CH1-CH8)
        vacuum_group = QGroupBox("Vacuum Gauges (CH1-CH8)")
        vacuum_layout = QFormLayout(vacuum_group)
        self.vacuum_address_inputs = []
        self.vacuum_scale_inputs = []
        self.vacuum_decimals_inputs = []
        
        for i in range(1, 9):
            row_layout = QHBoxLayout()
            
            # Address input
            address_input = QSpinBox()
            address_input.setRange(0, 65535)
            address_input.setPrefix(f"CH{i} Address: ")
            row_layout.addWidget(address_input)
            self.vacuum_address_inputs.append(address_input)
            
            # Scale checkbox
            scale_check = QCheckBox("Apply Scaling")
            row_layout.addWidget(scale_check)
            self.vacuum_scale_inputs.append(scale_check)
            
            # Decimal places
            decimals_input = QSpinBox()
            decimals_input.setRange(0, 6)
            decimals_input.setPrefix("Decimal Places: ")
            row_layout.addWidget(decimals_input)
            self.vacuum_decimals_inputs.append(decimals_input)
            
            vacuum_layout.addRow(f"Channel {i}", row_layout)
        
        channel_layout.addWidget(vacuum_group)
        
        # Temperature channels (CH9-CH12)
        temp_group = QGroupBox("Temperature Channels (CH9-CH12)")
        temp_layout = QFormLayout(temp_group)
        self.temp_address_inputs = []
        self.temp_scale_inputs = []
        self.temp_decimals_inputs = []
        
        for i in range(9, 13):
            row_layout = QHBoxLayout()
            
            # Address input
            address_input = QSpinBox()
            address_input.setRange(0, 65535)
            address_input.setPrefix(f"CH{i} Address: ")
            row_layout.addWidget(address_input)
            self.temp_address_inputs.append(address_input)
            
            # Scale checkbox
            scale_check = QCheckBox("Apply Scaling")
            row_layout.addWidget(scale_check)
            self.temp_scale_inputs.append(scale_check)
            
            # Decimal places
            decimals_input = QSpinBox()
            decimals_input.setRange(0, 6)
            decimals_input.setPrefix("Decimal Places: ")
            row_layout.addWidget(decimals_input)
            self.temp_decimals_inputs.append(decimals_input)
            
            temp_layout.addRow(f"Channel {i}", row_layout)
        
        channel_layout.addWidget(temp_group)
        
        # Pressure & System Vacuum (CH13-CH14)
        pressure_group = QGroupBox("Pressure & System Vacuum (CH13-CH14)")
        pressure_layout = QFormLayout(pressure_group)
        self.pressure_address_inputs = []
        self.pressure_scale_inputs = []
        self.pressure_decimals_inputs = []
        
        for i, label in [(13, "Cylinder Pressure"), (14, "System Vacuum")]:
            row_layout = QHBoxLayout()
            
            # Address input
            address_input = QSpinBox()
            address_input.setRange(0, 65535)
            address_input.setPrefix(f"CH{i} Address: ")
            row_layout.addWidget(address_input)
            self.pressure_address_inputs.append(address_input)
            
            # Scale checkbox
            scale_check = QCheckBox("Apply Scaling")
            row_layout.addWidget(scale_check)
            self.pressure_scale_inputs.append(scale_check)
            
            # Decimal places
            decimals_input = QSpinBox()
            decimals_input.setRange(0, 6)
            decimals_input.setPrefix("Decimal Places: ")
            row_layout.addWidget(decimals_input)
            self.pressure_decimals_inputs.append(decimals_input)
            
            pressure_layout.addRow(f"{label} (CH{i})", row_layout)
        
        channel_layout.addWidget(pressure_group)
        
        self.tab_widget.addTab(channel_widget, "Channel Addresses")
    
    def setup_boolean_tab(self):
        boolean_widget = QWidget()
        boolean_layout = QVBoxLayout(boolean_widget)
        
        # Create boolean address table
        self.bool_table = QTableWidget(6, 2)  # 6 rows, 2 columns
        self.bool_table.setHorizontalHeaderLabels(["Address", "Label"])
        
        # Set up table properties
        self.bool_table.horizontalHeader().setStretchLastSection(True)
        self.bool_table.setColumnWidth(0, 100)
        
        boolean_layout.addWidget(QLabel("Boolean Addresses (Coils)"))
        boolean_layout.addWidget(self.bool_table)
        
        self.tab_widget.addTab(boolean_widget, "Boolean Addresses")
    
    def setup_control_tab(self):
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        # Cycle Control Address
        cycle_group = QGroupBox("Cycle Control")
        cycle_layout = QFormLayout(cycle_group)
        
        self.cycle_start_address = QSpinBox()
        self.cycle_start_address.setRange(0, 65535)
        cycle_layout.addRow("Cycle Start/Stop Address (Coil):", self.cycle_start_address)
        
        # Alarm Address
        alarm_group = QGroupBox("Alarm Settings")
        alarm_layout = QFormLayout(alarm_group)
        
        self.alarm_address = QSpinBox()
        self.alarm_address.setRange(0, 65535)
        alarm_layout.addRow("Alarm Status Address (Register):", self.alarm_address)
        
        control_layout.addWidget(cycle_group)
        control_layout.addWidget(alarm_group)
        control_layout.addStretch()
        
        self.tab_widget.addTab(control_widget, "Control Addresses")
    
    def load_data(self):
        # Load channel settings
        for i in range(1, 15):
            channel = self.db.session.query(ChannelConfigSettings).filter_by(id=i).first()
            if channel:
                # Determine which array to use based on channel number
                if i <= 8:
                    address_array = self.vacuum_address_inputs
                    scale_array = self.vacuum_scale_inputs
                    decimals_array = self.vacuum_decimals_inputs
                    idx = i - 1
                elif i <= 12:
                    address_array = self.temp_address_inputs
                    scale_array = self.temp_scale_inputs
                    decimals_array = self.temp_decimals_inputs
                    idx = i - 9
                else:
                    address_array = self.pressure_address_inputs
                    scale_array = self.pressure_scale_inputs
                    decimals_array = self.pressure_decimals_inputs
                    idx = i - 13

                # Set values with error handling
                try:
                    address_value = int(channel.address) if channel.address is not None else 0
                    address_array[idx].setValue(address_value)
                except (ValueError, TypeError):
                    address_array[idx].setValue(0)

                try:
                    scale_value = bool(channel.scale) if channel.scale is not None else False
                    scale_array[idx].setChecked(scale_value)
                except (ValueError, TypeError):
                    scale_array[idx].setChecked(False)

                try:
                    # Updated attribute from 'decimal_point' to 'dec_point'
                    decimal_value = int(channel.dec_point) if channel.dec_point is not None else 0
                    decimals_array[idx].setValue(decimal_value)
                except (ValueError, TypeError):
                    decimals_array[idx].setValue(0)
    
    def save_all(self):
        try:
            # Save channel settings
            for i in range(1, 15):
                # Determine which array to use based on channel number
                if i <= 8:
                    address_array = self.vacuum_address_inputs
                    scale_array = self.vacuum_scale_inputs
                    decimals_array = self.vacuum_decimals_inputs
                    idx = i - 1
                elif i <= 12:
                    address_array = self.temp_address_inputs
                    scale_array = self.temp_scale_inputs
                    decimals_array = self.temp_decimals_inputs
                    idx = i - 9
                else:
                    address_array = self.pressure_address_inputs
                    scale_array = self.pressure_scale_inputs
                    decimals_array = self.pressure_decimals_inputs
                    idx = i - 13

                # Get values from UI inputs
                address = address_array[idx].value()
                scale = scale_array[idx].isChecked()
                decimals = decimals_array[idx].value()

                # Update or create channel settings
                channel = self.db.session.query(ChannelConfigSettings).filter_by(id=i).first()
                if not channel:
                    channel = ChannelConfigSettings(id=i)
                    self.db.session.add(channel)

                # Ensure integer values are set
                channel.address = int(address)
                channel.scale = bool(scale)
                channel.decimal_point = int(decimals)
                channel.active = bool(address > 0)  # Set active if address is specified

                # Default values for other required fields if they're missing
                if channel.label is None:
                    channel.label = f"Channel {i}"
                if channel.pv is None:
                    channel.pv = 0
                if channel.sv is None:
                    channel.sv = 0
                
                if not hasattr(channel, 'set_point') or channel.set_point is None:
                    channel.set_point = 0
                if channel.limit_low is None:
                    channel.limit_low = 0
                if channel.limit_high is None:
                    channel.limit_high = 1000
                if channel.axis_direction is None:
                    channel.axis_direction = "Vertical"
                if channel.color is None:
                    channel.color = "#000000"
                if channel.min_scale_range is None:
                    channel.min_scale_range = 0
                if channel.max_scale_range is None:
                    channel.max_scale_range = 1000

                # Also update pool configuration
                pool.set_config(f'channel_{i}_address', int(address))
                pool.set_config(f'scale{i}', bool(scale))
                pool.set_config(f'decimal_point{i}', int(decimals))
                pool.set_config(f'active{i}', bool(address > 0))
            
            # Save boolean addresses
            self.db.session.query(BooleanAddress).delete()
            for i in range(6):
                address_item = self.bool_table.item(i, 0)
                label_item = self.bool_table.item(i, 1)
                
                if address_item and label_item:
                    try:
                        address = int(address_item.text())
                        label = label_item.text().strip()
                        new_entry = BooleanAddress(address=address, label=label)
                        self.db.session.add(new_entry)
                    except ValueError:
                        pass
            
            # Save control addresses
            cycle_addr = self.cycle_start_address.value()
            pool.set_config('cycle_control_address', int(cycle_addr))
            
            alarm_addr = self.alarm_address.value()
            pool.set_config('alarm_address', int(alarm_addr))
            
            # Commit changes to the database
            self.db.session.commit()
            
            QMessageBox.information(self, "Success", "All PLC configurations saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLCConfigHelper()
    window.show()
    sys.exit(app.exec_())