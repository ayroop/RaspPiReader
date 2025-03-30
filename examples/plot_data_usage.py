# -*- coding: utf-8 -*-
"""
Example code showing how to integrate and use the new plot data tab.
This is for reference purposes - the actual integration happens in main_form_handler.py
"""
from PyQt5 import QtWidgets, QtCore
import sys
import random
from RaspPiReader.ui.plot_data_tab import PlotDataTab

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Plot Data Tab Example")
        self.resize(1200, 800)
        
        # Create central widget and layout
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QtWidgets.QVBoxLayout(self.central_widget)
        
        # Create tab widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        # Create a dummy dashboard tab
        dashboard = QtWidgets.QWidget()
        dashboard_layout = QtWidgets.QVBoxLayout(dashboard)
        dashboard_layout.addWidget(QtWidgets.QLabel("This is the dashboard tab"))
        self.tab_widget.addTab(dashboard, "Dashboard")
        
        # Create the plot data tab
        self.plot_tab = PlotDataTab()
        self.tab_widget.addTab(self.plot_tab, "Plot Data")
        
        # Start a timer to simulate data updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_with_random_data)
        self.timer.start(1000)  # Update every second
    
    def update_with_random_data(self):
        """Update the plot with random data for demonstration."""
        # Generate random values for channels
        channel_values = {f'ch{i}': random.uniform(0, 100) for i in range(1, 15)}
        
        # Generate random boolean values
        boolean_values = {f'bool{i}': random.choice([True, False]) for i in range(1, 7)}
        
        # Update the plot
        self.plot_tab.update_plot(channel_values, boolean_values)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())