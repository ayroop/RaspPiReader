# RaspPiReader - PLC Integration System

## Project Overview

RaspPiReader is an advanced industrial monitoring system that integrates Programmable Logic Controllers (PLCs) with Raspberry Pi devices for comprehensive data acquisition, real-time monitoring, and detailed reporting. The system is designed for industrial applications requiring robust performance, reliable data collection, and intuitive visualization.

![RaspPiReader Dashboard](https://placeholder-for-dashboard-screenshot.com)

## Key Features

- **PLC Communication**: Direct interface with industrial PLCs via RS485 or TCP protocols
- **Real-time Data Visualization**: Dynamic dashboard with matplotlib integration
- **Cycle Management**: Start, monitor, and stop manufacturing cycles with proper resource handling
- **Comprehensive Data Logging**: Automatic CSV and PDF report generation
- **Alarm Monitoring**: Real-time detection and notification of system alarms
- **User Authentication**: Role-based access control system
- **Core Temperature Monitoring**: Specialized tracking for thermal processes
- **Cloud Integration**: Automatic syncing with Azure SQL Database and OneDrive
- **Serial Number Management**: Track manufactured items throughout production

## System Architecture

- **Python-based** application with PyQt UI framework
- **Dual Database System**:
  - Local SQLite database for immediate storage and offline operation
  - Azure SQL Database for enterprise-level data management and remote access
- **Modular Design** with separation of concerns for maintainability
- **Thread-based** concurrent operations for responsive UI during data collection
- **Resource Management** with proper cleanup mechanisms

## Prerequisites

1. **Python**: Version 3.6 or later ([python.org](https://www.python.org/downloads/))
2. **Git**: For version control ([git-scm.com](https://git-scm.com/downloads/))
3. **Azure Account**: For cloud database integration
4. **OneDrive Account**: For cloud storage integration
5. **ODBC Driver 17 for SQL Server**: Required for Azure SQL connectivity

## Deployment on Windows

### Installation

1. **Clone the Repository**:
   ```sh
   git clone https://github.com/yourusername/RaspPiReader.git
   cd RaspPiReader
   ```

2. **Set Up Virtual Environment**:
   ```sh
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Initial Configuration**:
   ```sh
   python create_tables.py
   python run.py
   ```

### Configuration

#### PLC Communication Setup

1. Navigate to "Settings" > "PLC Communication Settings"
2. Configure your connection:
   - Select communication mode (RS485/TCP)
   - For TCP: Enter IP address and port
   - For RS485: Select COM port and configure baudrate, parity, databits, stopbits
   - Set reading address and register read type
   - Configure polling intervals

#### Database Configuration

1. Navigate to "Settings" > "Database Settings"
2. Enter your Azure SQL Database credentials:
   - Server name
   - Database name
   - Username and password
3. Test the connection before saving

#### User Management

1. Navigate to "Settings" > "User Management"
2. Create users with appropriate permissions:
   - Settings access
   - Search capabilities
   - User management rights

#### Cloud Integration

1. Navigate to "Settings" > "OneDrive Settings"
2. Enter your Azure AD application details:
   - Client ID
   - Client Secret
   - Tenant ID
3. Set synchronization intervals

## Building for Distribution

Create a standalone executable using PyInstaller:

```sh
pip install pyinstaller
pyinstaller --onefile --windowed --icon="RaspPiReader-icon.ico" --add-data "local_database.db;." run.py
```

The executable will be created in the `dist` folder.

## Development Guidelines

- Use feature branches for new development
- Submit pull requests for code review
- Follow PEP 8 style guidelines
- Include unit tests for new functionality

## Troubleshooting

- **Connection Issues**: Verify firewall settings and network connectivity
- **Database Errors**: Ensure ODBC Driver 17 is installed and Azure firewall rules are configured
- **PLC Communication Failures**: Check physical connections and PLC settings
- **Application Crashes**: Review log files in the application directory

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For support or inquiries, please contact [your-email@example.com](mailto:your-email@example.com)
