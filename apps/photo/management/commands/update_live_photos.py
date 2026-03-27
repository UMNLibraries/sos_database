import os
import time
import boto3
import pandas as pd
from multiprocessing.pool import ThreadPool

from django.core.management.base import BaseCommand

from apps.photo.models import Photo
from sos_database.storage_backends import PrivateMediaStorage
from apps.photo.utils.image_processing import get_current_s3_matches, copy_image_to_public_s3

from django.conf import settings

class Command(BaseCommand):
    '''Find photos that are in DB but have not been moved to S3, then copy from Box to private storage'''

    if hasattr(settings, 'AWS_PROFILE_NAME'):
        session = boto3.Session(profile_name=settings.AWS_PROFILE_NAME)
    else:
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
    
    s3 = session.client('s3', region_name='us-east-2')
    public_bucket = settings.AWS_PUBLIC_BUCKET_NAME

    upload_log = []
    delete_log = []

    min_thread_time = None

    def add_arguments(self, parser):
    
        parser.add_argument('-p', '--pool', type=int, default=8,
                            help='How many threads to use? (Default is 8)')

        parser.add_argument('-m', '--mintime', type=float, default=0.3,
                            help='What is the minimum time to execute each thread (rate limit) in seconds (Default is 0.3)')

    def prepare_manifest(self, main_or_thumb, live_photo_objs_df, current_s3_df):

        if main_or_thumb == 'main':
            private_s3_key_col = 'main_image_url'
            public_s3_key_col = 's3_main_image_url'
            drop_col = 'thumb_url'
        elif main_or_thumb == 'thumb':
            private_s3_key_col = 'thumb_url'
            public_s3_key_col = 's3_thumb_url'
            drop_col = 'main_image_url'
        else:
            return False
        
        image_join_df = live_photo_objs_df.drop(columns=[drop_col]).merge(
            current_s3_df,
            how="outer",
            left_on=private_s3_key_col,
            right_on=public_s3_key_col,
            indicator=True
        )

        images_to_upload = image_join_df[
            image_join_df['_merge'] == 'left_only'
        ].rename(columns={
            private_s3_key_col: 'public_s3_key',  # Note that this seems reversed, but since this doesn't exist yet we need this for the future public value
        })
        images_to_upload['private_s3_key'] = images_to_upload['public_s3_key'].apply(lambda x: os.path.join(PrivateMediaStorage.location, x))  # prepending prefix for actual private key location

        images_to_delete = image_join_df[image_join_df['_merge'] == 'right_only']
        images_to_delete.rename(columns={public_s3_key_col: 'public_s3_key'}, inplace=True)

        print(f"Found {images_to_upload.shape[0]} {main_or_thumb} images to upload and {images_to_delete.shape[0]} {main_or_thumb} images to delete.")

        return images_to_upload, images_to_delete
    
    def wait_maybe(self, start_time):
        # If necessary, wait before completing
        if self.min_thread_time > 0:
            elapsed = time.time() - start_time
            time_remaining = self.min_thread_time - elapsed
            if time_remaining > 0:
                print(f'Pausing {round(time_remaining, 3)} seconds')
                time.sleep(time_remaining)

    def send_to_s3(self, row):

        start_time = time.time()

        row['bool_upload'] = copy_image_to_public_s3(self.s3, settings.AWS_STORAGE_BUCKET_NAME, row['private_s3_key'], self.public_bucket, row['public_s3_key'])

        self.upload_log.append(row)
        self.wait_maybe(start_time)
        return row

    def delete_s3_image(self, row):

        start_time = time.time()

        try:
            response = self.s3.delete_object(
                Bucket=self.public_bucket,
                Key=row['public_s3_key']
            )
            print(f"'{row['public_s3_key']}' deleted successfully. Response: {response['ResponseMetadata']['HTTPStatusCode']}")
            row['bool_delete'] = True
        except Exception as e:
            print(f"Error deleting file: {e}")
            row['bool_delete'] = True

        self.delete_log.append(row)
        self.wait_maybe(start_time)
        return row

    def update_django_photo_status(self, current_main_images, current_thumbs, live_photo_objs_df):
        '''Check whether Photo objects that are being worked on have been successfully uploaded.
        Only update status to "Approved" in cases where both main image and thumbnail have
        been successfully uploaded'''
        
        main_image_uploads = [row['public_s3_key'] for row in self.upload_log if 'thumbs' not in row['public_s3_key'] and row['bool_upload'] == True]
        main_images_public = current_main_images + main_image_uploads
        main_images_public_df = pd.DataFrame(main_images_public, columns=['main_image_public'])

        thumb_uploads = [row['public_s3_key'] for row in self.upload_log if 'thumbs' in row['public_s3_key'] and row['bool_upload'] == True]
        thumbs_public = current_thumbs + thumb_uploads
        thumbs_public_df = pd.DataFrame(thumbs_public, columns=['thumb_public'])

        live_photo_objs_df = live_photo_objs_df.merge(
            main_images_public_df,
            how="left",
            left_on="main_image_url",
            right_on="main_image_public"
        ).merge(
            thumbs_public_df,
            how="left",
            left_on="thumb_url",
            right_on="thumb_public"
        )

        successful_uploads_df = live_photo_objs_df[
            (~live_photo_objs_df['main_image_public'].isna()) & (~live_photo_objs_df['thumb_public'].isna())
        ]

        objs_to_update = Photo.objects.filter(pk__in=successful_uploads_df['id'].to_list(), status='AP')
        print(f"Setting {objs_to_update.count()} Photo objects to 'Approved'...")

        objs_to_update.update(status="LV")

    def handle(self, *args, **kwargs):

        self.min_thread_time = kwargs['mintime']
        self.num_threads = kwargs['pool']

        current_thumbs = get_current_s3_matches(self.s3, self.public_bucket, 'thumbs')
        current_main_images = get_current_s3_matches(self.s3, self.public_bucket, 'images')

        current_thumbs_df = pd.DataFrame(current_thumbs, columns=['s3_thumb_url'])
        current_main_images_df = pd.DataFrame(current_main_images, columns=['s3_main_image_url'])

        print(f"Found {len(current_main_images)} main images and {len(current_thumbs)} thumbnails already on public S3.")

        live_photo_objs_df = pd.DataFrame(Photo.objects.filter(status__in=['LV', 'AP'], scope='IN').values(
            'id', 'thumb_url', 'main_image_url'
        ))

        # Main images
        # TODO: Remove head()
        main_images_to_upload, main_images_to_delete = self.prepare_manifest('main', live_photo_objs_df.copy(), current_main_images_df)
        
        if main_images_to_upload.shape[0] > 0:
            print("Uploading main images...")

            pool = ThreadPool(processes=self.num_threads)
            pool.map(self.send_to_s3, main_images_to_upload.head().to_dict('records'))

        # Thumbnails
        thumbnails_to_upload, thumbnails_to_delete = self.prepare_manifest('thumb', live_photo_objs_df, current_thumbs_df)

        if thumbnails_to_upload.shape[0] > 0:
            print("Uploading thumbnails...")
            pool = ThreadPool(processes=self.num_threads)
            pool.map(self.send_to_s3, thumbnails_to_upload.head().to_dict('records'))

        # Delete routine
        # TODO: Remove head()
        if main_images_to_delete.shape[0] > 0:
            print("Deleting main images...")
            pool = ThreadPool(processes=self.num_threads)
            pool.map(self.delete_s3_image, main_images_to_delete.head().to_dict('records'))

        if main_images_to_delete.shape[0] > 0:
            print("Deleting thumbnails...")
            pool = ThreadPool(processes=self.num_threads)
            pool.map(self.delete_s3_image, thumbnails_to_delete.head().to_dict('records'))

        # Updating status of photo records
        self.update_django_photo_status(current_main_images, current_thumbs, live_photo_objs_df)
