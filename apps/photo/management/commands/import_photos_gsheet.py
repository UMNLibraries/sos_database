import os
import boto3
import datetime
import pandas as pd
import numpy as np
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.park.models import Park
from apps.photo.models import Photo, ManualCorrection, SCOPE_CHOICES, LOCATION_TYPE_CHOICES
from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df
from apps.photo.utils.box import get_box_client, build_folder_file_list
from apps.photo.utils.image_processing import get_jpg_filename
from apps.photo.utils.import_utils import set_collections

from sos_database.storage_backends import PrivateMediaStorage
from django.conf import settings


class Command(BaseCommand):

    DATA_DIR = os.path.join(settings.BASE_DIR, 'data')
    BOX_IMAGE_IDS_CSV = os.path.join(DATA_DIR, 'box_image_id_lookup.csv')
    LOGGING_MANIFEST_PATH = os.path.join(DATA_DIR, 's3_upload_results.csv')

    logging_keys = [
        'Scope', 'Metadata edits', 'box_foldername', 'photo_file_name', 'title', 'additional_notes', 'date_taken', 'collection', 'park_name', 'id', 'original_file_name', 'ext', 'longitude', 'latitude', 'location_source', 'type', 'alpha_code', 'box_id',
        'thumb_url', 'main_image_url', 's3_error', 'original_additional_notes'
    ]

    raw_storage_class = 'GLACIER_IR'
    
    box = get_box_client()
    gsheets = gsheets_login()

    def add_arguments(self, parser):

        parser.add_argument('-b', '--box_refresh', action='store_true',
                        help='Re-generate CSV of Box Image IDs.')

        parser.add_argument('-r', '--reset_cxes', action='store_true',
                        help='Delete and re-create Django ManualCorrection instances, possibly deleting manual work but increasing speed.')
        
    def get_box_image_ids_by_site(self):
        # Only run this cell if you need to re-generate image IDs
        image_id_list = []

        for park in Park.objects.exclude(box_folder_id=''):

            print(f"Getting image IDs for {park.site_code} ({park.box_folder_id})")

            image_id_list += build_folder_file_list(self.box, park.box_folder_id)

        site_df = pd.DataFrame(image_id_list)
        print(image_id_list)

        os.makedirs(self.DATA_DIR, exist_ok=True)
        site_df.to_csv(self.BOX_IMAGE_IDS_CSV, index=False)

    def build_image_df(self, image_id_list):
        """ Main import of image metadata from Gsheets. Join to Box image IDs since we don't already have them connected in that sheet."""

        image_df = get_gsheets_df(self.gsheets, settings.GSHEETS_PHOTOS_IMPORT_ID, settings.GSHEETS_PHOTOS_IMPORT_SHEET_NAME)
        # print(image_df)
        print(f"Found {image_df.shape[0]} images in data set.")
        image_df.drop(columns=['box_id'], inplace=True)

        # Join to box image_ids
        site_df = pd.read_csv(self.BOX_IMAGE_IDS_CSV, dtype={'box_id': str})


        image_df = image_df.drop(
            columns=['box_filename']
        ).merge(
            site_df,
            how="left",
            left_on="photo_file_name",
            right_on="box_filename"
        )

        # Remove unexpected columns
        existing_colums = list(image_df.columns)
        # print(existing_colums)
        keep_columns = [e for e in existing_colums if e in self.logging_keys]
        # print(f'Keep columns: : {keep_columns}')
        image_df = image_df[keep_columns]

        # TODO: Fill na on notes
        image_df['additional_notes'] = image_df['additional_notes'].fillna('')
        image_df['original_additional_notes'] = image_df['original_additional_notes'].fillna('')

        return image_df
    
    def parse_additional_notes(self, row):
        '''Check if changes have been made to additional notes, and if so, create ManualCorrection object.
        Otherwise, set original and final values to same thing.'''

        additional_notes = row['original_additional_notes']
        if row['additional_notes'] != additional_notes:
            # Manual correction needed
            additional_notes_final = row['additional_notes']
            if additional_notes_final == '':
                additional_notes_final = None
            bool_cx = True
        else:
            additional_notes_final = additional_notes
            bool_cx = False

        return {
            'photo_file_name': row['photo_file_name'],
            'additional_notes': additional_notes,
            'additional_notes_final': additional_notes_final,
            'bool_cx': bool_cx
        }

    def delete_existing_gsheet_photo_objs(self, image_df, bool_reset_cxes=False):
        photo_objs = Photo.objects.filter(photo_file_name__in=image_df.photo_file_name.to_list())
        if bool_reset_cxes:
            ManualCorrection.objects.filter(photo_id__in=photo_objs.values_list('id', flat=True)).delete()
        photo_objs.delete()
        # print(len(photo_objs))
    
    def import_photo_objects(self, image_df):
        parks_lookup = {park['site_code']: park['id'] for park in Park.objects.all().values('id', 'site_code')}

        photo_objs = []
        cx_lookups = []
        collection_lookups = []
        for index, row in image_df.iterrows():

            park_id = parks_lookup[row['box_foldername']]

            scope = next((scope[0] for scope in SCOPE_CHOICES if row['Scope'].lower() == scope[1].lower()), '')

            # Set status
            if row['Scope'].lower() == 'save for later':
                status = 'SV'
            elif row['Scope'].lower() == 'needs attention':
                status = 'AT'
            elif row['Scope'].lower() == 'exact duplicate':
                status = 'RJ'
            elif row['Scope'].lower() == 'out of scope':
                status = 'RJ'
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

            notes_obj = self.parse_additional_notes(row)
            if notes_obj['bool_cx']:
                cx_lookups.append(notes_obj)

            photo = Photo(
                park_id=park_id,
                scope=scope,
                status=status,
                photo_type='NML',
                box_id=row['box_id'],
                # box_filename=row['box_filename'],
                # box_foldername = models.CharField(max_length=255)
                photo_file_name=row['photo_file_name'],
                original_file_name=row['original_file_name'],
                date_taken=date_taken,
                title=row['title'],
                title_final=row['title'],  # Set initial "final" value
                additional_notes=notes_obj['additional_notes'],
                additional_notes_final=notes_obj['additional_notes_final'],  # Set initial "final" value
                # location=location_orig,  # Don't set this now, instead have location_embedded value that requires opening the image in Box
                location_final=location_orig,  # Set initial "final" value
                location_type=location_type,
                location_type_final=location_type,  # Set initial "final" value
                main_image_url=f"images/{get_jpg_filename(row['photo_file_name'])}",
                thumb_url=f"thumbs/{get_jpg_filename(row['photo_file_name'])}",
            )
            photo_objs.append(photo)

        Photo.objects.bulk_create(photo_objs, batch_size=1000)

        return {'photo_objs': photo_objs, 'cx_lookups': cx_lookups}
    
    def create_cxes(self, photo_objs, cx_lookups, bool_reset_cxes=False):

        photo_objs_lookup = {obj.photo_file_name: obj.pk for obj in photo_objs}
        
        if bool_reset_cxes:
            print('Adding ManualCorrections the fast way.')
            cx_objs = []
            for cx in cx_lookups:

                if not cx['additional_notes_final']:
                    notes = 'BLANK'
                else:
                    notes = cx['additional_notes_final']

                cx_obj = ManualCorrection(
                    photo_id=photo_objs_lookup[cx['photo_file_name']],
                    additional_notes=notes
                )
                cx_objs.append(cx_obj)
            ManualCorrection.objects.bulk_create(cx_objs)

        else:
            print('Adding ManualCorrections, but only re-setting additional notes')
            for cx in cx_lookups:

                if not cx['additional_notes_final']:
                    notes = 'BLANK'
                else:
                    notes = cx['additional_notes_final']

                print(f"Creating ManualCorrection for {cx['photo_file_name']}")
                obj, created = ManualCorrection.objects.get_or_create(
                    photo_id=photo_objs_lookup[cx['photo_file_name']],
                    defaults={"additional_notes": notes},
                )
                if not created:
                    obj.additional_notes = notes
                    obj.save()
        
    def handle(self, *args, **kwargs):
        reset_cxes = kwargs['reset_cxes']
        box_refresh = kwargs['box_refresh']

        if box_refresh:
            image_id_list = self.get_box_image_ids_by_site()
        else:
            image_id_list = pd.read_csv(self.BOX_IMAGE_IDS_CSV)

        image_df = self.build_image_df(image_id_list)

        self.delete_existing_gsheet_photo_objs(image_df, reset_cxes)
        import_results = self.import_photo_objects(image_df)

        set_collections(image_df)

        if len(import_results['cx_lookups']) > 0:
            self.create_cxes(import_results['photo_objs'], import_results['cx_lookups'], reset_cxes)
