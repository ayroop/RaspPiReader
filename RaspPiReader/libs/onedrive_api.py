import os
import requests
from requests.auth import HTTPBasicAuth

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
            return False

    def check_connection(self):
        if not self.token:
            return False
        url = f"{self.base_url}/me/drive"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        return response.status_code == 200

    def create_folder(self, folder_name, parent_folder_id=None):
        if not self.token:
            return None
        if parent_folder_id:
            url = f"{self.base_url}/me/drive/items/{parent_folder_id}/children"
        else:
            url = f"{self.base_url}/me/drive/root/children"
        headers = {"Authorization": f"Bearer {self.token}",
                   "Content-Type": "application/json"}
        data = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in (200, 201):
            return response.json().get("id")
        else:
            return None

    def upload_file(self, file_path, folder_id=None):
        if not self.token:
            return False
        file_name = os.path.basename(file_path)
        if folder_id:
            url = f"{self.base_url}/me/drive/items/{folder_id}:/{file_name}:/content"
        else:
            url = f"{self.base_url}/me/drive/root:/{file_name}:/content"
        headers = {"Authorization": f"Bearer {self.token}"}
        with open(file_path, "rb") as f:
            response = requests.put(url, headers=headers, data=f)
        return response.status_code in (200, 201)