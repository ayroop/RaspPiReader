# RaspPiReader

## Deployment on Windows

Follow these steps to deploy the RaspPiReader application on a Windows machine.

### Prerequisites

1. **Python**: Ensure that Python 3.6 or later is installed. You can download it from [python.org](https://www.python.org/downloads/).
2. **Git**: Ensure that Git is installed. You can download it from [git-scm.com](https://git-scm.com/downloads/).

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
