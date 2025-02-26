from genericpath import isfile
from os import path, getenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GoogleDriveAPI(object):
    def __init__(self):
        self.drive_service = None

    def check_creds(self):
        SCOPES = ['https://www.googleapis.com/auth/drive']
        cred_path = path.join(getenv('LOCALAPPDATA'), r"RasbPiReader\credentials")
        token_path = path.join(cred_path, 'token.json')

        creds = None
        if path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    path.join(cred_path, 'google_drive.json'), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        try:
            self.drive_service = build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"Failed to create Google Drive service: {e}")
            return False
        return True

    def initiate_service(self):
        return self.check_creds()

    def upload_file(self, file_name, mime_type, drive_full_path, parent_id):
        if not self.drive_service:
            print("Google Drive service not initialized.")
            return None

        file_metadata = {
            'name': file_name,
            'parents': [parent_id]
        }
        media = MediaFileUpload(drive_full_path, mimetype=mime_type)
        try:
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            print(f"File {file_name} uploaded successfully.")
            return file.get('id')
        except Exception as e:
            print(f"Failed to upload file {file_name}: {e}")
            return None

    def create_folder(self, folder_name):
        if not self.drive_service:
            print("Google Drive service not initialized.")
            return None

        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        try:
            file = self.drive_service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            print(f"Folder {folder_name} created successfully.")
            return file.get('id')
        except Exception as e:
            print(f"Failed to create folder {folder_name}: {e}")
            return None

    def update_file(self, file_id, new_filename):
        if not self.drive_service:
            print("Google Drive service not initialized.")
            return None

        try:
            file = self.drive_service.files().update(
                fileId=file_id,
                body={'name': new_filename},
                fields='id'
            ).execute()
            print(f"File {file_id} updated successfully.")
            return file.get('id')
        except Exception as e:
            print(f"Failed to update file {file_id}: {e}")
            return None

    def check_connection(self):
        if not self.drive_service:
            print("Google Drive service not initialized.")
            return False

        try:
            about = self.drive_service.about().get(fields="user").execute()
            print(f"Connected to Google Drive as {about['user']['displayName']}")
            return True
        except Exception as e:
            print(f"Failed to connect to Google Drive: {e}")
            return False

    def delete_file(self, file_id):
        if not self.drive_service:
            print("Google Drive service not initialized.")
            return False

        try:
            self.drive_service.files().delete(fileId=file_id).execute()
            print(f"File {file_id} deleted successfully.")
            return True
        except Exception as e:
            print(f"Failed to delete file {file_id}: {e}")
            return False

    def grant_access(self, sheet_id, email):
        def callback(request_id, response, exception):
            if exception:
                print(f"Failed to grant access to {email}: {exception}")
            else:
                print(f"Access granted to {email}")

        batch = self.drive_service.new_batch_http_request(callback=callback)
        user_permission = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': email
        }
        batch.add(self.drive_service.permissions().create(
            fileId=sheet_id,
            body=user_permission,
            fields='id',
        ))
        batch.execute()