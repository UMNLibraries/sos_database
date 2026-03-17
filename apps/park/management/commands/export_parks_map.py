import os
import boto3
from django.core.management.base import BaseCommand

from apps.photo.utils.export import build_map_gdf, data_file_to_s3

from django.conf import settings

class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument('-u', '--upload', action='store_true',
                        help='Upload result to S3 bucket.')

    def handle(self, *args, **kwargs):
        KEY_PATH = os.path.join('data', 'nps_site_photo_counts.geojson')
        LOCAL_GEOJSON_PATH = os.path.join(settings.BASE_DIR, KEY_PATH)

        gdf = build_map_gdf()

        # Check that there is JSON here
        if gdf.shape[0] > 10:
            pass
        else:
            print('WARNING: GeoJSON looks suspicious. Exiting without overwriting file.')
            return False

        gdf.to_file(LOCAL_GEOJSON_PATH, driver="GeoJSON")

        if kwargs['upload']:
            print('Uploading to S3 data directory...')
            
            if hasattr(settings, 'AWS_PROFILE_NAME'):
                session = boto3.Session(profile_name=settings.AWS_PROFILE_NAME)
            else:
                session = boto3.Session(
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME
                )
            s3 = session.client('s3', region_name='us-east-2')

            data_file_to_s3(s3, LOCAL_GEOJSON_PATH, settings.AWS_STORAGE_BUCKET_NAME, KEY_PATH, 'public-read')
