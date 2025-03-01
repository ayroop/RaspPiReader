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

def convert_to_int(val):
    """
    Convert the input val to an integer.
    If val is the string "high", return 1; if "low", return 0.
    Otherwise, try to convert using int(val); if that fails, raise a ValueError.
    """
    try:
        return int(val)
    except ValueError:
        if isinstance(val, str):
            mapping = {"high": 1, "low": 0}
            lower_val = val.strip().lower()
            if lower_val in mapping:
                return mapping[lower_val]
        raise ValueError(f"Cannot convert {val} to an integer.")

def generate_csv_report(serial_numbers, filepath):
    """Generate a CSV file with serial numbers."""
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Serial Numbers'])
            for sn in serial_numbers:
                writer.writerow([sn])
        logger.info(f"CSV report generated successfully at {filepath}")
    except Exception as e:
        logger.error(f"Error generating CSV report: {e}")
        raise

def upload_to_onedrive(csv_path, pdf_path):
    """Upload reports to OneDrive."""
    try:
        db = Database("sqlite:///local_database.db")
        settings = db.session.query(OneDriveSettings).first()

        if not settings or not all([settings.client_id, settings.client_secret, settings.tenant_id]):
            logger.warning("OneDrive settings not properly configured. Files saved locally only.")
            return False

        onedrive = OneDriveAPI()
        onedrive.authenticate(settings.client_id, settings.client_secret, settings.tenant_id)

        # Create a folder in OneDrive using the current date.
        folder_name = f"PLC_Reports_{datetime.now().strftime('%Y-%m-%d')}"
        try:
            folder_response = onedrive.create_folder(folder_name)
            folder_id = folder_response.get('id')
            logger.info(f"Created OneDrive folder: {folder_name}")
        except Exception as e:
            logger.warning(f"Could not create OneDrive folder, uploading to root instead: {e}")
            folder_id = None  # Upload to the root of OneDrive if folder creation fails

        # Upload CSV file.
        if os.path.exists(csv_path):
            try:
                csv_response = onedrive.upload_file(csv_path, folder_id)
                csv_id = csv_response.get('id')
                logger.info(f"CSV uploaded to OneDrive: {os.path.basename(csv_path)}")
            except Exception as e:
                logger.error(f"Failed to upload CSV to OneDrive: {e}")

        # Upload PDF file.
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

def finalize_cycle(cycle_data, serial_numbers, supervisor_username=None, alarm_values={}, 
                   reports_folder="reports", template_file="RaspPiReader/ui/result_template.html"):
    """
    Finalizes a cycle:
      - Writes a false (stop) signal to a designated Boolean address.
      - Evaluates alarm conditions by matching live alarm values with texts from the Alarm table.
      - Generates a PDF report using a Jinja2 HTML template and a CSV report listing the serial numbers.
      - Uploads the generated reports to OneDrive.
      
    Parameters:
         cycle_data         : Object with attributes (order_id, cycle_id, start_time, stop_time, etc.)
         serial_numbers     : List of serial numbers (strings)
         supervisor_username: Supervisor username if applicable, else None.
         alarm_values       : Dict mapping alarm addresses to values (integer or "high"/"low")
         reports_folder     : Local folder (relative to project root) to store the reports.
         template_file      : Path to the HTML template file.
         
    Returns:
         (pdf_filename, csv_filename)
    """
    # --- 1. Write the stop signal to PLC ---
    stop_bool_addr = pool.config("cycle_stop_bool", int, 1101)
    write_bool_address(stop_bool_addr, 0)
    
    # --- 2. Evaluate alarm conditions ---
    db = Database("sqlite:///local_database.db")
    alarm_mapping = {}
    db_alarms = db.session.query(Alarm).all()
    if not db_alarms:
        # Fallback hard-coded mapping if no alarms are stored in the database.
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
        try:
            numeric_value = convert_to_int(value)
            if numeric_value == 1:
                text = alarm_mapping.get(str(addr), f"Unknown Alarm at {addr}")
                active_alarms.append(text)
        except Exception as e:
            logger.error(f"Error converting alarm value for address {addr}: {e}")
    alarm_info = ", ".join(active_alarms) if active_alarms else "None"

    # --- 3. Create reports directory (absolute path) ---
    reports_dir = os.path.join(os.getcwd(), "reports")  # Use just one "reports" folder
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    # --- 4. Generate filenames with timestamps ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    order_id = cycle_data.order_id if hasattr(cycle_data, 'order_id') else "unknown"
    base_filename = f"{order_id}_{timestamp}"
    csv_filename = f"{base_filename}.csv"
    pdf_filename = f"{base_filename}.pdf"
    
    csv_path = os.path.join(reports_dir, csv_filename)
    pdf_path = os.path.join(reports_dir, pdf_filename)
    
    # --- 5. Generate CSV report with serial numbers ---
    try:
        generate_csv_report(serial_numbers, csv_path)
        logger.info(f"CSV report generated: {csv_path}")
    except Exception as e:
        logger.error(f"Error generating CSV report: {e}")
        raise

    # --- 6. Generate PDF report ---
    try:
        with open(template_file, 'r', encoding='utf-8') as file:
            template_content = file.read()
        
        template = Template(template_content)
        cycle_start_time = cycle_data.start_time if hasattr(cycle_data, 'start_time') else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cycle_end_time = cycle_data.stop_time if hasattr(cycle_data, 'stop_time') else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        serial_list = ", ".join(serial_numbers)
        
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
        
        html_content = template.render(**report_data)
        
        options = {
            'page-size': 'A4',
            'encoding': "UTF-8",
            'enable-local-file-access': ""
        }
        
        # Locate wkhtmltopdf executable (assumed to be in the project root)
        path_wkhtmltopdf = os.path.join(os.getcwd(), 'wkhtmltopdf.exe')
        config_pdfkit = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        
        pdfkit.from_string(html_content, pdf_path, options=options, configuration=config_pdfkit)
        logger.info(f"PDF report generated: {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        fallback_path = pdf_path.replace('.pdf', '.txt')
        try:
            with open(fallback_path, 'w', encoding='utf-8') as file:
                file.write(f"Report for {order_id} (fallback due to PDF generation failure)\n")
                for key, value in report_data['data'].items():
                    file.write(f"{key}: {value}\n")
            logger.info(f"Fallback text report generated: {fallback_path}")
        except Exception as ex:
            logger.error(f"Failed to generate fallback report: {ex}")
    
    # --- 7. Upload reports to OneDrive ---
    try:
        upload_to_onedrive(csv_path, pdf_path)
    except Exception as e:
        logger.error(f"Error during OneDrive upload: {e}")
    
    return (pdf_filename, csv_filename)