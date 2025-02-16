# RaspPiReader

## Deployment on Windows

Follow these steps to deploy the RaspPiReader application on a Windows machine.

### Prerequisites

1. **Python**: Ensure that Python 3.6 or later is installed. You can download it from [python.org](https://www.python.org/downloads/).
2. **Git**: Ensure that Git is installed. You can download it from [git-scm.com](https://git-scm.com/downloads/).
3. **Azure Account**: Ensure that you have an Azure account to create an Azure SQL Database.
4. **OneDrive Account**: Ensure that you have a OneDrive account for integration.

### Steps

1. **Clone the Repository**:
    ```sh
    git clone https://github.com/yourusername/RaspPiReader.git
    cd RaspPiReader
    ```

2. **Create a Virtual Environment**:
    ```sh
    python -m venv venv
    ```

3. **Activate the Virtual Environment**:
    ```sh
    .\venv\Scripts\activate
    ```

4. **Install the Required Packages**:
    ```sh
    pip install -r requirements.txt
    ```

5. **Run the Application**:
    ```sh
    python run.py
    ```

### Setting Up Azure SQL Database

1. **Create an Azure SQL Database**:
    - Log in to the [Azure Portal](https://portal.azure.com/).
    - Click on "Create a resource" and select "SQL Database".
    - Fill in the required details and create a new SQL Database.

2. **Configure Firewall Rules**:
    - Go to your SQL Database resource in the Azure Portal.
    - Click on "Set server firewall" and add your client IP address to the allowed IP addresses.

3. **Get Connection String**:
    - Go to your SQL Database resource in the Azure Portal.
    - Click on "Connection strings" and copy the ADO.NET connection string.

4. **Create Tables**:
    - Connect to your Azure SQL Database using SQL Server Management Studio (SSMS) or any other SQL client.
    - Run the following SQL script to create the necessary tables:
    ```sql
    CREATE TABLE Users (
        id INT PRIMARY KEY IDENTITY,
        username NVARCHAR(50) NOT NULL,
        password NVARCHAR(50) NOT NULL,
        settings BIT NOT NULL,
        search BIT NOT NULL,
        user_mgmt_page BIT NOT NULL
    );

    -- Add other necessary tables here
    ```

### Configuring OneDrive

1. **Register an Application in Azure AD**:
    - Go to the [Azure Portal](https://portal.azure.com/).
    - Navigate to "Azure Active Directory" > "App registrations" > "New registration".
    - Fill in the required details and register the application.
    - Note down the "Application (client) ID" and "Directory (tenant) ID".

2. **Configure API Permissions**:
    - Go to your registered application in the Azure Portal.
    - Navigate to "API permissions" > "Add a permission" > "Microsoft Graph" > "Delegated permissions".
    - Add the necessary permissions for OneDrive (e.g., `Files.ReadWrite.All`).

3. **Generate Client Secret**:
    - Go to your registered application in the Azure Portal.
    - Navigate to "Certificates & secrets" > "New client secret".
    - Note down the generated client secret.

4. **Configure OneDrive Settings in the Application**:
    - Run the application and navigate to the OneDrive settings page.
    - Enter the "Client ID", "Client Secret", and "Tenant ID" obtained from the Azure Portal.
    - Test the connection and save the settings.

### Configuring Database Settings

1. **Run the Application**:
    ```sh
    python run.py
    ```

2. **Navigate to Database Settings**:
    - In the application, go to the "Settings" menu and select "Database Settings".

3. **Enter Database Connection Details**:
    - Enter the database connection details (e.g., server name, database name, username, password).
    - Test the connection and save the settings.

### Creating Users

To create an admin user in the SQLite database, follow these steps:

1. **Run the Application**:
    ```sh
    python run.py
    ```

2. **Navigate to User Management**:
    - In the application, go to the "Settings" menu and select "User Management".

3. **Add a New User**:
    - Click on "Add User" and fill in the required details.
    - Ensure that the "Admin" checkbox is selected to grant admin privileges to the user.

Alternatively, you can manually add an admin user to the SQLite database using a script:

1. **Create a Script to Add an Admin User**:
    ```python
    # add_admin_user.py
    from RaspPiReader.libs.database import Database
    from RaspPiReader.libs.models import User

    database_url = 'sqlite:///path_to_your_database.db'
    db = Database(database_url)

    admin_user = User(
        username='admin',
        password='admin_password',  # Ensure to hash the password
        settings=True,
        search=True,
        user_mgmt_page=True
    )

    db.add_user(admin_user)
    print("Admin user created successfully.")
    ```

2. **Run the Script**:
    ```sh
    python add_admin_user.py
    ```
### Configuring PLC Communication Settings

1. **Run the Application**:
    ```sh
    python run.py
    ```

2. **Navigate to PLC Communication Settings**:
    - In the application, go to the "Settings" menu and select "PLC Communication Settings".

3. **Enter PLC Communication Details**:
    - Enter the communication mode (e.g., RS485 or TCP).
    - Enter the IP address and port for TCP communication.
    - Enter the COM port for RS485 communication.
    - Save the settings.

### Configuring Database Settings

1. **Run the Application**:
    ```sh
    python run.py
    ```

2. **Navigate to Database Settings**:
    - In the application, go to the "Settings" menu and select "Database Settings".

3. **Enter Database Connection Details**:
    - Enter the database connection details (e.g., server name, database name, username, password).
    - Test the connection and save the settings.

### Syncing to Azure Database

The application will automatically sync the database settings, PLC communication settings, and user data to the Azure database every 60 seconds.
### Additional Information

- **Virtual Environment**: The virtual environment helps to manage dependencies and avoid conflicts with other projects.
- **Requirements File**: The [requirements.txt](http://_vscodecontentref_/1) file contains all the necessary packages for the project.
- **Running the Application**: The [run.py](http://_vscodecontentref_/2) script starts the application.

### Troubleshooting

- If you encounter any issues, ensure that all dependencies are installed correctly.
- Check the console output for any error messages and resolve them accordingly.

### Notes

- Make sure to replace `https://github.com/yourusername/RaspPiReader.git` with the actual URL of your repository.
- If you need to deactivate the virtual environment, you can use the following command:
    ```sh
    deactivate
    ```

### License

This project is licensed under the MIT License - see the LICENSE file for details.