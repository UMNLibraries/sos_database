import pandas as pd
import numpy as np

from django.core.management.base import BaseCommand

from apps.photo.models import Photo, ManualCorrection
from apps.park.models import Park

from django.conf import settings


class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument('-f', '--infile', type=str,
                            help='Path to CSV file of manual titles')

    def handle(self, *args, **kwargs):

        infile = kwargs['infile']
        
        if not infile:
            print("Missing infile path. Please specify with --infile. Infile should be a CSV with fields 'park_name', 'main_image_url', and 'title'")
            return False
        else:
            print("Loading custom titles from spreadsheet...")
            titles_df = pd.read_csv(infile)

            parks_df = pd.DataFrame(Park.objects.filter(
                name__in=titles_df['park_name'].drop_duplicates().to_list()
            ).values('id', 'name', 'site_code'))
            parks_df.rename(columns={'id': 'park_dbid'}, inplace=True)
            print(parks_df)

            # Only work on rows with parks in the database and valid titles
            valid_titles_df = titles_df[
                (titles_df['park_name'].isin(parks_df.name.drop_duplicates().to_list()))
                & (~titles_df['title'].isin(['', None, np.nan]))
                & (~titles_df['main_image_url'].isin(['', None, np.nan]))
            ]
            valid_titles_df = valid_titles_df.merge(
                parks_df,
                how="left",
                left_on="park_name",
                right_on="name"
            )

            photos_to_update = []
            mcs_to_create = []
            for k, row in valid_titles_df.iterrows():
                try:
                    matching_photo = Photo.objects.get(
                        park_id=row['park_dbid'],
                        main_image_url=row['main_image_url'],
                        manualcorrection__isnull=True
                    )
                    matching_photo.title_final = row['title']

                    mc = ManualCorrection(
                        photo_id=matching_photo.id,
                        photo_file_name=matching_photo.photo_file_name,
                        title=row['title']
                    )

                    mcs_to_create.append(mc)
                    photos_to_update.append(matching_photo)
                except Photo.DoesNotExist:
                    print(f"Matching photo not found or already has manual correction: {row['main_image_url']}")

            if len(mcs_to_create) > 0:
                print(f"Creating {len(mcs_to_create)} manual corrections with new titles...")
                # Create ManualCorrection objects
                created_mcs = ManualCorrection.objects.bulk_create(mcs_to_create)

                # Bulk update photo objects to avoid running save methods individually
                Photo.objects.bulk_update(photos_to_update, ['title_final'])
            else:
                print("No manual corrections to create.")
