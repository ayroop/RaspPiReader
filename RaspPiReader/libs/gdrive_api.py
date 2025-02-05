import os.path
from genericpath import isfile
from os import path, getenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GoogleDriveAPI(object):
    def __init__(self):
        pass

    def check_creds(self):
        cred_path = path.join(getenv('LOCALAPPDATA'), r"RasbPiReader\credentials")
        if not isfile(path.join(cred_path, 'google_drive.json')):
            return FileNotFoundError
        return self.initiate_service()

    def initiate_service(self):
        # If modifying these scopes, delete the file token.json.
        SCOPES = ['https://www.googleapis.com/auth/drive']

        cred_path = path.join(getenv('LOCALAPPDATA'), r"RasbPiReader\credentials")
        token_path = path.join(cred_path, 'token.json')

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    path.join(cred_path, 'google_drive.json'), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w+') as token:
                token.write(creds.to_json())
        try:
            self.drive_service = build('drive', 'v3', credentials=creds)
        except:
            DISCOVERY_SERVICE_URL = 'https://www.googleapis.com/discovery/v1/apis/drive/v3/rest'
            self.drive_service = build('drive', 'v3', credentials=creds, discoveryServiceUrl=DISCOVERY_SERVICE_URL)
        return True

    def upload_file(self, file_name, mime_type, drive_full_path, parent_id):
        file_metadata = {
            'name': file_name,
            'parents': [parent_id],
        }
        media = MediaFileUpload(drive_full_path,
                                mimetype=mime_type)
        file = self.drive_service.files().create(body=file_metadata, media_body=media,
                                                 fields='id').execute()
        print(F'File ID: {file.get("id")}')
        return file.get("id")

    def create_folder(self, folder_name):
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        file = self.drive_service.files().create(body=file_metadata, fields='id'
                                                 ).execute()
        print(F'Folder has created with ID: "{file.get("id")}".')
        return file.get('id')

    def update_file(self, file_id, new_filename):
        media_body = MediaFileUpload(
            new_filename, resumable=True)

        updated_file = self.drive_service.files().update(
            fileId=file_id,
            # body=file,
            media_body=media_body).execute()
        return updated_file.get('id')

    def check_connection(self):
        files = self.drive_service.files()
        return files.list(pageSize=1, fields="files(id, name)").execute()

    def delete_file(self, file_id):
        try:
            deleted_file = self.drive_service.files().delete(
                fileId=file_id,
            ).execute()
            return True
        except Exception as e:
            print('An error occurred  while deleting file: %s' % e)
            return False


def grant_access(self, sheet_id, email):
    def callback(request_id, response, exception):
        if exception:
            # Handle error
            print(exception)
        else:
            print("Permission Id: %s" % response.get('id'))

    batch = self.drive_service.new_batch_http_request(callback=callback)
    # user_permission = {
    #     'type': 'user',
    #     'role': 'writer',
    #     'emailAddress': 'user@example.com'
    # }
    # batch.add(self.drive_service.permissions().create(
    #         fileId=sheet_id,
    #         body=user_permission,
    #         fields='id',
    # ))
    domain_permission = {
        'type': 'user',
        'role': 'reader',
        'emailAddress': email,
    }
    batch.add(self.drive_service.permissions().create(
        fileId=sheet_id,
        body=domain_permission,
        fields='id',
    ))
    batch.execute()
