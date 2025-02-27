import os
import csv
import logging
import pdfkit
from jinja2 import Template
from datetime import datetime
from RaspPiReader.libs.plc_communication import write_bool_address
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from RaspPiReader import pool
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, OneDriveSettings

logger = logging.getLogger(__name__)

def finalize_cycle(cycle_data, serial_numbers, supervisor_username=None, alarm_values={}, 
                   reports_folder="reports", template_file="RaspPiReader/ui/result_template.html"):
    """
    Finalizes a cycle:
      - Writes a false (stop) signal to a designated Boolean address (from dynamic config).
      - Evaluates alarm conditions (reads live alarm values and matches with texts stored in the Alarm table).
      - Generates a PDF report (using a Jinja2 HTML template) and a CSV file listing the serial numbers.
      - Uploads the generated reports to OneDrive.
      
    Parameters:
         cycle_data         : dict with keys like order_id, program, start_time, stop_time
         serial_numbers     : list of serial numbers (strings; duplicates allowed if overridden, e.g., "12345R")
         supervisor_username: if duplicate override occurred, the supervisor's username (string), else None.
         alarm_values       : dict mapping alarm addresses (e.g. 100) to integer values (0 or 1)
         reports_folder     : local folder to store the reports
         template_file      : file path to the HTML template (result_template.html)
         
    Returns:
         (pdf_filename, csv_filename)
    """
    # --- 1. Write the stop signal (use dynamic config from pool) ---
    stop_bool_addr = pool.config("cycle_stop_bool", int, 1101)
    # Write False to indicate cycle stop
    write_bool_address(stop_bool_addr, 0)
    
    # --- 2. Evaluate alarm conditions ---
    # Load alarm texts from the database (if defined) or use fallback mapping.
    db = Database("sqlite:///local_database.db")
    alarm_mapping = {}
    db_alarms = db.session.query(Alarm).all()
    # If no alarms are in the DB, use fallback hard-coded mapping:
    if not db_alarms:
        alarm_mapping = {
            "100": "Temperature High Alarm",
            "101": "Temperature Low Alarm",
            "102": "Pressure High Alarm",
            "103": "Pressure Low Alarm",
            "104": "Voltage High Alarm",
            "105": "Voltage Low Alarm",
            "106": "Flow High Alarm",
            "107": "Flow Low Alarm",
        }
    else:
        for alarm in db_alarms:
            alarm_mapping[str(alarm.address)] = alarm.alarm_text

    active_alarms = []
    for addr, value in alarm_values.items():
        if int(value) == 1:
            text = alarm_mapping.get(str(addr), f"Unknown Alarm at {addr}")
            active_alarms.append(text)
    alarm_info = ", ".join(active_alarms) if active_alarms else "None"

    # --- 3. Create reports directory if it doesn't exist ---
    if not os.path.exists(reports_folder):
        os.makedirs(reports_folder)
    
    # --- 4. Generate filenames with timestamps ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    order_id = cycle_data.order_id if hasattr(cycle_data, 'order_id') else "unknown"
    
    base_filename = f"{order_id}_{timestamp}"
    csv_filename = f"{base_filename}.csv"
    pdf_filename = f"{base_filename}.pdf"
    
    csv_path = os.path.join(reports_folder, csv_filename)
    pdf_path = os.path.join(reports_folder, pdf_filename)
    
    # --- 5. Generate CSV report with serial numbers ---
    generate_csv_report(serial_numbers, csv_path)
    logger.info(f"CSV report generated: {csv_path}")
    
    # --- 6. Generate PDF report ---
    try:
        # Load the HTML template
        with open(template_file, 'r', encoding='utf-8') as file:
            template_content = file.read()
        
        template = Template(template_content)
        
        # Format cycle data for report
        cycle_start_time = cycle_data.start_time if hasattr(cycle_data, 'start_time') else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cycle_end_time = cycle_data.stop_time if hasattr(cycle_data, 'stop_time') else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format serial numbers as comma-separated list
        serial_list = ", ".join(serial_numbers)
        
        # Format replacement values for template
        report_data = {
            'data': {
                'order_id': cycle_data.order_id if hasattr(cycle_data, 'order_id') else "N/A",
                'cycle_id': cycle_data.cycle_id if hasattr(cycle_data, 'cycle_id') else "N/A",
                'quantity': cycle_data.quantity if hasattr(cycle_data, 'quantity') else len(serial_numbers),
                'size': cycle_data.size if hasattr(cycle_data, 'size') else "N/A",
                'serial_numbers': serial_list,
                'cycle_location': cycle_data.cycle_location if hasattr(cycle_data, 'cycle_location') else "N/A",
                'start_time': cycle_start_time,
                'end_time': cycle_end_time,
                'dwell_time': cycle_data.dwell_time if hasattr(cycle_data, 'dwell_time') else "N/A",
                'cool_down_temp': cycle_data.cool_down_temp if hasattr(cycle_data, 'cool_down_temp') else "N/A",
                'core_temp_setpoint': cycle_data.core_temp_setpoint if hasattr(cycle_data, 'core_temp_setpoint') else "N/A",
                'temp_ramp': cycle_data.temp_ramp if hasattr(cycle_data, 'temp_ramp') else "N/A",
                'set_pressure': cycle_data.set_pressure if hasattr(cycle_data, 'set_pressure') else "N/A",
                'maintain_vacuum': "Yes" if (hasattr(cycle_data, 'maintain_vacuum') and cycle_data.maintain_vacuum) else "No",
                'initial_set_cure_temp': cycle_data.initial_set_cure_temp if hasattr(cycle_data, 'initial_set_cure_temp') else "N/A",
                'final_set_cure_temp': cycle_data.final_set_cure_temp if hasattr(cycle_data, 'final_set_cure_temp') else "N/A",
                'alarms': alarm_info,
                'supervisor': supervisor_username if supervisor_username else "N/A",
                'current_date': datetime.now().strftime("%Y-%m-%d"),
                'generation_time': datetime.now().strftime("%H:%M:%S")
            }
        }
        
        # Render HTML content
        html_content = template.render(**report_data)
        
        # Convert HTML to PDF
        options = {
            'page-size': 'A4',
            'encoding': "UTF-8",
            'enable-local-file-access': None
        }
        
        # Find wkhtmltopdf executable path
        path_wkhtmltopdf = os.path.join(os.getcwd(), 'wkhtmltopdf.exe')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        
        # Generate PDF
        pdfkit.from_string(html_content, pdf_path, options=options, configuration=config)
        logger.info(f"PDF report generated: {pdf_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        # Create a simple text file as fallback
        with open(pdf_path.replace('.pdf', '.txt'), 'w', encoding='utf-8') as file:
            file.write(f"Report for {order_id} (fallback due to PDF generation failure)\n")
            for key, value in report_data['data'].items():
                file.write(f"{key}: {value}\n")
    
    # --- 7. Upload reports to OneDrive ---
    upload_to_onedrive(csv_path, pdf_path)
    
    return (pdf_filename, csv_filename)

def generate_csv_report(serial_numbers, filepath):
    """Generate a CSV file with serial numbers"""
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Serial Numbers'])
        for sn in serial_numbers:
            writer.writerow([sn])

def upload_to_onedrive(csv_path, pdf_path):
    """Upload reports to OneDrive"""
    try:
        # Get OneDrive credentials from database
        db = Database("sqlite:///local_database.db")
        settings = db.session.query(OneDriveSettings).first()
        
        if not settings or not all([settings.client_id, settings.client_secret, settings.tenant_id]):
            logger.warning("OneDrive settings not properly configured. Files saved locally only.")
            return False
        
        # Initialize OneDrive API and authenticate
        onedrive = OneDriveAPI()
        onedrive.authenticate(settings.client_id, settings.client_secret, settings.tenant_id)
        
        # Create a folder for reports using current date
        folder_name = f"PLC_Reports_{datetime.now().strftime('%Y-%m-%d')}"
        try:
            folder_response = onedrive.create_folder(folder_name)
            folder_id = folder_response.get('id')
            logger.info(f"Created OneDrive folder: {folder_name}")
        except Exception as e:
            logger.warning(f"Could not create OneDrive folder: {e}")
            folder_id = None  # Upload to root if folder creation fails
        
        # Upload CSV file
        if os.path.exists(csv_path):
            try:
                csv_response = onedrive.upload_file(csv_path, folder_id)
                csv_id = csv_response.get('id')
                logger.info(f"CSV uploaded to OneDrive: {os.path.basename(csv_path)}")
            except Exception as e:
                logger.error(f"Failed to upload CSV to OneDrive: {e}")
        
        # Upload PDF file
        if os.path.exists(pdf_path):
            try:
                pdf_response = onedrive.upload_file(pdf_path, folder_id)
                pdf_id = pdf_response.get('id')
                logger.info(f"PDF uploaded to OneDrive: {os.path.basename(pdf_path)}")
            except Exception as e:
                logger.error(f"Failed to upload PDF to OneDrive: {e}")
        
        return True
    
    except Exception as e:
        logger.error(f"OneDrive upload process failed: {e}")
        return False