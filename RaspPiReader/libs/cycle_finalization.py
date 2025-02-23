import os
import csv
import datetime
import pdfkit
from jinja2 import Template
from RaspPiReader.libs.plc_communication import write_bool_address
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from RaspPiReader import pool
from RaspPiReader.libs.database import Database

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
         supervisor_username: if duplicate override occurred, the supervisor’s username (string), else None.
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
    db_alarms = db.session.query(db.session.query(db.session.bind.class_.Alarm).subquery()).all()
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
        # For each alarm in the DB, use its string address and text.
        for alarm in db.session.query(db.session.bind.class_.Alarm).all():
            alarm_mapping[str(alarm.address)] = alarm.alarm_text

    active_alarms = []
    for addr, value in alarm_values.items():
        if int(value) == 1:
            text = alarm_mapping.get(str(addr), f"Unknown Alarm at {addr}")
            active_alarms.append(text)
    alarm_info = ", ".join(active_alarms) if active_alarms else "None"

    # --- 3. Load the HTML template and render report ---
    if not os.path.exists(template_file):
        raise FileNotFoundError(f"Template file not found: {template_file}")
    with open(template_file, "r", encoding="utf-8") as f:
        template_content = f.read()
    template = Template(template_content)
    html_output = template.render(
        order_id = cycle_data.get("order_id", "N/A"),
        program = cycle_data.get("program", "N/A"),
        start_time = cycle_data.get("start_time", "N/A"),
        stop_time = cycle_data.get("stop_time", "N/A"),
        supervisor_username = supervisor_username if supervisor_username else "No",
        alarm_info = alarm_info,
        serial_numbers = serial_numbers
    )

    # --- 4. Save PDF and CSV reports locally ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if not os.path.exists(reports_folder):
        os.makedirs(reports_folder)
    pdf_filename = os.path.join(reports_folder, f"CycleReport_{timestamp}.pdf")
    csv_filename = os.path.join(reports_folder, f"CycleReport_{timestamp}.csv")
    pdfkit.from_string(html_output, pdf_filename)
    
    with open(csv_filename, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Serial Number"])
        for sn in serial_numbers:
            writer.writerow([sn])

    # --- 5. Upload reports to OneDrive using dynamic settings ---
    od_api = OneDriveAPI()
    client_id = pool.config("onedrive_client_id", str, "")
    client_secret = pool.config("onedrive_client_secret", str, "")
    tenant_id = pool.config("onedrive_tenant_id", str, "")
    if od_api.authenticate(client_id, client_secret, tenant_id):
        parent_folder_id = pool.config("onedrive_folder_id", str, "DEFAULT_FOLDER_ID")
        if od_api.upload_file(pdf_filename, folder_id=parent_folder_id):
            print(f"Uploaded PDF: {pdf_filename}")
        if od_api.upload_file(csv_filename, folder_id=parent_folder_id):
            print(f"Uploaded CSV: {csv_filename}")
    else:
        print("OneDrive authentication failed; skipping upload.")

    return pdf_filename, csv_filename