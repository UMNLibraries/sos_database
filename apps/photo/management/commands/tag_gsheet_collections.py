from django.core.management.base import BaseCommand

from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df
from apps.photo.utils.import_utils import set_collections

from django.conf import settings


class Command(BaseCommand):
    
    gsheets = gsheets_login()

    def handle(self, *args, **kwargs):

        image_df = get_gsheets_df(self.gsheets, settings.GSHEETS_PHOTOS_IMPORT_ID, settings.GSHEETS_PHOTOS_IMPORT_SHEET_NAME)

        set_collections(image_df)

