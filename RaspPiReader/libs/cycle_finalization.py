import os
import csv
import logging
import pdfkit
import webbrowser
from jinja2 import Template
from datetime import datetime
from RaspPiReader.libs.plc_communication import write_bool_address
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from RaspPiReader import pool
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, OneDriveSettings, CycleSerialNumber, CycleData, CycleReport
import sqlalchemy.exc

logger = logging.getLogger(__name__)


def convert_to_int(val):
    try:
        return int(val)
    except ValueError:
        if isinstance(val, str):
            mapping = {"high": 1, "low": 0}
            lower_val = val.strip().lower()
            if lower_val in mapping:
                return mapping[lower_val]
        raise ValueError(f"Cannot convert {val} to an integer.")


def generate_csv_report(serial_numbers, filepath, cycle_data=None):
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Add cycle data information if available
            if cycle_data:
                writer.writerow(['Cycle Information'])
                writer.writerow(['Order ID', getattr(cycle_data, 'order_id', "N/A")])
                writer.writerow(['Cycle ID', getattr(cycle_data, 'cycle_id', "N/A")])
                writer.writerow(['Start Time', getattr(cycle_data, 'start_time', "N/A")])
                writer.writerow(['End Time', getattr(cycle_data, 'stop_time', "N/A")])
                writer.writerow([])
            writer.writerow(['Serial Numbers'])
            valid_serials = [sn for sn in serial_numbers if sn and not str(sn).startswith("PLACEHOLDER_")]
            if not valid_serials:
                writer.writerow(["No serial numbers recorded"])
            else:
                for sn in valid_serials:
                    writer.writerow([sn])
        logger.info(f"CSV report generated successfully at {filepath}")
    except Exception as e:
        logger.error(f"Error generating CSV report: {e}")
        # Generate fallback report
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Error generating complete report'])
                writer.writerow([f'Error: {str(e)}'])
                writer.writerow(['Serial Numbers (partial)'])
                for sn in serial_numbers[:5]:
                    if sn:
                        writer.writerow([sn])
        except Exception as fallback_error:
            logger.error(f"Even fallback CSV report failed: {fallback_error}")


def upload_to_onedrive(csv_path, pdf_path):
    try:
        db = Database("sqlite:///local_database.db")
        settings = db.session.query(OneDriveSettings).first()
        if not settings or not all([settings.client_id, settings.client_secret, settings.tenant_id]):
            logger.warning("OneDrive settings not properly configured. Files saved locally only.")
            return False
        onedrive = OneDriveAPI()
        onedrive.authenticate(settings.client_id, settings.client_secret, settings.tenant_id)
        folder_name = f"PLC_Reports_{datetime.now().strftime('%Y-%m-%d')}"
        try:
            folder_response = onedrive.create_folder(folder_name)
            folder_id = folder_response.get('id')
            logger.info(f"Created OneDrive folder: {folder_name}")
        except Exception as e:
            logger.warning(f"Could not create OneDrive folder, uploading to root instead: {e}")
            folder_id = None
        if os.path.exists(csv_path):
            try:
                onedrive.upload_file(csv_path, folder_id)
                logger.info(f"CSV uploaded to OneDrive: {os.path.basename(csv_path)}")
            except Exception as e:
                logger.error(f"Failed to upload CSV to OneDrive: {e}")
        if os.path.exists(pdf_path):
            try:
                onedrive.upload_file(pdf_path, folder_id)
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
    Finalize a cycle by generating reports and storing cycle data.

    Args:
        cycle_data: The cycle data object
        serial_numbers: List of serial numbers to associate with this cycle
        supervisor_username: Optional supervisor name for the report
        alarm_values: Dictionary of alarm values
        reports_folder: Folder to store reports
        template_file: HTML template for report generation

    Returns:
        Tuple of (pdf_filename, csv_filename)
    """
    # Verify cycle_data has a valid ID
    if not hasattr(cycle_data, 'id') or not cycle_data.id:
        logger.error("Cannot finalize cycle: cycle_data has no valid ID")
        return (None, None)
    
    cycle_id = cycle_data.id
    logger.info(f"Finalizing cycle with ID: {cycle_id}")
    # Write to the PLC coil to signal end-of-cycle.
    stop_bool_addr = pool.config("cycle_stop_bool", int, default_val=1101)
    try:
        write_bool_address(stop_bool_addr, 0)
    except Exception as e:
        logger.error(f"Error writing to coil: {e}")
    # Ensure we write zero again
    write_bool_address(stop_bool_addr, 0)

    db = Database("sqlite:///local_database.db")
    # Build alarm mapping from DB or use defaults.
    alarm_mapping = {}
    db_alarms = db.session.query(Alarm).all()
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
        try:
            numeric_value = convert_to_int(value)
            if numeric_value == 1:
                text = alarm_mapping.get(str(addr), f"Unknown Alarm at {addr}")
                active_alarms.append(text)
        except Exception as e:
            logger.error(f"Error converting alarm value for address {addr}: {e}")
    alarm_info = ", ".join(active_alarms) if active_alarms else "None"

    # Ensure the reports folder exists.
    reports_dir = os.path.join(os.getcwd(), reports_folder)
    os.makedirs(reports_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Determine a unique cycle identifier: prefer cycle_data.cycle_id if provided.
    cycle_number = getattr(cycle_data, 'cycle_id', None)
    if not cycle_number or not str(cycle_number).strip():
        cycle_number = getattr(cycle_data, 'order_id', "unknown")
    cycle_number = str(cycle_number).strip()
    base_filename = f"{cycle_number}_{timestamp}"
    csv_filename = f"{base_filename}.csv"
    pdf_filename = f"{base_filename}.pdf"
    html_filename = f"{base_filename}.html"
    csv_path = os.path.join(reports_dir, csv_filename)
    pdf_path = os.path.join(reports_dir, pdf_filename)
    html_path = os.path.join(reports_dir, html_filename)

    try:
        generate_csv_report(serial_numbers, csv_path, cycle_data)
        logger.info(f"CSV report generated: {csv_path}")
    except Exception as e:
        logger.error(f"Error generating CSV report: {e}")
        raise

    # Process serial numbers to handle duplicates for display.
    final_serials = []
    counts = {}
    for sn in serial_numbers:
        if not sn:
            continue
        counts[sn] = counts.get(sn, 0) + 1
        final_serials.append(f"{sn}R" if counts[sn] > 1 else sn)

    # Retrieve stored serial numbers from the DB for consistency in the template.
    try:
        # Explicitly verify the cycle ID before proceeding
        cycle_id = getattr(cycle_data, 'id', None)
        if not cycle_id:
            logger.error("Cannot retrieve serial numbers: cycle_data has no valid ID")
            filtered_serials = [s for s in final_serials if s and not s.startswith("PLACEHOLDER_")]
            serial_list = ", ".join(filtered_serials) if filtered_serials else "No serial numbers recorded"
            logger.info(f"Using final_serials instead (no cycle ID): {serial_list}")
        else:
            stored_serials = db.session.query(CycleSerialNumber).filter(CycleSerialNumber.cycle_id == cycle_id).all()
            db_serial_list = [s.serial_number for s in stored_serials if s.serial_number and not s.serial_number.startswith("PLACEHOLDER_")]
            if not db_serial_list:
                serial_list = "No serial numbers recorded"
                logger.info(f"Only placeholder serial numbers found in DB for cycle {cycle_id}")
            else:
                serial_list = ", ".join(db_serial_list)
                logger.info(f"Retrieved serial numbers from DB for cycle {cycle_id}: {serial_list}")
    except Exception as e:
        logger.error(f"Error fetching stored cycle serial numbers: {e}")
        filtered_serials = [s for s in final_serials if s and not s.startswith("PLACEHOLDER_")]
        serial_list = ", ".join(filtered_serials) if filtered_serials else "No serial numbers recorded"
        logger.info(f"Using final_serials instead (due to error): {serial_list}")

    try:
        dwell_time = float(cycle_data.dwell_time) if hasattr(cycle_data, 'dwell_time') else 0.0
    except Exception:
        dwell_time = 0.0
    try:
        quantity = int(cycle_data.quantity) if hasattr(cycle_data, 'quantity') and str(cycle_data.quantity).isdigit() else len(serial_numbers)
    except Exception:
        quantity = len(serial_numbers)

    try:
        with open(template_file, 'r', encoding='utf-8') as file:
            template_content = file.read()
        template = Template(template_content)
        cycle_date = (cycle_data.start_time.strftime("%Y-%m-%d")
                      if hasattr(cycle_data, 'start_time') and cycle_data.start_time
                      else datetime.now().strftime("%Y-%m-%d"))
        cycle_start_time = (cycle_data.start_time.strftime("%H:%M:%S")
                            if hasattr(cycle_data, 'start_time') and cycle_data.start_time
                            else datetime.now().strftime("%H:%M:%S"))
        cycle_end_time = (cycle_data.stop_time.strftime("%H:%M:%S")
                          if hasattr(cycle_data, 'stop_time') and cycle_data.stop_time
                          else datetime.now().strftime("%H:%M:%S"))
        report_data = {
            'data': {
                'order_id': getattr(cycle_data, 'order_id', "N/A"),
                'cycle_id': getattr(cycle_data, 'cycle_id', "N/A"),
                'quantity': quantity,
                'size': getattr(cycle_data, 'size', "N/A"),
                'serial_numbers': serial_list,
                'cycle_location': getattr(cycle_data, 'cycle_location', "N/A"),
                'cycle_date': cycle_date,
                'cycle_start_time': cycle_start_time,
                'cycle_end_time': cycle_end_time,
                'dwell_time': dwell_time,
                'cool_down_temp': getattr(cycle_data, 'cool_down_temp', "N/A"),
                'core_temp_setpoint': getattr(cycle_data, 'core_temp_setpoint', "N/A"),
                'temp_ramp': getattr(cycle_data, 'temp_ramp', "N/A"),
                'set_pressure': getattr(cycle_data, 'set_pressure', "N/A"),
                'maintain_vacuum': "Yes" if (hasattr(cycle_data, 'maintain_vacuum') and cycle_data.maintain_vacuum) else "No",
                'initial_set_cure_temp': getattr(cycle_data, 'initial_set_cure_temp', "N/A"),
                'final_set_cure_temp': getattr(cycle_data, 'final_set_cure_temp', "N/A"),
                'alarms': alarm_info,
                'supervisor': supervisor_username if supervisor_username else "N/A",
                'current_date': datetime.now().strftime("%Y-%m-%d"),
                'generation_time': datetime.now().strftime("%H:%M:%S")
            }
        }
        html_content = template.render(**report_data)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"HTML report generated successfully: {html_path}")
        webbrowser.open_new_tab(html_path)

        options = {
            'page-size': 'A4',
            'encoding': "UTF-8",
            'enable-local-file-access': ""
        }
        wkhtmltopdf_path = os.path.join(os.getcwd(), 'wkhtmltopdf.exe')
        config_pdfkit = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        pdfkit.from_string(html_content, pdf_path, options=options, configuration=config_pdfkit)
        logger.info(f"PDF report generated: {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        fallback_path = pdf_path.replace('.pdf', '.txt')
        try:
            with open(fallback_path, 'w', encoding='utf-8') as file:
                file.write(f"Report for {cycle_number} (fallback due to PDF generation failure)\n")
                for key, value in report_data['data'].items():
                    file.write(f"{key}: {value}\n")
            logger.info(f"Fallback text report generated: {fallback_path}")
        except Exception as ex:
            logger.error(f"Failed to generate fallback report: {ex}")

    # Create or update the CycleReport record bound to this cycle.
    try:
        # Explicitly verify the cycle ID before proceeding
        cycle_id = getattr(cycle_data, 'id', None)
        if not cycle_id:
            logger.error("Cannot associate report: cycle_data has no valid ID")
            return (pdf_filename, csv_filename)
            
        # Check if a report already exists for this cycle
        existing_report = db.session.query(CycleReport).filter(CycleReport.cycle_id == cycle_id).first()
        
        if existing_report:
            logger.info(f"Updating existing report record for cycle {cycle_id}")
            existing_report.pdf_report_path = pdf_filename
            existing_report.html_report_path = html_filename
            existing_report.html_report_content = html_content  # Save HTML content
        else:
            logger.info(f"Creating new report record for cycle {cycle_id}")
            new_report = CycleReport(
                cycle_id=cycle_id,
                pdf_report_path=pdf_filename,
                html_report_path=html_filename,
                html_report_content=html_content  # Save HTML content
            )
            db.session.add(new_report)
        
        db.session.commit()
        logger.info(f"Successfully saved report paths to database for cycle {cycle_id}")
    except sqlalchemy.exc.IntegrityError as ie:
        logger.error(f"Database integrity error updating cycle report record: {ie}")
        db.session.rollback()
        try:
            cycle_id = getattr(cycle_data, 'id', None)
            if cycle_id:
                db.session.execute(
                    "UPDATE cycle_reports SET pdf_report_path = :pdf, html_report_path = :html, html_report_content = :html_content WHERE cycle_id = :cycle_id",
                    {"pdf": pdf_filename, "html": html_filename, "html_content": html_content, "cycle_id": cycle_id}
                )
                db.session.commit()
                logger.info(f"Successfully updated report using direct SQL for cycle {cycle_id}")
            else:
                logger.error("Cannot update report: cycle_data has no valid ID")
        except Exception as e2:
            logger.error(f"Second attempt to update report failed: {e2}")
            db.session.rollback()
    except Exception as e:
        logger.error(f"Error updating cycle report record: {e}")
        db.session.rollback()

    # Delete existing serial numbers and insert the new ones for this cycle.
    try:
        # Explicitly verify the cycle ID before proceeding
        cycle_id = getattr(cycle_data, 'id', None)
        if not cycle_id:
            logger.error("Cannot associate serial numbers: cycle_data has no valid ID")
            return (pdf_filename, csv_filename)
            
        logger.info(f"Deleting existing serial numbers for cycle {cycle_id}")
        db.session.query(CycleSerialNumber).filter(CycleSerialNumber.cycle_id == cycle_id).delete()
        
        valid_serials = [sn.strip() for sn in serial_numbers if sn and sn.strip() and not sn.startswith("PLACEHOLDER_")]
        if not valid_serials:
            timestamp_serial = datetime.now().strftime("%Y%m%d%H%M%S")
            placeholder = f"PLACEHOLDER_{cycle_id}_{timestamp_serial}"
            logger.warning(f"No valid serial numbers provided; creating unique placeholder: {placeholder}")
            record = CycleSerialNumber(cycle_id=cycle_id, serial_number=placeholder)
            db.session.add(record)
        else:
            logger.info(f"Adding new serial numbers for cycle {cycle_id}: {valid_serials}")
            for sn in valid_serials:
                try:
                    record = CycleSerialNumber(cycle_id=cycle_id, serial_number=sn)
                    db.session.add(record)
                except sqlalchemy.exc.IntegrityError as ie:
                    logger.warning(f"Serial number {sn} already exists. Adding with suffix.")
                    db.session.rollback()
                    suffix = datetime.now().strftime("%H%M%S")
                    record = CycleSerialNumber(cycle_id=cycle_id, serial_number=f"{sn}_R{suffix}")
                    db.session.add(record)
        
        db.session.commit()
        logger.info(f"Cycle serial numbers stored successfully for cycle {cycle_id}.")
    except Exception as e:
        logger.error(f"Error saving cycle serial numbers: {e}")
        db.session.rollback()
    try:
        upload_to_onedrive(csv_path, pdf_path)
    except Exception as e:
        logger.error(f"Error during OneDrive upload: {e}")

    return (pdf_filename, csv_filename)
