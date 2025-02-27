import os
import csv
from datetime import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer, pyqtSignal, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QErrorMessage, QMessageBox, QApplication, QLabel, QAction
from colorama import Fore

from RaspPiReader import pool
from .mainForm import MainForm
from .plot_handler import InitiatePlotWidget
from .plot_preview_form_handler import PlotPreviewFormHandler
from .setting_form_handler import SettingFormHandler, CHANNEL_COUNT
from .start_cycle_form_handler import StartCycleFormHandler
from .user_management_form_handler import UserManagementFormHandler
from RaspPiReader.ui.one_drive_settings_form_handler import OneDriveSettingsFormHandler
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from .plc_comm_settings_form_handler import PLCCommSettingsFormHandler
from RaspPiReader.ui.database_settings_form_handler import DatabaseSettingsFormHandler

# New import related with 6 bool addresses and new cycle widget
from RaspPiReader.libs.communication import dataReader
from RaspPiReader.libs.configuration import config
from RaspPiReader.ui.mainForm import MainForm
from .boolean_status import Ui_BooleanStatusWidget
from RaspPiReader.libs.models import BooleanStatus, PlotData
from RaspPiReader.libs.database import Database
from RaspPiReader.ui.new_cycle_handler import NewCycleHandler

# Add default program settings
from RaspPiReader.ui.default_program_form import DefaultProgramForm
# New Cycle logic
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler
# Add Alarm settings
from RaspPiReader.ui.alarm_settings_form_handler import AlarmSettingsFormHandler
# BackgroundSettingsForm
from RaspPiReader.ui.background_settings_form import BackgroundSettingsForm
# Add PLC connection status
from RaspPiReader.libs import plc_communication
def timedelta2str(td):
    h, rem = divmod(td.seconds, 3600)
    m, s = divmod(rem, 60)
    def zp(val):
        return str(val) if val >= 10 else f"0{val}"
    return "{0}:{1}:{2}".format(zp(h), zp(m), zp(s))

class MainFormHandler(QtWidgets.QMainWindow):
    update_status_bar_signal = pyqtSignal(str, int, str)
    
    def __init__(self, user_record=None):
        super(MainFormHandler, self).__init__()
        self.user_record = user_record
        print(f"Initializing MainFormHandler with user_record: {self.user_record}")
        self.form_obj = MainForm()
        self.form_obj.setupUi(self)
        
        self.file_name = None
        self.folder_name = None
        self.csv_path = None
        self.pdf_path = None
      # self.plot = None
        self.username = self.user_record.username if self.user_record else ''
        pool.set('main_form', self)
        self.cycle_timer = QTimer()
        self.set_connections()
        self.start_cycle_form = pool.set('cycle_start_form', StartCycleFormHandler())
        self.display_username()
        # (Optional) create data stacks
        self.create_stack()
        
        self.set_connections()
        self.setup_access_controls()
        self.connect_menu_actions()
        # Add OneDrive Settings option to the menu
        self.add_one_drive_menu()
        # Add PLC Setting to the menu
        self.add_plc_comm_menu()
        # Add Database Setting to the menu
        self.add_database_menu()
        
        # 6 Bool Addresses status
        self.db = Database("sqlite:///local_database.db")
        self.setup_bool_status_display()
        self.setup_plot_data_display()
        
        # Integrate new cycle widget next to the Boolean status widget
        self.integrate_new_cycle_widget()
        
        # Create a timer to update status every few seconds
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_bool_status)
        self.status_timer.start(5000)  # update every 5 seconds
        # Setup main form for products serial numbers
        self.add_default_program_menu()
        # Alarm Settings Menu
        self.add_alarm_settings_menu()
        # Fix menu hover styles with targeted CSS
        menuStyle = """
            /* Only target menu items, not other widgets */
            QMenu::item:selected {
                background-color: #0078d7;
                color: white;
                /* Fix text position shifting */
                padding-left: 10px;
                padding-top: 4px;
                padding-bottom: 4px;
            }
            
            QMenuBar::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """
        
        # Apply this style only to the menubar and its menus
        self.menubar.setStyleSheet(menuStyle)
        # Add Background setting
        self.add_background_settings_menu()
        self.load_background()
        # Add PLC connection status
        self.connectionTimer = QTimer()
        self.connectionTimer.timeout.connect(self.update_connection_status_display)
        self.connectionTimer.start(5000)  # Update every 5 seconds
        self.showMaximized()
        print("MainFormHandler initialized.")
    
    def add_background_settings_menu(self):
    # Get the already existing File menu (assume you have one)
        menubar = self.menuBar()
        file_menu = None
        for action in menubar.actions():
            if action.text() == "File":
                file_menu = action.menu()
                break
        if file_menu is None:
            # Create File menu if it doesn't exist
            file_menu = menubar.addMenu("File")
        # Add "Background Settings" action next to others
        bg_action = QAction("Background Settings", self)
        bg_action.triggered.connect(self.open_background_settings)
        file_menu.addAction(bg_action)

    def open_background_settings(self):
        dialog = BackgroundSettingsForm(self)
        if dialog.exec_():
            self.load_background()

    def load_background(self):
        # Read saved settings and set the style for the main window.
        settings = QSettings("RaspPiHandler", "RaspPiReader")
        color = settings.value("background/color", "")
        image = settings.value("background/image", "")
        style = ""
        if color:
            style = f"background-color: {color};"
        elif image and os.path.exists(image):
            # Use the image as background without forcing scaling (CSS will handle repetition/position)
            style = f"background-image: url({image}); background-repeat: no-repeat; background-position: center;"
        else:
            # No background style by default
            style = ""
        self.setStyleSheet(style)

    def add_alarm_settings_menu(self):
        # Create a new menu called "Alarms" if not already present.
        menubar = self.menuBar()
        alarms_menu = menubar.addMenu("Alarms")
        alarm_settings_action = QAction("Manage Alarms", self)
        alarm_settings_action.triggered.connect(self.open_alarm_settings)
        alarms_menu.addAction(alarm_settings_action)
    
    def open_alarm_settings(self):
        # Instantiate and show the Alarm Settings dialog.
        dialog = AlarmSettingsFormHandler(self)
        dialog.exec_()
    def new_cycle_start(self):
        self.workOrderForm = WorkOrderFormHandler()
        self.workOrderForm.show()

    def add_default_program_menu(self):
        menubar = self.menuBar()
        defaultProgMenu = menubar.addMenu("Default Programs")
        manageAction = QtWidgets.QAction("Manage Default Programs", self)
        manageAction.triggered.connect(self.open_default_program_management)
        defaultProgMenu.addAction(manageAction)

    def open_default_program_management(self):
        dlg = DefaultProgramForm(self)
        dlg.exec_()
    
    def setup_bool_status_display(self):
        self.boolStatusWidgetContainer = QtWidgets.QWidget()
        self.boolStatusWidget = Ui_BooleanStatusWidget()
        self.boolStatusWidget.setupUi(self.boolStatusWidgetContainer)
        self.boolStatusLabels = [
            self.boolStatusWidget.boolStatusLabel1,
            self.boolStatusWidget.boolStatusLabel2,
            self.boolStatusWidget.boolStatusLabel3,
            self.boolStatusWidget.boolStatusLabel4,
            self.boolStatusWidget.boolStatusLabel5,
            self.boolStatusWidget.boolStatusLabel6,
        ]
        central_layout = self.centralWidget().layout()
        if central_layout is None:
            central_layout = QtWidgets.QVBoxLayout(self.centralWidget())
        # Add the boolean status widget container to the layout (it will be reinserted with the new widget)
        central_layout.addWidget(self.boolStatusWidgetContainer)
        
    def integrate_new_cycle_widget(self):
        # Create an instance of the new cycle widget
        self.new_cycle_handler = NewCycleHandler(self)
        
        # Get the central layout of the QMainWindow (set up by MainForm.setupUi)
        central_layout = self.centralWidget().layout()
        if central_layout is None:
            central_layout = QtWidgets.QVBoxLayout(self.centralWidget())
        
        # Remove the already added bool status widget container from the central layout
        central_layout.removeWidget(self.boolStatusWidgetContainer)
        
        # Create a new container with a horizontal layout
        container = QtWidgets.QWidget(self.centralWidget())
        h_layout = QtWidgets.QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        # Add the Boolean status container on the left
        h_layout.addWidget(self.boolStatusWidgetContainer)
        # Add the new cycle widget on the right
        h_layout.addWidget(self.new_cycle_handler)
        
        # Add the container to the central layout
        central_layout.addWidget(container)
        container.show()

    def update_bool_status(self):
        # Ensure dataReader is started.
        if not getattr(dataReader, 'connected', False):
            dataReader.start()
        # Read the 6 boolean coil addresses starting at the first configured address.
        result = dataReader.read_bool_addresses(1, config.bool_addresses[0], count=6)
        if result is None:
            status_str = "PLC not responding"
            for label in self.boolStatusLabels:
                label.setText(status_str)
        else:
            for i, state in enumerate(result):
                self.boolStatusLabels[i].setText(f"Bool Addr {config.bool_addresses[i]}: {state}")

    def setup_plot_data_display(self):
        self.plotWidgetContainer = QtWidgets.QWidget()
        self.plotWidgetContainer.setLayout(QtWidgets.QVBoxLayout())  # Ensure the container has a layout
        self.plotWidget = InitiatePlotWidget(active_channels=[], parent_layout=self.plotWidgetContainer.layout(), headers=["Time", "Value", ""])
        central_layout = self.centralWidget().layout()
        if central_layout is None:
            central_layout = QtWidgets.QVBoxLayout(self.centralWidget())
        central_layout.addWidget(self.plotWidgetContainer)

    def add_one_drive_menu(self):
        one_drive_action = QAction("OneDrive Settings", self)
        one_drive_action.triggered.connect(self.show_onedrive_settings)
        self.menuBar().addAction(one_drive_action)

    def show_onedrive_settings(self):
        dialog = OneDriveSettingsFormHandler(self)
        dialog.exec_()

    def add_plc_comm_menu(self):
        menubar = self.menuBar()
        plc_menu = menubar.addMenu("PLC")
        plc_settings_action = QtWidgets.QAction("PLC Communication Settings", self)
        plc_menu.addAction(plc_settings_action)
        plc_settings_action.triggered.connect(self.show_plc_comm_settings)

    def show_plc_comm_settings(self):
        dialog = PLCCommSettingsFormHandler(self)
        dialog.exec_()

    def add_database_menu(self):
        database_menu = self.menuBar().addMenu("Database")
        database_settings_action = QtWidgets.QAction("Database Settings", self)
        database_settings_action.triggered.connect(self.show_database_settings)
        database_menu.addAction(database_settings_action)

    def show_database_settings(self):
        dlg = DatabaseSettingsFormHandler(parent=self)
        dlg.exec_()

    def setup_access_controls(self):
        """
        Disable or hide menu actions/pages based on user_record flags.
        The keys in 'permissions' must match those in user_record.
        """
        permissions = {
            "settings": "actionSetting",
            "search": "actionSearch",
            "user_mgmt_page": "actionUserManagement",
        }
        for perm_key, action_name in permissions.items():
            if not getattr(self.user_record, perm_key, False):
                if hasattr(self.form_obj, action_name):
                    getattr(self.form_obj, action_name).setEnabled(False)
                else:
                    print(f"Warning: '{action_name}' not found in MainForm UI.")

    def connect_menu_actions(self):
        """
        Connect menu actions and check permissions if necessary.
        """
        if hasattr(self.form_obj, "actionSetting"):
            self.form_obj.actionSetting.triggered.connect(self.handle_settings)
        else:
            print("Warning: 'actionSetting' not found in the MainForm UI.")

    def handle_settings(self):
        print(f"Handling settings with user_record: {self.user_record}")
        if getattr(self.user_record, 'settings', False):
            self.settings_handler = SettingFormHandler()
            self.settings_handler.show()
        else:
            QMessageBox.critical(self, "Access Denied", "You don't have permission to access Settings.")

    def set_connections(self):
        self.actionExit.triggered.connect(self.close)
        self.actionCycle_Info.triggered.connect(self._show_cycle_info)
        self.actionPlot.triggered.connect(self._show_plot)
        self.actionSetting.triggered.connect(self.handle_settings)
        self.actionStart.triggered.connect(self._start)
        self.actionStart.triggered.connect(lambda: self.actionPlot_preview.setEnabled(False))
        self.actionStop.triggered.connect(self._stop)
        self.actionPlot_preview.triggered.connect(self.show_plot_preview)
        self.actionPrint_results.triggered.connect(self.open_pdf)
        self.cycle_timer.timeout.connect(self.cycle_timer_update)
        self.update_status_bar_signal.connect(self.update_status_bar)
        if not hasattr(self, 'userMgmtAction'):
            self.userMgmtAction = QAction("User Management", self)
            self.userMgmtAction.triggered.connect(self.open_user_management)
            self.menuBar().addAction(self.userMgmtAction)

    def open_user_management(self):
        if getattr(self.user_record, 'user_mgmt_page', False):
            dlg = UserManagementFormHandler(self)
            dlg.exec_()
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Access denied. Only admin can manage users.")

    def display_username(self):
        self.username_label = QLabel(f"Logged in as: {self.username}")
        self.statusBar().addPermanentWidget(self.username_label)
        self.setWindowTitle(f"Main Form - {self.username}")
    def create_stack(self):
        # initialize data stack: [[process_time(minutes)], [v1], [v2], ... , [V14], sampling_time,]
        data_stack = []
        test_data_stack = []
        for i in range(CHANNEL_COUNT + 2):
            data_stack.append([])
            test_data_stack.append([])
            self.data_stack = pool.set("data_stack", data_stack)
            self.test_data_stack = pool.set("test_data_stack", test_data_stack)
        pass
    def load_active_channels(self):
        self.active_channels = []
        for i in range(CHANNEL_COUNT):
            if pool.config('active' + str(i + 1), bool):
                self.active_channels.append(i + 1)
        return pool.set('active_channels', self.active_channels)
        pass
    def _start(self):

        self.create_stack()
        self.active_channels = self.load_active_channels()
        self.initialize_ui_panels()
        self.plot = self.create_plot(plot_layout=self.plotAreaLayout, legend_layout=self.formLayoutLegend)
        self.start_cycle_form.show()

    def _stop(self):
        self.start_cycle_form.stop_cycle()
        self.actionStart.setEnabled(True)
        self.actionStop.setEnabled(False)
        self.actionPrint_results.setEnabled(True)
        self.show_plot_preview()
        QTimer.singleShot(1000, self.close_csv_file)

    def show_plot_preview(self):
        self.plot_preview_form = pool.set('plot_preview_form', PlotPreviewFormHandler())
        self.plot_preview_form.initiate_plot(self.headers)

    def _print_result(self):
        pass

    def _show_cycle_info(self, checked):
        self.cycle_infoGroupBox.setVisible(checked)

    def _show_plot(self, checked):
        self.mainPlotGroupBox.setVisible(checked)

    def _save(self):
        pass

    def _save_as(self):
        pass

    def _show_setting_form(self):
        self.setting_form = SettingFormHandler()

    def _exit(self):
        pass

    def create_plot(self, plot_layout=None, legend_layout=None):

        self.plot_update_locked = False
        self.headers = list()
        self.headers.append(pool.config('h_label'))
        self.headers.append(pool.config('left_v_label'))
        self.headers.append(pool.config('right_v_label'))
        for i in range(1, CHANNEL_COUNT + 1):
            self.headers.append(pool.config('label' + str(i)))

        # Clear old plot if exists
        if plot_layout is not None:
            for i in reversed(range(plot_layout.count())):
                plot_layout.itemAt(i).widget().setParent(None)
        if legend_layout is not None:
            for i in reversed(range(legend_layout.count())):
                legend_layout.itemAt(i).widget().setParent(None)

        return InitiatePlotWidget(pool.get('active_channels'), plot_layout, legend_layout=legend_layout,
                                  headers=self.headers)

    def update_plot(self):
        if self.plot_update_locked:
            return
        self.plot_update_locked = True
        self.plot.update_plot()
        self.plot_update_locked = False

    def initialize_ui_panels(self):
        self.immediate_panel_update_locked = False
        active_channels = pool.get('active_channels')
        for i in range(CHANNEL_COUNT):

            getattr(self, 'chLabel' + str(i + 1)).setText(pool.config('label' + str(i + 1)))
            spin_widget = getattr(self, 'ch' + str(i + 1) + 'Value')
            if (i + 1) not in self.active_channels:
                spin_widget.setEnabled(False)
            else:
                spin_widget.setEnabled(True)
                decimal_value = pool.config('decimal_point' + str(i + 1), int, 2)
                spin_widget.setDecimals(decimal_value)
                spin_widget.setMinimum(-999999)
                spin_widget.setMaximum(+999999)

    def update_data(self):
        self.update_csv_file()
        QApplication.processEvents()
        self.update_immediate_values_panel()
        # QApplication.processEvents()
        self.update_plot()
        # QApplication.processEvents()

    def update_immediate_test_values_panel(self):
        for i in self.active_channels:
            spin_widget = getattr(self, 'ch' + str(i) + 'Value')
            if self.test_data_stack[i]:
                spin_widget.setValue(self.test_data_stack[i][-1])
            self.test_data_stack[i] = []

    def update_immediate_values_panel(self):
        if self.immediate_panel_update_locked:
            return
        self.immediate_panel_update_locked = True
        for i in range(CHANNEL_COUNT):
            spin_widget = getattr(self, 'ch' + str(i + 1) + 'Value')
            spin_widget.setValue(self.data_stack[i + 1][-1])
            self.o1.setText(str(self.start_cycle_form.core_temp_above_setpoint_time or 'N/A'))
            self.o2.setText(str(self.start_cycle_form.pressure_drop_core_temp or 'N/A'))
        self.immediate_panel_update_locked = False

    def cycle_timer_update(self):
        self.run_duration.setText(timedelta2str(datetime.now() - self.start_cycle_form.cycle_start_time))
        self.d6.setText(datetime.now().strftime("%H:%M:%S"))  # Cycle end time

    def update_cycle_info_pannel(self):
        self.d1.setText(pool.config("cycle_id"))
        self.d2.setText(pool.config("order_id"))
        self.d3.setText(pool.config("quantity"))
        self.d4.setText(self.start_cycle_form.cycle_start_time.strftime("%Y/%m/%d"))
        self.d5.setText(self.start_cycle_form.cycle_start_time.strftime("%H:%M:%S"))
        self.d7.setText(pool.config("cycle_location"))
        self.p1.setText(pool.config("maintain_vacuum"))
        self.p2.setText(pool.config("initial_set_cure_temp"))
        self.p3.setText(pool.config("temp_ramp"))
        self.p4.setText(pool.config("set_pressure"))
        self.p5.setText(pool.config("dwell_time"))
        self.p6.setText(pool.config("cool_down_temp"))
        self.cH1Label_36.setText(f"TIME (min) CORE TEMP ≥ {pool.config('core_temp_setpoint')} °C:")

    def create_csv_file(self):
        self.csv_update_locked = False
        self.last_written_index = 0
        file_extension = '.csv'
        csv_full_path = os.path.join(self.start_cycle_form.folder_path,
                                     self.start_cycle_form.file_name + file_extension)
        self.csv_path = csv_full_path
        delimiter = pool.config('csv_delimiter') or ' '
        csv.register_dialect('unixpwd', delimiter=delimiter)
        self.open_csv_file(mode='w')
        self.write_cycle_info_to_csv()

    def open_csv_file(self, mode='a'):
        self.csv_file = open(self.csv_path, mode, newline='')
        self.csv_writer = csv.writer(self.csv_file)

    def close_csv_file(self):
        self.csv_file.close()

    def write_cycle_info_to_csv(self):
        data = [
            ["Work Order", pool.config("order_id")],
            ["Cycle Number", pool.config("cycle_id")],
            ["Quantity", pool.config("quantity")],
            ["Process Start Time", self.start_cycle_form.cycle_start_time],
        ]
        self.csv_writer.writerows(data)
        self.csv_writer.writerows([['Date', 'Time', 'Timer(min)'] + self.headers[3:]])

    def update_csv_file(self):
        if self.csv_update_locked:
            return
        self.csv_update_locked = True
        n_data = len(self.data_stack[0])
        temp_data = []

        for i in range(self.last_written_index, n_data):
            temp_rec = []
            temp_rec.append(self.data_stack[15][i].strftime("%Y/%m/%d"))
            temp_rec.append(self.data_stack[15][i].strftime("%H:%M:%S"))
            temp_rec.append(self.data_stack[0][i])
            for j in range(CHANNEL_COUNT):
                temp_rec.append(self.data_stack[j + 1][i])
            temp_data.append(temp_rec)
        self.csv_writer.writerows(temp_data)
        self.last_written_index = n_data
        self.csv_file.flush()
        self.csv_update_locked = False

    def show_error_and_stop(self, msg, parent=None):
        error_dialog = QErrorMessage(parent or self)
        error_dialog.showMessage(msg)
        self.start_cycle_form.stop_cycle()
        self.actionStart.setEnabled(True)
        self.actionStop.setEnabled(False)
        self.csv_file.close()

    def generate_html_report(self, image_path=None):
        report_data = {
            "order_id": pool.config("order_id") or "-",
            "cycle_id": pool.config("cycle_id") or "-",
            "quantity": pool.config("quantity") or "-",
            "cycle_location": pool.config("cycle_location") or "-",
            "dwell_time": int(pool.config("dwell_time")) or "-",
            "cool_down_temp": pool.config("cool_down_temp") or "-",
            "core_temp_setpoint": pool.config("core_temp_setpoint") or "-",
            "temp_ramp": pool.config("temp_ramp") or "-",
            "set_pressure": pool.config("set_pressure") or "-",
            "maintain_vacuum": pool.config("maintain_vacuum") or "-",
            "initial_set_cure_temp": pool.config("initial_set_cure_temp") or "-",
            "final_set_cure_temp": pool.config("final_set_cure_temp") or "-",
            "core_high_temp_time": round(self.start_cycle_form.core_temp_above_setpoint_time, 2) or "-",
            "release_temp": self.start_cycle_form.pressure_drop_core_temp or "-",
            "cycle_date": self.start_cycle_form.cycle_start_time.strftime("%Y/%m/%d") or "-",
            "cycle_start_time": self.start_cycle_form.cycle_start_time.strftime("%H:%M:%S") or "-",
            "cycle_end_time": self.start_cycle_form.cycle_end_time.strftime("%H:%M:%S") or "-",
            "image_path": image_path,
            "logo_path": os.path.join(os.getcwd(), 'ui\\logo.jpg'),
        }

        self.render_print_template(template_file='result_template.html',
                                   data=report_data,
                                   )

    def render_print_template(self, *args, template_file=None, **kwargs):
        templateLoader = jinja2.FileSystemLoader(searchpath=os.path.join(os.getcwd(), "ui"))
        templateEnv = jinja2.Environment(loader=templateLoader, extensions=['jinja2.ext.loopcontrols'])
        template = templateEnv.get_template(template_file)
        html = template.render(**kwargs)
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html') as f:
            fname = f.name
            f.write(html)
        file_extension = '.pdf'
        pdf_full_path = os.path.join(self.start_cycle_form.folder_path,
                                     self.start_cycle_form.file_name + file_extension)
        self.html2pdf(fname, pdf_full_path)

    def html2pdf(self, html_path, pdf_path):
        self.pdf_path = pdf_path
        options = {
            'page-size': 'A4',
            'dpi': 2000,
            'margin-top': '0.35in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None
        }
        path_wkhtmltopdf = os.path.join(os.getcwd(), 'wkhtmltopdf.exe')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        with open(html_path) as f:
            pdfkit.from_file(f, pdf_path, options=options, configuration=config)
        webbrowser.open('file://' + pdf_path)

    def open_pdf(self):
        webbrowser.open('file://' + self.pdf_path)

    def test_onedrive_connection(self):
        msg = QMessageBox()
        try:
            onedrive_api = OneDriveAPI()
            onedrive_api.authenticate(
                pool.config('onedrive_client_id'),
                pool.config('onedrive_client_secret'),
                pool.config('onedrive_tenant_id')
            )
            if onedrive_api.check_connection():
                msg.setIcon(QMessageBox.Information)
                msg.setText("OneDrive connection OK.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()
                self.update_status_bar_signal.emit('OneDrive connection OK.', 15000, 'green')
            else:
                raise Exception("Connection failed")
        except Exception as e:
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Connection failed.\n" + str(e))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            self.update_status_bar_signal.emit('OneDrive connection failed.', 0, 'red')

    def _sync_onedrive(self, *args, upload_csv=True, upload_pdf=True, show_message=True, delete_existing=True):
        try:
            # Check if settings are configured
            client_id = pool.config("onedrive_client_id")
            client_secret = pool.config("onedrive_client_secret")
            tenant_id = pool.config("onedrive_tenant_id")
            
            if not all([client_id, client_secret, tenant_id]):
                if show_message:
                    QMessageBox.warning(self, "OneDrive Not Configured", 
                                    "Please configure OneDrive settings first.")
                return False
                
            # Create OneDrive API instance
            onedrive_api = OneDriveAPI()
            onedrive_api.authenticate(client_id, client_secret, tenant_id)
            
            # Create folder for reports
            folder_name = f"PLC_Reports_{datetime.now().strftime('%Y-%m-%d')}"
            try:
                folder_response = onedrive_api.create_folder(folder_name)
                folder_id = folder_response.get('id')
                # Use logger instead of print for consistent logging
                logger.info(f"Created OneDrive folder: {folder_name}")
            except Exception as e:
                logger.warning(f"Could not create OneDrive folder: {e}")
                folder_id = None
                
            # Upload CSV file if requested
            if upload_csv:
                csv_file_path = self.csv_path
                if csv_file_path and os.path.exists(csv_file_path):  # Added null check
                    file_resp = onedrive_api.upload_file(csv_file_path, folder_id)
                    logger.info(f"CSV uploaded to OneDrive: {os.path.basename(csv_file_path)}")
                    self.update_status_bar_signal.emit(f"CSV uploaded to OneDrive", 10000, 'green')
            
            # Upload PDF file if requested
            if upload_pdf:
                pdf_file_path = self.pdf_path
                if pdf_file_path and os.path.exists(pdf_file_path):  # Added null check
                    file_resp = onedrive_api.upload_file(pdf_file_path, folder_id)
                    logger.info(f"PDF uploaded to OneDrive: {os.path.basename(pdf_file_path)}")
                    self.update_status_bar_signal.emit(f"PDF uploaded to OneDrive", 10000, 'green')
            
            if show_message:
                QMessageBox.information(self, "Success", "Files uploaded to OneDrive successfully")
            return True
            
        except Exception as e:
            logger.error(f"OneDrive upload failed: {e}")
            if show_message:
                QMessageBox.critical(self, "Error", f"OneDrive upload failed: {str(e)}")
            else:
                self.update_status_bar_signal.emit(f"OneDrive upload failed: {str(e)}", 5000, 'red')
            return False

    def closeEvent(self, event):
        if hasattr(self, 'start_cycle_form') \
                and hasattr(self.start_cycle_form, 'running') \
                and self.start_cycle_form.running:
            quit_msg = "Are you Sure?\nCSV data may be not be saved."
        else:
            quit_msg = "Are you sure?"
        reply = QMessageBox.question(self, 'Exiting app ...',
                                     quit_msg, (QMessageBox.Yes | QMessageBox.Cancel))
        if reply == QMessageBox.Yes:
            event.accept()
        elif reply == QMessageBox.Cancel:
            event.ignore()

    def update_status_bar(self, msg, ms_timeout, color):
        self.statusbar.showMessage(msg, ms_timeout)
        self.statusbar.setStyleSheet("color: {}".format(color.lower()))
        self.statusBar().setFont(QFont('Times', 12))
    
    def update_connection_status_display(self):
        """Update the UI to show current connection status and type"""
        # Check if we're in demo/simulation mode
        is_demo = pool.config('demo', bool, False)
        is_simulation = pool.config('plc/simulation_mode', bool, False)
        connection_type = pool.config('plc/connection_type', str, 'rtu')
        
        # Create or update the connection type label in the status bar
        if not hasattr(self, 'connectionTypeLabel'):
            self.connectionTypeLabel = QLabel()
            self.statusbar.addPermanentWidget(self.connectionTypeLabel)
        
        # Update the label with the current connection type
        if connection_type == 'tcp':
            host = pool.config('plc/host', str, 'Not Set')
            port = pool.config('plc/tcp_port', int, 502)
            self.connectionTypeLabel.setText(f"TCP: {host}:{port}")
            self.connectionTypeLabel.setStyleSheet("color: blue;")
        else:
            port = pool.config('plc/port', str, 'Not Set')
            self.connectionTypeLabel.setText(f"RTU: {port}")
            self.connectionTypeLabel.setStyleSheet("color: green;")
        
        # Update status bar with enhanced information and colors
        if is_demo:
            self.statusbar.showMessage("DEMO MODE - No real PLC connection", 0)  # 0 = show permanently
            self.statusbar.setStyleSheet("background-color: #FFF2CC; color: #9C6500;")
        elif is_simulation:
            self.statusbar.showMessage("SIMULATION MODE - No real PLC connection", 0)
            self.statusbar.setStyleSheet("background-color: #FFF2CC; color: #9C6500;")
        else:
            # Only check real connection status if not in simulation mode
            try:
                is_connected = plc_communication.is_connected()
                if is_connected:
                    self.statusbar.showMessage("Connected to PLC", 5000)
                    self.statusbar.setStyleSheet("background-color: #D5F5E3; color: #196F3D;")
                else:
                    self.statusbar.showMessage("Not connected to PLC - Check settings", 0)
                    self.statusbar.setStyleSheet("background-color: #FADBD8; color: #943126;")
            except Exception as e:
                self.statusbar.showMessage(f"Error checking connection: {str(e)}", 0)
                self.statusbar.setStyleSheet("background-color: #FADBD8; color: #943126;")