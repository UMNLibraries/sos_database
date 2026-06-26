import os
import pandas as pd

from django.core.management.base import BaseCommand

from apps.photo.models import Photo, SCOPE_CHOICES

from django.conf import settings


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        photos_df = pd.DataFrame(Photo.objects.filter(
            park__site_code='INDE',
            title_final='',
            status__in=['LV']
        ).values(
            'park__name',
            'main_image_url',
            'revisedphoto__main_image_url'
        ))
        photos_df['main_image_url'] = photos_df['revisedphoto__main_image_url'].combine_first(photos_df['main_image_url'])
        photos_df.drop(columns=['revisedphoto__main_image_url'], inplace=True)
        photos_df['main_image_url'] = '=HYPERLINK("' + f'https://{settings.AWS_PUBLIC_BUCKET_NAME}.s3.amazonaws.com/' + photos_df['main_image_url'] + f'", "' + photos_df['main_image_url'] + '")'

        photos_df['title'] = ''
        photos_df['comments'] = ''
        print(photos_df)

        photos_df.to_excel(os.path.join(settings.BASE_DIR, 'data', 'INDE_missing_titles.xlsx'), index=False)
        
