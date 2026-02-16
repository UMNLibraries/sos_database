import os
import re
import csv
import boto3
import time
import datetime
import pandas as pd
import numpy as np
from slugify import slugify
from multiprocessing.pool import ThreadPool
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.park.models import Park
from apps.photo.models import Photo, SCOPE_CHOICES, LOCATION_TYPE_CHOICES
from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df
from apps.photo.utils.box import get_box_client, build_folder_file_list, load_box_image, load_box_spreadsheet
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

    # TODO: How do I get the numerical Box ID?

    raw_storage_class = 'GLACIER_IR'
    
    box = get_box_client()
    # gsheets = gsheets_login()
    # session = boto3.Session(profile_name='sos')
    # s3 = session.client('s3', region_name='us-east-2')
    # upload_batch_size = -1
    # bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    # min_thread_time = None
    # num_threads = None

    # def add_arguments(self, parser):

    #     parser.add_argument('-l', '--limit', type=int, default=-1,
    #                     help='Only upload a certain number of images, primarily for testing')

    #     parser.add_argument('-b', '--box_refresh', action='store_true',
    #                     help='Re-generate CSV of Box Image IDs.')

    #     parser.add_argument('-r', '--reload_objs', action='store_true',
    #                     help='Delete and re-create Django Photo instances.')

    #     parser.add_argument('-y', '--dry', action='store_true',
    #                     help='Just tell me how many keys are left to upload and exit.')
        
    #     parser.add_argument('-p', '--pool', type=int, default=8,
    #                         help='How many threads to use? (Default is 8)')

    #     parser.add_argument('-m', '--mintime', type=float, default=0,
    #                         help='What is the minimum time to execute each thread (rate limit) in seconds (Default is 0)')

    def build_real_box_filename(self, row):
        '''Modified from Melinda code: clean original file name and then construct 'photo_file_name'. Using custom replace instead of slugify to match what is being done in Qualtrix upload'''
        # print(row)
        file_name_slug = re.sub(r"[()\~'%\\\[\]\s]", '', row['photo_file_name_orig'])
        photo_file_name_final = row['qualtrix_response_id'] + '_' + file_name_slug
        return photo_file_name_final
    
    def merge_with_parks_list(self, form_response_df):
        # Create park slug for comparison to existing values
        form_response_df['park_slug'] = form_response_df['park_name'].apply(lambda x: slugify(x))
        
        parks_df = pd.DataFrame(Park.objects.all().values('name', 'site_code'))
        parks_df['park_slug'] = parks_df['name'].apply(lambda x: slugify(x))

        form_response_df = form_response_df.merge(
            parks_df.drop(columns=['name']),
            how="left",
            on="park_slug"
        )
        print(form_response_df)

        # Missing site code values?
        missing_site_codes = form_response_df[form_response_df['site_code'].isna()]
        if missing_site_codes.shape[0] > 0:
            print(f"WARNING: Missing site code value on {missing_site_codes.shape[0]} rows.")
            print(missing_site_codes)

        return form_response_df
    
    def get_box_image_ids_by_site(self, site_code_list):
        # Only run this cell if you need to re-generate image IDs
        image_id_list = []
        # box = get_box_client()
        for park in Park.objects.exclude(box_folder_id='').filter(site_code__in=site_code_list):

            print(f"Getting image IDs for {park.site_code} ({park.box_folder_id})")

            image_id_list += build_folder_file_list(self.box, park.box_folder_id)

        site_df = pd.DataFrame(image_id_list)
        # print(image_id_list)

        # os.makedirs(self.DATA_DIR, exist_ok=True)
        # site_df.to_csv(self.BOX_IMAGE_IDS_CSV, index=False)

        return site_df
    
    def get_box_image_ids_bulk(self):
        '''Photos that did not go through stage 1 manual processing are in one big folder, not listed by site'''
        
        image_id_list = build_folder_file_list(self.box, settings.BOX_FORM_IMAGES_FOLDER_ID)
        image_df = pd.DataFrame(image_id_list)
        return image_df
    
    def import_photo_objects(self, image_df):
        ''' This is simpler than the version in import_photos_gsheet because no moderation has happened yet.'''
        parks_lookup = {park['site_code']: {'id': park['id'], 'centerpoint': park['centerpoint']} for park in Park.objects.all().values('id', 'site_code', 'centerpoint')}

        photo_objs = []
        for index, row in image_df.iterrows():

            park_id = parks_lookup[row['site_code']]['id']
            centerpoint = parks_lookup[row['site_code']]['centerpoint']

            try:
                date_taken = datetime.datetime.strptime(row['date_taken'], "%m/%d/%Y").date()
            except ValueError:
                date_taken = None

            photo = Photo(
                park_id=park_id,
                status='RD',  # 'Ready for Review'
                box_id=row['box_id'],
                box_filename=row['photo_file_name_final'],
                photo_file_name=row['photo_file_name_final'],
                original_file_name=row['photo_file_name_orig'],
                date_taken=date_taken,
                dt_form=row['dt_form_submitted'],
                title=row['title'],
                additional_notes=row['additional_notes'],
                location_orig=centerpoint,
                location_type='PK',  # 'Park Centerpoint'
                main_image_url=f"images/{get_jpg_filename(row['photo_file_name_final'])}",
                thumb_url=f"thumbs/{get_jpg_filename(row['photo_file_name_final'])}",
            )
            photo_objs.append(photo)

        Photo.objects.bulk_create(photo_objs, batch_size=1000)
    
    def handle(self, *args, **kwargs):

        form_response_df = load_box_spreadsheet(self.box, settings.BOX_FORM_RESPONSES_FILE_ID)
        print(form_response_df)

        print(form_response_df.columns)
    #     ['StartDate', 'EndDate', 'Status', 'Progress', 'Duration (in seconds)',
    #    'Finished', 'RecordedDate', 'ResponseId', 'DistributionChannel',
    #    'UserLanguage', 'Q_RecaptchaScore', 'Q1_Id', 'Q1_Name', 'Q1_Size',
    #    'Q1_Type', 'Q2', 'Q6_1', 'Q10', 'Q7', 'Q2.1', 'Q20', 'Q2_1', 'Q21']
        
        form_response_df = form_response_df.rename(columns={
            'RecordedDate': 'dt_form_submitted',
            'Finished': 'upload_complete',
            'ResponseId': 'qualtrix_response_id',
            # 'Q1_Id': 'box_id',
            'Q1_Name': 'photo_file_name_orig',  # In Google sheet this value has qualtrix response ID added as a prefix -- should I look for images with or without that value?
            'Q6_1': 'park_name',
            'Q10': 'title',
            'Q7': 'additional_notes',
            'Q2.1': 'date_taken',
            'Q2_1': 'date_taken_2'
        })[[
            'dt_form_submitted',
            'upload_complete',
            'qualtrix_response_id',
            'photo_file_name_orig',
            'park_name',
            'title',
            'additional_notes',
            'date_taken',
            'date_taken_2',
        ]]

        print(form_response_df)

        # Filter out unfinished uploads
        form_response_df = form_response_df[(form_response_df['upload_complete'] == 1) & (~form_response_df['photo_file_name_orig'].isna())].drop(columns=['upload_complete'])

        # Merge 2 different date_taken values
        form_response_df['date_taken_final'] = form_response_df['date_taken'].combine_first(form_response_df['date_taken_2'])
        form_response_df.drop(columns=['date_taken', 'date_taken_2'], inplace=True)
        form_response_df.rename(columns={'date_taken_final': 'date_taken'}, inplace=True)

        # Fix Box filename because a prefix has been pre-pended at upload
        form_response_df['photo_file_name_final'] = form_response_df.apply(lambda row: self.build_real_box_filename(row), axis=1)

        print(form_response_df)

        print(f"Found {form_response_df.shape[0]} valid Qualtrics rows...")

        # Merge with parks list
        form_response_df = self.merge_with_parks_list(form_response_df)

        # Dedupe from what is in DB/gsheets import
        existing_photo_ids = pd.DataFrame(list(set(Photo.objects.all().values_list('box_filename', flat=True))), columns=['existing_box_filename'])
        print(f"Currently {existing_photo_ids.shape[0]} images in database.")

        form_response_df = form_response_df.merge(
            existing_photo_ids,
            how="left",
            left_on="photo_file_name_final",
            right_on="existing_box_filename"
        )
        form_response_df = form_response_df[form_response_df['existing_box_filename'].isna()]
        print(f"{form_response_df.shape[0]} remaining new rows for import...")

        if form_response_df.shape[0] > 0:

            # sites_with_updates = list(form_response_df['site_code'].drop_duplicates())

            # # Get numerical Box IDs from Box
            # # TODO: These IDs are not matching -- is it possible that Box folder IDs for each site changed?
            # image_id_list = self.get_box_image_ids_by_site(sites_with_updates)

            # Get numerical Box IDs from Box
            image_id_list = self.get_box_image_ids_bulk()

            print(image_id_list)
            form_response_df = form_response_df.merge(
                image_id_list,
                how="left",
                left_on="photo_file_name_final",
                right_on="box_filename"
            )
            form_response_df['title'] = form_response_df['title'].fillna(value='')

            form_response_df.to_csv(os.path.join(self.DATA_DIR, 'merge_test.csv'), index=False)

            self.import_photo_objects(form_response_df)

        # TODO: Ingest missing Box images to private Google storage