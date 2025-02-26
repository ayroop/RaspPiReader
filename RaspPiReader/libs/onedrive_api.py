import os
import requests
import logging

class OneDriveAPI:
    def __init__(self):
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.token = None

    def authenticate(self, client_id, client_secret, tenant_id):
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "client_id": client_id,
            "scope": "https://graph.microsoft.com/.default",
            "client_secret": client_secret,
            "grant_type": "client_credentials"
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            return True
        else:
            raise Exception(f"Authentication failed: {response.text}")

    def check_connection(self):
        if not self.token:
            return False
        
        url = f"{self.base_url}/me/drive"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        return response.status_code == 200

    def create_folder(self, folder_name, parent_folder_id=None):
        if not self.token:
            raise Exception("Not authenticated")
            
        url = f"{self.base_url}/me/drive/root/children"
        if parent_folder_id:
            url = f"{self.base_url}/me/drive/items/{parent_folder_id}/children"
            
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in [201, 200]:
            return response.json()
        else:
            raise Exception(f"Failed to create folder: {response.text}")

    def upload_file(self, file_path, folder_id=None):
        if not self.token:
            raise Exception("Not authenticated")
            
        file_name = os.path.basename(file_path)
        url = f"{self.base_url}/me/drive/root:/{file_name}:/content"
        if folder_id:
            url = f"{self.base_url}/me/drive/items/{folder_id}:/{file_name}:/content"
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            with open(file_path, "rb") as file:
                response = requests.put(url, headers=headers, data=file)
                
            if response.status_code == 201:
                return response.json()
            else:
                raise Exception(f"Failed to upload file: {response.text}")
        except Exception as e:
            logging.error(f"Error uploading file to OneDrive: {str(e)}")
            raise