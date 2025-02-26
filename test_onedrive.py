from RaspPiReader.libs.onedrive_api import OneDriveAPI
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

def test_onedrive():
    """Test OneDrive authentication and operations"""
    # Replace these with your application's values
    client_id = input("Enter Client ID: ")
    client_secret = input("Enter Client Secret: ")
    tenant_id = input("Enter Tenant ID: ")
    
    if not client_id or not client_secret or not tenant_id:
        logger.error("Missing required parameters")
        return
    
    onedrive = OneDriveAPI()
    
    # Test authentication
    logger.info("Testing OneDrive authentication...")
    authenticated = onedrive.authenticate(client_id, client_secret, tenant_id)
    
    if authenticated:
        logger.info("Authentication successful!")
        
        # Test folder creation
        folder_name = "TestFolder"
        logger.info(f"Creating folder '{folder_name}'...")
        folder_id = onedrive.create_folder(folder_name)
        
        if folder_id:
            logger.info(f"Folder created with ID: {folder_id}")
            
            # Test file upload (create a test file first)
            test_file_path = "test_file.txt"
            with open(test_file_path, 'w') as f:
                f.write("This is a test file for OneDrive integration")
            
            logger.info(f"Uploading file '{test_file_path}'...")
            file_id = onedrive.upload_file(test_file_path, folder_id)
            
            if file_id:
                logger.info(f"File uploaded with ID: {file_id}")
                
                # Test file update
                with open(test_file_path, 'w') as f:
                    f.write("This is an updated test file for OneDrive integration")
                
                logger.info("Updating file...")
                if onedrive.update_file(file_id, test_file_path):
                    logger.info("File updated successfully")
                else:
                    logger.error("File update failed")
                
                # Test file deletion
                logger.info("Deleting file...")
                if onedrive.delete_file(file_id):
                    logger.info("File deleted successfully")
                else:
                    logger.error("File deletion failed")
            else:
                logger.error("File upload failed")
        else:
            logger.error("Folder creation failed")
    else:
        logger.error("Authentication failed")

if __name__ == "__main__":
    test_onedrive()