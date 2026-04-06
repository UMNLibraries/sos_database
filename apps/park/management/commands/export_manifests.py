import os
import boto3

from django.core.management.base import BaseCommand

from apps.photo.utils.export import build_public_manifest, data_file_to_s3

from django.conf import settings


class Command(BaseCommand):

    DATA_DIR = os.path.join(settings.BASE_DIR, 'data')
    SITE_MANIFEST_DIR = os.path.join(DATA_DIR, 'site_manifests')
    S3_DATA_DIR = os.path.join('sos-public-viewer', 'data')
    s3 = None

    def add_arguments(self, parser):

        parser.add_argument('-u', '--upload', action='store_true',
                        help='Upload result to S3 bucket.')
        
    def initialize_s3(self):
        if hasattr(settings, 'AWS_PROFILE_NAME'):
            session = boto3.Session(profile_name=settings.AWS_PROFILE_NAME)
        else:
            session = boto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
        self.s3 = session.client('s3', region_name='us-east-2')
        return self.s3
    
    def handle(self, *args, **kwargs):
        print(f"Exporting main manifest...")
        main_manifest_df = build_public_manifest()
        print(f"Found {main_manifest_df.shape[0]} live images.")
        main_manifest_path = os.path.join(self.DATA_DIR, 'public_manifest_main.csv')
        main_manifest_excel_path = os.path.join(self.DATA_DIR, 'sos_public_manifest.xlsx')
        main_manifest_df.to_csv(main_manifest_path, index=False)
        main_manifest_df.to_excel(main_manifest_excel_path, index=False)

        if kwargs['upload']:
            self.initialize_s3()
            print('Uploading to S3 data directory...')
            main_manifest_s3_path = os.path.join(self.S3_DATA_DIR, 'public_manifest_main.csv')
            data_file_to_s3(self.s3, main_manifest_path, settings.SOS_VIEWER_S3_BUCKET, main_manifest_s3_path, 'public-read', 'GLACIER_IR', 'text/csv')
            
            main_manifest_excel_s3_path = os.path.join(self.S3_DATA_DIR, 'sos_public_manifest.xlsx')
            data_file_to_s3(self.s3, main_manifest_excel_path, settings.SOS_VIEWER_S3_BUCKET, main_manifest_excel_s3_path, 'public-read', 'GLACIER_IR', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # Slice main manifest into site-specific dfs
        site_codes = main_manifest_df['site_code'].drop_duplicates().to_list()
        print(f"Exporting {len(site_codes)} site manifests...")

        os.makedirs(self.SITE_MANIFEST_DIR, exist_ok=True)

        for site_code in site_codes:
            site_manifest_df = main_manifest_df[main_manifest_df['site_code'] == site_code]

            site_manifest_path = os.path.join(self.SITE_MANIFEST_DIR, f'sos_public_manifest_{site_code}.xlsx')
            site_manifest_df.to_excel(site_manifest_path, index=False)

            if kwargs['upload']:
                site_manifest_s3_path = os.path.join(self.S3_DATA_DIR, 'site_manifests', f'sos_public_manifest_{site_code}.xlsx')
                data_file_to_s3(self.s3, site_manifest_path, settings.SOS_VIEWER_S3_BUCKET, site_manifest_s3_path, 'public-read', 'GLACIER_IR', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # TODO: Cleanup of sites with no photos

