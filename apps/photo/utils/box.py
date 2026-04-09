import os
from tempfile import NamedTemporaryFile
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener

from boxsdk import JWTAuth
from boxsdk import Client
from boxsdk.exception import BoxValueError
import pandas as pd

from django.conf import settings
# from dk import BOX_JWT

register_heif_opener()

def get_box_client():
    auth = JWTAuth(
        client_id=settings.BOX_JWT['boxAppSettings']['clientID'],
        client_secret=settings.BOX_JWT['boxAppSettings']['clientSecret'],
        enterprise_id=settings.BOX_JWT['enterpriseID'],
        jwt_key_id=settings.BOX_JWT['boxAppSettings']['appAuth']['publicKeyID'],
        rsa_private_key_file_sys_path=os.path.join(settings.BASE_DIR, 'settings', 'box_cert.pem'),
        rsa_private_key_passphrase=settings.BOX_JWT['boxAppSettings']['appAuth']['passphrase'],
    )

    access_token = auth.authenticate_instance()
    client = Client(auth)

    return client


def download_box_file(client, out_dir, box_id):
    box_obj = client.file(box_id).get()
    download_path = os.path.join(out_dir, box_obj.name)

    with open(download_path, 'wb') as open_file:
        client.file(box_obj.id).download_to(open_file)
        open_file.close()
    return download_path


def get_box_file_as_tempfile(client, box_id):
    '''Get a Box image file by ID and open as BytesIO file-like object'''
    if type(box_id) != float:
        box_obj = client.file(box_id).get()
    else:
        print(f'Error opening Box image {box_id}')
        return False
    
    with NamedTemporaryFile(delete=False) as temp_file:

        f = BytesIO(client.file(box_obj.id).content())
        temp_file.write(f.read())
        temp_file.flush() # Ensure the data is written to disk
        temp_file.seek(0)
        temp_file_name = temp_file.name
        # print(f"Temporary file created at: {temp_file_name}")

        return temp_file_name


def load_box_image(client, box_id):
    '''Get a Box image file by ID and open in PIL for further operations'''
    if type(box_id) != float:
        try:
            box_obj = client.file(box_id).get()
        except BoxValueError:
            print(f'Error opening Box image {box_id}')
            return False
    else:
        print(f'Error opening Box image {box_id}')
        return False

    f = BytesIO(client.file(box_obj.id).content())
    
    try:
        im = Image.open(f)
        return im
    except UnidentifiedImageError:
        print(f'Error opening Box image {box_id}')
        return False

    

def load_box_spreadsheet(client, box_id):
    '''Get a Box spreadsheet file by ID and open in pandas for further operations'''
    if type(box_id) != float:
        box_obj = client.file(box_id).get()
    else:
        print(f'Error opening Box file {box_id}')
        return False
    
    f = BytesIO(client.file(box_obj.id).content())
    
    try:
        df = pd.read_csv(f)
        return df
    except:
        raise
        print(f'Error opening Box spreadsheet {box_id}')
        return False


def build_folder_file_list(client, box_folder_id):
    ''' Export a dictionary where Box file names are the keys and the values are Box file IDs, to enable downloading by ID'''

    box_folder = client.folder(box_folder_id).get()
    file_list = []
    items = box_folder.get_items()
    for item in items:
        file_list.append({'box_id': item.id, 'photo_file_name': item.name})
        # print('{0} {1} is named "{2}"'.format(item.type.capitalize(), item.id, item.name))

    return file_list
