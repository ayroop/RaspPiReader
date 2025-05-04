import os
import csv
import logging
import pdfkit
import webbrowser
import shutil
from jinja2 import Template
from datetime import datetime
from RaspPiReader.libs.plc_communication import write_coil
from RaspPiReader.libs.onedrive_api import OneDriveAPI
from RaspPiReader import pool
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, OneDriveSettings, CycleSerialNumber, CycleData, CycleReport, AlarmMapping, DefaultProgram
import sqlalchemy.exc
from sqlalchemy.orm import Session

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

def create_unique_plot_export(cycle_id, timestamp):
    """
    Create a unique plot export image for this cycle using a multi-strategy approach:
    1. Try to find a plot image named with the cycle ID first
    2. Copy the default plot_export.png to a unique name if it exists
    3. Use the most recent plot as a fallback
    4. Create a basic placeholder plot if nothing else is available
    
    Args:
        cycle_id: The cycle ID
        timestamp: Timestamp string for the filename
        
    Returns:
        Tuple of (plot_filename, plot_path)
    """
    try:
        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Create a unique filename for this cycle's plot
        plot_filename = f"{cycle_id}_{timestamp}_plot.png"
        unique_plot_path = os.path.join(reports_dir, plot_filename)
        
        # Strategy 1: Look for a plot with the cycle ID in the name
        cycle_id_str = str(cycle_id)
        cycle_plots = list(filter(
            lambda f: cycle_id_str in f and f.endswith('.png'),
            os.listdir(reports_dir)
        ))
        
        if cycle_plots:
            # Use the most recent plot for this cycle
            most_recent = sorted(cycle_plots, key=lambda f: os.path.getmtime(os.path.join(reports_dir, f)), reverse=True)[0]
            most_recent_path = os.path.join(reports_dir, most_recent)
            shutil.copy2(most_recent_path, unique_plot_path)
            logger.info(f"Using existing cycle plot for cycle {cycle_id}: {most_recent} → {unique_plot_path}")
            return (plot_filename, unique_plot_path)
        
        # Strategy 2: Check normal plot_export.png
        default_plot_path = os.path.join(os.getcwd(), "RaspPiReader", "reports", "plot_export.png")
        if os.path.exists(default_plot_path):
            # Copy the plot export to our unique filename
            shutil.copy2(default_plot_path, unique_plot_path)
            logger.info(f"Created unique plot from default for cycle {cycle_id}: {unique_plot_path}")
            return (plot_filename, unique_plot_path)
        
        # Strategy 3: No plot exists, check if we have an older one to use
        logger.warning(f"No plot_export.png found at {default_plot_path}")
        existing_plots = sorted(list(filter(
            lambda f: f.endswith('_plot.png'),
            os.listdir(reports_dir)
        )), reverse=True)
        
        if existing_plots:
            # Use the most recent plot as a fallback
            recent_plot = os.path.join(reports_dir, existing_plots[0])
            shutil.copy2(recent_plot, unique_plot_path)
            logger.info(f"Using most recent plot as template: {recent_plot} -> {unique_plot_path}")
            return (plot_filename, unique_plot_path)
        
        # Strategy 4: Create a basic placeholder plot
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            # Create a simple placeholder plot
            plt.figure(figsize=(10, 6))
            x = np.linspace(0, 10, 100)
            y = np.sin(x)
            plt.plot(x, y)
            plt.title(f"Cycle {cycle_id} - Placeholder Chart")
            plt.xlabel("Time")
            plt.ylabel("Value")
            plt.grid(True)
            
            # Save it
            plt.savefig(unique_plot_path)
            plt.close()
            
            logger.info(f"Created placeholder plot for cycle {cycle_id}: {unique_plot_path}")
            return (plot_filename, unique_plot_path)
            
        except Exception as e:
            logger.error(f"Error creating placeholder plot: {e}")
            logger.warning(f"No plot images found to use as fallback")
            return (None, None)
            
    except Exception as e:
        logger.error(f"Error creating unique plot export: {e}")
        return (None, None)

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
    
    # Write to the PLC coil to signal end-of-cycle using fixed address 8200
    stop_coil_addr = 8200  # Fixed address for cycle stop signal
    try:
        write_coil(stop_coil_addr, 0)  # Write 0 to stop the cycle
        logger.info(f"Cycle stop signal sent to coil {stop_coil_addr} (0x{stop_coil_addr:04X})")
    except Exception as e:
        logger.error(f"Error writing to stop coil: {e}")
    
    # Ensure we write zero again
    try:
        write_coil(stop_coil_addr, 0)
    except Exception as e:
        logger.error(f"Error writing second stop signal: {e}")

    db = Database("sqlite:///local_database.db")
    from RaspPiReader.libs.models import CycleData, CycleReport
    cycle_data = db.session.query(CycleData)\
        .outerjoin(CycleReport, CycleData.id == CycleReport.cycle_id)\
        .filter(CycleData.id == cycle_data.id)\
        .one_or_none()
    
    # Build alarm mapping from DB
    alarm_mapping = {}
    alarm_logs = []  # List to store alarm logs
    db_alarms = db.session.query(Alarm).all()
    for alarm in db_alarms:
        # Get all active mappings for this alarm
        mappings = db.session.query(AlarmMapping).filter_by(
            alarm_id=alarm.id,
            active=True
        ).all()
        
        for mapping in mappings:
            threshold_type = "Low" if mapping.value == 1 else "High"
            alarm_text = f"{threshold_type} Threshold ({mapping.threshold:.2f}) - {mapping.message}"
            alarm_mapping[str(alarm.channel)] = alarm_text
            # Add to alarm logs
            alarm_logs.append(f"Channel {alarm.channel}: {alarm_text}")

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
    
    # Create a unique plot export for this cycle
    plot_filename, plot_path = create_unique_plot_export(cycle_number, timestamp)
        
    # Try to get plot path from visualization manager if available
    try:
        # Import here to avoid circular imports
        from RaspPiReader.libs.visualization_manager import VisualizationManager
        vis_manager = VisualizationManager.instance()
        if hasattr(vis_manager, 'get_current_plot_path'):
            vis_plot_path = vis_manager.get_current_plot_path()
            if vis_plot_path and os.path.exists(vis_plot_path):
                logger.info(f"Using visualization manager plot: {vis_plot_path}")
                plot_path = vis_plot_path
                plot_filename = os.path.basename(vis_plot_path)
    except Exception as e:
        logger.warning(f"Could not get plot from visualization manager: {e}")

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

    try:
        # First check for serial numbers directly associated with this cycle
        stored_serials = db.session.query(CycleSerialNumber).filter(CycleSerialNumber.cycle_id == cycle_id).all()
        db_serial_list = [s.serial_number for s in stored_serials
                          if s.serial_number and not s.serial_number.startswith("PLACEHOLDER_")]
        
        # If no valid serial numbers found for this cycle, check for related cycles
        if not db_serial_list:
            logger.info(f"No direct serial numbers found for cycle {cycle_id}, checking related cycles")
            # Look for related cycles with the same order_id
            if hasattr(cycle_data, 'order_id') and cycle_data.order_id:
                # Find other cycles with the same order_id
                related_cycles = db.session.query(CycleData).filter(
                    CycleData.order_id == cycle_data.order_id,
                    CycleData.id != cycle_id  # Exclude current cycle
                ).all()
                
                for related_cycle in related_cycles:
                    related_serials = db.session.query(CycleSerialNumber).filter(
                        CycleSerialNumber.cycle_id == related_cycle.id
                    ).all()
                    
                    related_serial_list = [s.serial_number for s in related_serials
                                          if s.serial_number and not s.serial_number.startswith("PLACEHOLDER_")]
                    
                    if related_serial_list:
                        logger.info(f"Found {len(related_serial_list)} serial numbers from related cycle {related_cycle.id}")
                        db_serial_list.extend(related_serial_list)
        
        if not db_serial_list:
            serial_list = "No serial numbers recorded"
            logger.info(f"Only placeholder serial numbers found in DB for cycle {cycle_id}")
        else:
            # Remove duplicates while preserving order
            seen = set()
            unique_serials = []
            for sn in db_serial_list:
                if sn not in seen:
                    seen.add(sn)
                    unique_serials.append(sn)
            
            serial_list = ", ".join(unique_serials)
            logger.info(f"Retrieved serial numbers for cycle {cycle_id}: {serial_list}")
    except Exception as e:
        logger.error(f"Error fetching stored serial numbers: {e}")
        serial_list = "No serial numbers recorded"

    try:
        dwell_time = float(cycle_data.dwell_time) if hasattr(cycle_data, 'dwell_time') else 0.0
    except Exception:
        dwell_time = 0.0
    try:
        quantity = int(cycle_data.quantity) if hasattr(cycle_data, 'quantity') and str(cycle_data.quantity).isdigit() else len(serial_numbers)
    except Exception:
        quantity = len(serial_numbers)

    # Get program number and settings
    program_number = getattr(cycle_data, 'program_number', None)
    if not program_number:
        program_number = pool.config("program_number", int, default_val=1)
    
    # Get program settings from database
    from RaspPiReader.libs.models import DefaultProgram
    program_settings = db.session.query(DefaultProgram).filter_by(
        program_number=program_number
    ).first()
    
    if program_settings:
        core_temp_setpoint = program_settings.core_temp_setpoint
    else:
        core_temp_setpoint = pool.config("core_temp_setpoint", float, default_val=100.0)

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
        
        # Prepare plot image path for the template
        plot_image_rel_path = None
        if plot_path and os.path.exists(plot_path):
            try:
                # Get relative path for HTML - use the reports directory as base
                reports_dir = os.path.join(os.getcwd(), "reports")
                # Make sure we're using the correct path separator for HTML
                plot_image_rel_path = os.path.basename(plot_path)
                logger.info(f"Including plot image in report: {plot_image_rel_path}")
                
                # Create a backup copy with timestamp in the filename for reference
                timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
                backup_filename = f"{cycle_number}_{timestamp_str}_plot.png"
                backup_path = os.path.join(reports_dir, backup_filename)
                
                if not os.path.exists(backup_path) and os.path.exists(plot_path):
                    try:
                        shutil.copy2(plot_path, backup_path)
                        logger.info(f"Created timestamped backup of plot: {backup_filename}")
                    except Exception as copy_err:
                        logger.warning(f"Could not create timestamped backup of plot: {copy_err}")
            except Exception as e:
                logger.error(f"Error preparing plot path for template: {e}")
        # Add timestamp for cache busting
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        report_data = {
            'data': {
                'order_id': getattr(cycle_data, 'order_id', "N/A"),
                'cycle_id': getattr(cycle_data, 'cycle_id', "N/A"),
                'program_number': program_number,
                'core_temp_setpoint': core_temp_setpoint,
                'quantity': quantity,
                'size': getattr(cycle_data, 'size', "N/A"),
                'serial_numbers': serial_list,
                'cycle_location': getattr(cycle_data, 'cycle_location', "N/A"),
                'cycle_date': cycle_date,
                'cycle_start_time': cycle_start_time,
                'cycle_end_time': cycle_end_time,
                'dwell_time': dwell_time,
                'cool_down_temp': getattr(cycle_data, 'cool_down_temp', "N/A"),
                'temp_ramp': getattr(cycle_data, 'temp_ramp', "N/A"),
                'set_pressure': getattr(cycle_data, 'set_pressure', "N/A"),
                'maintain_vacuum': "Yes" if (hasattr(cycle_data, 'maintain_vacuum') and cycle_data.maintain_vacuum) else "No",
                'initial_set_cure_temp': getattr(cycle_data, 'initial_set_cure_temp', "N/A"),
                'final_set_cure_temp': getattr(cycle_data, 'final_set_cure_temp', "N/A"),
                'core_high_temp_time': getattr(cycle_data, 'core_high_temp_time', None),
                'release_temp': getattr(cycle_data, 'pressure_drop_core_temp', None),
                'alarms': alarm_info,
                'alarm_logs': alarm_logs,
                'supervisor': supervisor_username if supervisor_username else "N/A",
                'current_date': datetime.now().strftime("%Y-%m-%d"),
                'generation_time': datetime.now().strftime("%H:%M:%S"),
                'timestamp': timestamp,
                'plot_image': plot_image_rel_path,
                'plot_path': f"{plot_image_rel_path}?t={timestamp}" if plot_image_rel_path else None
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
            if plot_filename:
                existing_report.plot_image_path = plot_filename  # Save plot image path
                logger.info(f"Updated plot image path in database: {plot_filename}")
        else:
            logger.info(f"Creating new report record for cycle {cycle_id}")
            new_report = CycleReport(
                cycle_id=cycle_id,
                pdf_report_path=pdf_filename,
                html_report_path=html_filename,
                html_report_content=html_content,  # Save HTML content
                plot_image_path=plot_filename if plot_filename else None  # Save plot image path
            )
            db.session.add(new_report)
            if plot_filename:
                logger.info(f"Saved plot image path in new database record: {plot_filename}")
        
        db.session.commit()
        logger.info(f"Successfully saved report paths to database for cycle {cycle_id}")
    except sqlalchemy.exc.IntegrityError as ie:
        logger.error(f"Database integrity error updating cycle report record: {ie}")
        db.session.rollback()
        try:
            cycle_id = getattr(cycle_data, 'id', None)
            if cycle_id:
                db.session.execute(
                    "UPDATE cycle_reports SET pdf_report_path = :pdf, html_report_path = :html, html_report_content = :html_content, plot_image_path = :plot WHERE cycle_id = :cycle_id",
                    {"pdf": pdf_filename, "html": html_filename, "html_content": html_content, "plot": plot_filename, "cycle_id": cycle_id}
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

    # Process the final serial numbers:
    # Instead of deleting existing records, first see if there are valid serials stored.
    try:
        stored_serials = db.session.query(CycleSerialNumber).filter(CycleSerialNumber.cycle_id == cycle_id).all()
        valid_stored = [s.serial_number for s in stored_serials if s.serial_number and not s.serial_number.startswith("PLACEHOLDER_")]
        
        # Check if we have valid stored serial numbers for this cycle
        if valid_stored:
            logger.info(f"Using stored serial numbers for cycle {cycle_id}: {valid_stored}")
        else:
            # No valid serials found directly for this cycle
            
            # First, check if we have serial numbers from related cycles with the same order_id
            related_serials = []
            if hasattr(cycle_data, 'order_id') and cycle_data.order_id:
                # Find other cycles with the same order_id
                related_cycles = db.session.query(CycleData).filter(
                    CycleData.order_id == cycle_data.order_id,
                    CycleData.id != cycle_id  # Exclude current cycle
                ).all()
                
                for related_cycle in related_cycles:
                    related_records = db.session.query(CycleSerialNumber).filter(
                        CycleSerialNumber.cycle_id == related_cycle.id
                    ).all()
                    
                    for record in related_records:
                        if record.serial_number and not record.serial_number.startswith("PLACEHOLDER_"):
                            related_serials.append(record.serial_number)
                
                if related_serials:
                    logger.info(f"Found {len(related_serials)} serial numbers from related cycles")
                    # Copy these serial numbers to the current cycle
                    for sn in related_serials:
                        # Check if this serial number already exists for this cycle
                        existing = db.session.query(CycleSerialNumber).filter(
                            CycleSerialNumber.cycle_id == cycle_id,
                            CycleSerialNumber.serial_number == sn
                        ).first()
                        
                        if not existing:
                            record = CycleSerialNumber(cycle_id=cycle_id, serial_number=sn)
                            db.session.add(record)
                    
                    db.session.commit()
                    logger.info(f"Copied serial numbers from related cycles to cycle {cycle_id}")
            
            # If we still don't have serial numbers, use the provided list
            if not related_serials:
                # No valid serials found, so insert from the provided list.
                valid_serials = [sn.strip() for sn in serial_numbers if sn and sn.strip() and not sn.startswith("PLACEHOLDER_")]
                # Deduplicate while preserving order.
                seen = set()
                dedup_serials = []
                for s in valid_serials:
                    if s not in seen:
                        dedup_serials.append(s)
                        seen.add(s)
                valid_serials = dedup_serials

                if not valid_serials:
                    timestamp_serial = datetime.now().strftime("%Y%m%d%H%M%S")
                    placeholder = f"PLACEHOLDER_{cycle_id}_{timestamp_serial}"
                    logger.warning(f"No valid serial numbers provided; creating unique placeholder: {placeholder}")
                    record = CycleSerialNumber(cycle_id=cycle_id, serial_number=placeholder)
                    db.session.add(record)
                else:
                    logger.info(f"Adding new serial numbers for cycle {cycle_id}: {valid_serials}")
                    for sn in valid_serials:
                        record = CycleSerialNumber(cycle_id=cycle_id, serial_number=sn)
                        db.session.add(record)
                db.session.commit()
    except Exception as e:
        logger.error(f"Error saving cycle serial numbers: {e}")
        db.session.rollback()

    try:
        upload_to_onedrive(csv_path, pdf_path)
    except Exception as e:
        logger.error(f"Error during OneDrive upload: {e}")

    return (pdf_filename, csv_filename)
