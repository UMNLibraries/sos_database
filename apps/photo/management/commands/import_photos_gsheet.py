import os
import pandas as pd
from django.core.management.base import BaseCommand

from apps.park.models import Park
from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df
from apps.photo.utils.box import get_box_client, build_folder_file_list

from django.conf import settings

class Command(BaseCommand):

    DATA_DIR = os.path.join(settings.BASE_DIR, 'data')
    BOX_IMAGE_IDS_CSV = os.path.join(DATA_DIR, 'box_image_id_lookup.csv')

    def add_arguments(self, parser):

        parser.add_argument('-b', '--box_refresh', action='store_true',
                        help='Re-generate CSV of Box Image IDs.')
        
        parser.add_argument('-d', '--delete', action='store_true',
                        help='Delete existing records before import.')
        
    # def clear_all(self):
    #     State.objects.all().delete()
    #     SiteType.objects.all().delete()
    #     Park.objects.all().delete()

    def get_box_image_ids_by_site(self):
        # Only run this cell if you need to re-generate image IDs
        image_id_list = []
        box = get_box_client()
        for park in Park.objects.exclude(box_folder_id=''):

            print(f"Getting image IDs for {park.site_code} ({park.box_folder_id})")

            image_id_list += build_folder_file_list(box, park.box_folder_id)

        site_df = pd.DataFrame(image_id_list)
        print(image_id_list)

        os.makedirs(self.DATA_DIR, exist_ok=True)
        site_df.to_csv(self.BOX_IMAGE_IDS_CSV, index=False)
        
    def handle(self, *args, **kwargs):
        clear_first = kwargs['delete']
        box_refresh = kwargs['box_refresh']

        if clear_first:
            self.clear_all()

        if box_refresh:
            image_id_list = self.get_box_image_ids_by_site()
        else:
            image_id_list = pd.read_csv(self.BOX_IMAGE_IDS_CSV)

        # service = gsheets_login()
        # df = get_gsheets_df(service, settings.GSHEETS_PHOTOS_IMPORT_ID, settings.GSHEETS_PHOTOS_IMPORT_SHEET_NAME)
        # print(df)
