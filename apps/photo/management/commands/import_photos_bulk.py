import datetime
import pandas as pd
from django.core.management.base import BaseCommand

from apps.park.models import Park
from apps.photo.models import Photo
from apps.photo.utils.box import get_box_client, load_box_spreadsheet
from apps.photo.utils.image_processing import get_jpg_filename
from apps.photo.utils.import_utils import set_collections

from django.conf import settings


class Command(BaseCommand):
    
    box = get_box_client()

    def parse_date_taken(self, input_str):
        try:
            return datetime.datetime.strptime(input_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.datetime.strptime(input_str, "%m/%d/%Y").date()
            except ValueError:
                try:
                    return datetime.datetime.strptime(input_str, "%m-%d-%Y").date()
                except ValueError:
                    return None
        # except:
        #     return None
    
    def import_photo_objects(self, image_df):
        ''' This is simpler than the version in import_photos_gsheet because no moderation has happened yet.'''
        parks_lookup = {park['name']: {'id': park['id'], 'centerpoint': park['centerpoint']} for park in Park.objects.all().values('id', 'name', 'centerpoint')}

        photo_objs = []
        for index, row in image_df.iterrows():

            park_id = parks_lookup[row['park_name']]['id']
            centerpoint = parks_lookup[row['park_name']]['centerpoint']

            # Time inadvertantly added to date_taken
            date_taken = self.parse_date_taken(row['date_taken'].replace(' 00:00:00', ''))
      
            photo = Photo(
                park_id=park_id,
                status='RD',  # 'Ready for Review'
                photo_type=row['photo_type'],
                box_id=row['box_id'],
                # box_filename=row['photo_file_name_final'],
                photo_file_name=row['photo_file_name'],
                original_file_name=row['original_file_name'],
                date_taken=date_taken,
                dt_form=row['dt_form'],
                title=row['title'],
                title_final=row['title'],  # Set initial "final" value
                additional_notes=row['additional_notes'],
                additional_notes_final=row['additional_notes'],  # Set initial "final" value
                # location=centerpoint,  # Don't set this now, instead have location_embedded value that requires opening the image in Box
                location_final=centerpoint,  # Set initial "final" value
                location_type='PK',  # 'Park Centerpoint'
                location_type_final='PK',  # Set initial "final" value
                main_image_url=f"images/{get_jpg_filename(row['photo_file_name'])}",
                thumb_url=f"thumbs/{get_jpg_filename(row['photo_file_name'])}",
            )
            photo_objs.append(photo)

        Photo.objects.bulk_create(photo_objs, batch_size=1000)
    
    def handle(self, *args, **kwargs):

        form_response_df = load_box_spreadsheet(self.box, settings.BOX_BULK_RESPONSES_FILE_ID)
        print(form_response_df)

        # Dedupe from what is in DB/gsheets import
        existing_photo_ids = pd.DataFrame(list(set(Photo.objects.all().values_list('photo_file_name', flat=True))), columns=['existing_box_filename'])
        print(f"Currently {existing_photo_ids.shape[0]} images in database.")

        form_response_df = form_response_df.merge(
            existing_photo_ids,
            how="left",
            left_on="photo_file_name",
            right_on="existing_box_filename"
        )
        form_response_df = form_response_df[form_response_df['existing_box_filename'].isna()]
        print(f"{form_response_df.shape[0]} remaining new rows for import...")

        if form_response_df.shape[0] > 0:

            form_response_df['title'] = form_response_df['title'].fillna(value='')
            form_response_df['additional_notes'] = form_response_df['additional_notes'].fillna(value='')

            self.import_photo_objects(form_response_df)

            # Tweak collections column header
            form_response_df.rename(columns={'collection_code': 'collection'}, inplace=True)
            set_collections(form_response_df)
