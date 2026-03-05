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
from apps.photo.utils.box import get_box_client, load_box_image, get_box_file_as_tempfile
from apps.photo.utils.image_processing import remove_exif, get_gps_info, thumbnail_to_s3, image_to_s3, get_current_s3_matches, get_jpg_filename

from sos_database.storage_backends import PrivateMediaStorage
from django.conf import settings

class Command(BaseCommand):
    '''Find photos that are in DB but have not been moved to S3, then copy from Box to private storage'''

    DATA_DIR = os.path.join(settings.BASE_DIR, 'data')
    # BOX_IMAGE_IDS_CSV = os.path.join(DATA_DIR, 'box_image_id_lookup.csv')
    LOGGING_MANIFEST_PATH = os.path.join(DATA_DIR, 's3_upload_results.csv')

    logging_keys = [
        'box_id', 'photo_file_name', 'thumb_url', 'main_image_url', 's3_error', 'image_latitude', 'image_longitude'
    ]

    raw_storage_class = 'GLACIER_IR'
    
    box = get_box_client()

    if hasattr(settings, 'AWS_PROFILE_NAME'):
        session = boto3.Session(profile_name=settings.AWS_PROFILE_NAME)
    else:
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY,
            # region_name=settings.REGION
        )
    s3 = session.client('s3', region_name='us-east-2')
    upload_batch_size = -1
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    embedded_locations = []

    min_thread_time = None
    num_threads = None
    bool_extract_locations = False

    def add_arguments(self, parser):

        parser.add_argument('-l', '--limit', type=int, default=-1,
                        help='Only upload a certain number of images, primarily for testing')

        parser.add_argument('-y', '--dry', action='store_true',
                        help='Just tell me how many keys are left to upload and exit.')
        
        parser.add_argument('-x', '--no-location', action='store_false',
                        help='Do NOT try to extract location info from Box file while importing.')
        
        parser.add_argument('-p', '--pool', type=int, default=8,
                            help='How many threads to use? (Default is 8)')

        parser.add_argument('-m', '--mintime', type=float, default=0,
                            help='What is the minimum time to execute each thread (rate limit) in seconds (Default is 0)')
        
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
            im = load_box_image(box, row['box_id'])

            if not im:
                print("WARNING: COULDN'T UPLOAD IMAGE.")
                s3_error = True
                thumb_url = None
                main_image_url = None
            else:
                # Check for location data unless --no-location passed
                if self.bool_extract_locations:
                    infile = get_box_file_as_tempfile(box, row['box_id'])
                    location_info = get_gps_info(infile)
                    os.remove(infile)
                    if location_info:
                        row['image_latitude'] = location_info['latitude']
                        row['image_longitude'] = location_info['longitude']

                        self.embedded_locations.append(row)

                    else:
                        row['image_latitude'] = ''
                        row['image_longitude'] = ''

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
    
    def add_embedded_locations(self):
        '''After going through all new Box photos, attach any found location info to the Photo instance.'''

        update_objs = []

        photo_lookup_filenames = [p['photo_file_name'] for p in self.embedded_locations]

        photos_to_update = Photo.objects.filter(
            photo_file_name__in=photo_lookup_filenames
        )

        for p in photos_to_update:
            matching_row = next((l for l in self.embedded_locations if l['photo_file_name'] == p.photo_file_name), None)
            if matching_row:
                p.location_embedded = Point(float(matching_row['longitude']), float(matching_row['latitude']))
                update_objs.append(p)

        Photo.objects.bulk_update(update_objs, ['location_embedded'])
        
    def handle(self, *args, **kwargs):
        # reload_photos = kwargs['reload_objs']
        # box_refresh = kwargs['box_refresh']
        self.upload_batch_size = kwargs['limit']
        self.min_thread_time = kwargs['mintime']
        self.num_threads = kwargs['pool']
        self.bool_extract_locations = kwargs['no_location']
    
        # Check which images already uploaded
        current_thumbs = get_current_s3_matches(self.s3, self.bucket_name, 'media/thumbs')
        current_main_images = get_current_s3_matches(self.s3, self.bucket_name, 'media/images')
        # print(current_main_images)
        print(f"Found {len(current_main_images)} main images and {len(current_thumbs)} thumbnails already on S3.")

        image_df = pd.DataFrame(Photo.objects.all().values(
            'box_id', 'photo_file_name', 'thumb_url', 'main_image_url'
        ))
        upload_list = self.create_upload_list(image_df, current_thumbs, current_main_images)
        # print(upload_list)

        if kwargs['dry']:
            # Exit without uploading.
            return False

        self.upload_missing_files(upload_list)

        if self.bool_extract_locations:
            self.add_embedded_locations()
