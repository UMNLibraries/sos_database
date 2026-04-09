import os
import json
import datetime
import boto3
from django.core.management.base import BaseCommand

from apps.photo.utils.export import build_park_summary, data_file_to_s3

from django.conf import settings

class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument('-u', '--upload', action='store_true',
                        help='Upload result to S3 bucket.')

    def handle(self, *args, **kwargs):
        KEY_PATH = os.path.join('data', 'nps_site_photo_counts.csv')
        S3_KEY = os.path.join('sos-public-viewer', KEY_PATH)
        LOCAL_CSV_PATH = os.path.join(settings.BASE_DIR, KEY_PATH)

        df = build_park_summary()

        # Check that there is JSON here
        if df.shape[0] > 10:
            pass
        else:
            print('WARNING: GeoJSON looks suspicious. Exiting without overwriting file.')
            return False

        # Create timestamped file
        df['dt_updated'] = datetime.datetime.now().isoformat()
        df.to_csv(LOCAL_CSV_PATH, index=False)

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

            data_file_to_s3(s3, LOCAL_CSV_PATH, settings.SOS_VIEWER_S3_BUCKET, S3_KEY, 'public-read', 'STANDARD', 'text/csv')
