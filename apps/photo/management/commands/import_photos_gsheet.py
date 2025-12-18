from django.core.management.base import BaseCommand

from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df

from django.conf import settings

class Command(BaseCommand):

    def add_arguments(self, parser):
        
        parser.add_argument('-d', '--delete', action='store_true',
                        help='Delete existing records before import.')
        
    # def clear_all(self):
    #     State.objects.all().delete()
    #     SiteType.objects.all().delete()
    #     Park.objects.all().delete()
        
    def handle(self, *args, **kwargs):
        clear_first = kwargs['delete']

        if clear_first:
            self.clear_all()

        service = gsheets_login()
        df = get_gsheets_df(service, settings.GSHEETS_PHOTOS_IMPORT_ID, settings.GSHEETS_PHOTOS_IMPORT_SHEET_NAME)
        print(df)


