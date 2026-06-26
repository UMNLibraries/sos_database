import os
import datetime
import pandas as pd

from django.core.management.base import BaseCommand

from apps.photo.models import Photo
from apps.park.models import Park

from django.conf import settings


class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument('-s', '--site', type=str,
                            help='Site code for park to export from')

    def handle(self, *args, **kwargs):

        site_code = kwargs['site']
        
        if not site_code:
            print('Missing site code. Please specify with --site.')
            return False
        else:
            park = Park.objects.get(site_code=site_code)
            if not park:
                print("Matching park site not found. Please try a different site code")
                return False
            else:
                print(f"Exporting photos from {park.name} with missing titles...")

                photos_df = pd.DataFrame(Photo.objects.filter(
                    park__site_code=site_code,
                    title_final='',
                    status__in=['LV']
                ).values(
                    'park__name',
                    'main_image_url',
                    'revisedphoto__main_image_url'
                ))

                if photos_df.shape[0] == 0:
                    print('No photos from this site without a title.')
                else:
                    photos_df['main_image_url'] = photos_df['revisedphoto__main_image_url'].combine_first(photos_df['main_image_url'])
                    photos_df.drop(columns=['revisedphoto__main_image_url'], inplace=True)
                    photos_df['main_image_url'] = '=HYPERLINK("' + f'https://{settings.AWS_PUBLIC_BUCKET_NAME}.s3.amazonaws.com/' + photos_df['main_image_url'] + f'", "' + photos_df['main_image_url'] + '")'

                    photos_df['title'] = ''
                    photos_df['comments'] = ''
                    photos_df.rename(columns={'park__name': 'park_name'}, inplace=True)
                    print(photos_df)

                    today = datetime.datetime.now().date().strftime('%Y%m%d')

                    photos_df.to_excel(os.path.join(settings.BASE_DIR, 'data', f'{site_code}_missing_titles_{today}.xlsx'), index=False)
