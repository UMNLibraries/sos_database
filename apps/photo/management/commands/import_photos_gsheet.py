import os
import re
import csv
import boto3
import time
import datetime
import pandas as pd
import numpy as np
from multiprocessing.pool import ThreadPool
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.park.models import Park
from apps.photo.models import Photo, SCOPE_CHOICES, LOCATION_TYPE_CHOICES
from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df
from apps.photo.utils.box import get_box_client, build_folder_file_list, load_box_file
from apps.photo.utils.image_processing import remove_exif, thumbnail_to_s3, image_to_s3, get_current_s3_matches, get_jpg_filename

from sos_database.storage_backends import PrivateMediaStorage
from django.conf import settings

class Command(BaseCommand):

    DATA_DIR = os.path.join(settings.BASE_DIR, 'data')
    BOX_IMAGE_IDS_CSV = os.path.join(DATA_DIR, 'box_image_id_lookup.csv')
    LOGGING_MANIFEST_PATH = os.path.join(DATA_DIR, 's3_upload_results.csv')

    logging_keys = [
        'Scope', 'Metadata edits', 'box_foldername', 'photo_file_name', 'title', 'additional_notes', 'date_taken', 'collection', 'park_name', 'id', 'original_file_name', 'ext', 'longitude', 'latitude', 'location_source', 'type', 'alpha_code', 'box_id', 'box_filename',
        'thumb_url', 'main_image_url', 's3_error'
    ]

    raw_storage_class = 'GLACIER_IR'
    
    box = get_box_client()
    gsheets = gsheets_login()
    session = boto3.Session(profile_name='sos')
    s3 = session.client('s3', region_name='us-east-2')
    upload_batch_size = -1
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    min_thread_time = None
    num_threads = None

    def add_arguments(self, parser):

        parser.add_argument('-l', '--limit', type=int, default=-1,
                        help='Only upload a certain number of images, primarily for testing')

        parser.add_argument('-b', '--box_refresh', action='store_true',
                        help='Re-generate CSV of Box Image IDs.')
        
        parser.add_argument('-d', '--delete', action='store_true',
                        help='Delete existing records before import.')
        
        parser.add_argument('-y', '--dry', action='store_true',
                        help='Just tell me how many keys are left to upload and exit.')
        
        parser.add_argument('-p', '--pool', type=int, default=8,
                            help='How many threads to use? (Default is 8)')

        parser.add_argument('-m', '--mintime', type=float, default=0,
                            help='What is the minimum time to execute each thread (rate limit) in seconds (Default is 0)')
        
    def clear_all(self):
        Photo.objects.all().delete()

    def get_box_image_ids_by_site(self):
        # Only run this cell if you need to re-generate image IDs
        image_id_list = []
        # box = get_box_client()
        for park in Park.objects.exclude(box_folder_id=''):

            print(f"Getting image IDs for {park.site_code} ({park.box_folder_id})")

            image_id_list += build_folder_file_list(self.box, park.box_folder_id)

        site_df = pd.DataFrame(image_id_list)
        print(image_id_list)

        os.makedirs(self.DATA_DIR, exist_ok=True)
        site_df.to_csv(self.BOX_IMAGE_IDS_CSV, index=False)

    def build_image_df(self, image_id_list):
        """ Main import of image metadata from Gsheets. Join to Box image IDs since we don't already have them connected in that sheet."""

        # service = gsheets_login()
        image_df = get_gsheets_df(self.gsheets, settings.GSHEETS_PHOTOS_IMPORT_ID, settings.GSHEETS_PHOTOS_IMPORT_SHEET_NAME)
        # print(image_df)
        print(f"Found {image_df.shape[0]} images in data set.")

        # Join to box image_ids
        site_df = pd.read_csv(self.BOX_IMAGE_IDS_CSV, dtype={'box_id': str})

        image_df = image_df.merge(
            site_df,
            how="left",
            left_on="photo_file_name",
            right_on="box_filename"
        )

        # Remove unexpected columns
        existing_colums = list(image_df.columns)
        keep_columns = [e for e in existing_colums if e in self.logging_keys]
        image_df = image_df[keep_columns]

        return image_df
    
    def import_photo_objects(self, image_df):
        parks_lookup = {park['site_code']: park['id'] for park in Park.objects.all().values('id', 'site_code')}

        photo_objs = []
        for index, row in image_df.iterrows():

            park_id = parks_lookup[row['box_foldername']]

            scope = next((scope[0] for scope in SCOPE_CHOICES if row['Scope'].lower() == scope[1].lower()), '')

            # Set status
            if row['Scope'].lower() == 'save for later':
                status = 'SV'
            elif row['Scope'].lower() == 'needs attention':
                status = 'AT'
            elif row['Metadata edits'].lower() == 'needs attention':
                status = 'AT'
            else:
                status = 'AP'  # Will set to "live" after upload check

            try:
                date_taken = datetime.datetime.strptime(row['date_taken'], "%m/%d/%Y").date()
            except ValueError:
                date_taken = None

            location_orig = None
            location_type = ''
            if row['latitude'] not in [None, '', np.nan] and row['longitude'] not in [None, '', np.nan]:
                location_orig = Point(float(row['longitude']), float(row['latitude']))
                location_type = row['location_source']
                location_type = next((lt[0] for lt in LOCATION_TYPE_CHOICES if row['location_source'].lower() == lt[1].lower()), '')

            photo = Photo(
                park_id=park_id,
                scope=scope,
                status=status,
                box_id=row['box_id'],
                box_filename=row['box_filename'],
                # box_foldername = models.CharField(max_length=255)
                photo_file_name=row['photo_file_name'],
                original_file_name=row['original_file_name'],
                date_taken=date_taken,
                title=row['title'],
                additional_notes=row['additional_notes'],
                location_orig=location_orig,
                location_type=location_type,
                main_image_url=f"images/{get_jpg_filename(row['photo_file_name'])}",
                thumb_url=f"thumbs/{get_jpg_filename(row['photo_file_name'])}",
            )
            photo_objs.append(photo)

        Photo.objects.bulk_create(photo_objs, batch_size=1000)

    
    def create_upload_list(self, image_df, current_thumbs, current_main_images):
        """ This might be redundant, will revisit after importing metadata to Django model """
        
        upload_list = image_df.copy()

        upload_list['jpg_filename'] = upload_list['photo_file_name'].apply(lambda x: get_jpg_filename(x))
        # media_url_root = f'https://{settings.AWS_S3_CUSTOM_DOMAIN}/{PrivateMediaStorage.location}/'
        upload_list['thumb_key'] = upload_list['jpg_filename'].apply(lambda x: os.path.join(PrivateMediaStorage.location, 'thumbs', x))
        upload_list['thumb_url'] = f'https://{settings.AWS_S3_CUSTOM_DOMAIN}/' + upload_list['thumb_key']
        upload_list['main_key'] = upload_list['jpg_filename'].apply(lambda x: os.path.join(PrivateMediaStorage.location, 'images', x))
        upload_list['main_image_url'] = f'https://{settings.AWS_S3_CUSTOM_DOMAIN}/' + upload_list['main_key']

        # Filter down if you don't want to do the whole set
        if self.upload_batch_size > 0:
            upload_list = upload_list[:self.upload_batch_size]

        print(f"Found {len(upload_list)} images from spreadsheet for upload to S3...")

        print("Checking which images have been uploaded already...")
        upload_list['thumb_uploaded'] = upload_list['thumb_key'].apply(lambda x: x in current_thumbs)
        upload_list['main_image_uploaded'] = upload_list['main_key'].apply(lambda x: x in current_main_images)

        print(f"Found {upload_list[upload_list['thumb_uploaded'] == True].shape[0]} already uploaded, matching thumbnails.")
        print(f"Found {upload_list[upload_list['main_image_uploaded'] == True].shape[0]} already uploaded, matching main images.")

        upload_list = upload_list.to_dict('records')

        return upload_list
    
    def upload_missing_files(self, upload_list):
        
        with open(self.LOGGING_MANIFEST_PATH, 'w') as done_manifest:
            done_manifest.write(','.join(self.logging_keys) + "\n")

        pool = ThreadPool(processes=self.num_threads)
        pool.map(self.send_to_s3, upload_list)

    def send_to_s3(self, row):
        
        bucket_name = self.bucket_name
        start_time = time.time()
        s3_error = False
        bool_upload = False

        if row['thumb_uploaded'] == False or row['main_image_uploaded'] == False:
            bool_upload = True
            box = self.box
            # Get image from Box and open in PIL
            im = load_box_file(box, row['box_id'])

            if not im:
                print("WARNING: COULDN'T UPLOAD IMAGE.")
                s3_error = True
                thumb_url = None
                main_image_url = None
            else:

                if row['thumb_uploaded'] == False:
                    print(f"Uploading thumbnail {row['thumb_url']}...")
                    thumb_url = thumbnail_to_s3(self.s3, remove_exif(im), bucket_name, row['thumb_key'], row['thumb_url'])
        
                if row['main_image_uploaded'] == False:
                    print(f"Uploading image {row['main_image_url']}...")
                    main_image_url = image_to_s3(self.s3, remove_exif(im), bucket_name, row['main_key'], row['thumb_url'])
 
        row['s3_error'] = s3_error
        # print(row)
    
        with open(self.LOGGING_MANIFEST_PATH, 'a') as csvfile:
            spamwriter = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(row.values())

        # If necessary, wait before completing
        if bool_upload and self.min_thread_time > 0:
            elapsed = time.time() - start_time
            time_remaining = self.min_thread_time - elapsed
            if time_remaining > 0:
                print(f'Pausing {time_remaining} seconds')
                time.sleep(time_remaining)

        return row
        
    def handle(self, *args, **kwargs):
        clear_first = kwargs['delete']
        box_refresh = kwargs['box_refresh']
        self.upload_batch_size = kwargs['limit']
        self.min_thread_time = kwargs['mintime']
        self.num_threads = kwargs['pool']

        if clear_first:
            self.clear_all()

        if box_refresh:
            image_id_list = self.get_box_image_ids_by_site()
        else:
            image_id_list = pd.read_csv(self.BOX_IMAGE_IDS_CSV)

        image_df = self.build_image_df(image_id_list)
        print(image_df)

        photos = self.import_photo_objects(image_df)

        # Check which images already uploaded
        current_thumbs = get_current_s3_matches(self.s3, self.bucket_name, 'media/thumbs')
        current_main_images = get_current_s3_matches(self.s3, self.bucket_name, 'media/images')
        print(current_main_images)
        print(f"Found {len(current_main_images)} main images and {len(current_thumbs)} thumbnails already on S3.")

        upload_list = self.create_upload_list(image_df, current_thumbs, current_main_images)

        if kwargs['dry']:
            # Exit without uploading.
            return False

        self.upload_missing_files(upload_list)
