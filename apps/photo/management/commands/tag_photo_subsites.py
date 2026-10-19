import csv
from slugify import slugify
import pandas as pd

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point

from apps.park.models import Park, SubSite
from apps.photo.models import Photo
from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df

from django.conf import settings

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('-f', '--infile', type=str,
                        help='Path to CSV file of dumped sites.')

    def ss_slug(self, site_code, subsite_name):
        return f"{site_code}-{slugify(subsite_name)}"

    def handle(self, *args, **kwargs):
        infile = kwargs['infile']
        if not infile:
            print('Missing input CSV path. Please specify with --infile.')
        else:

            df = pd.read_csv(infile, dtype=str)

            subsite_combos = df[['site_code', 'subsite']].drop_duplicates().to_dict(orient="records")
            print(subsite_combos)
            subsite_lookup = {}
            for ss in subsite_combos:
                park_obj = Park.objects.get(site_code=ss['site_code'])

                subsite, subsite_created = SubSite.objects.get_or_create(
                    park_id=park_obj.pk,
                    name=ss['subsite'],
                )

                # make lookup to SubSite pk for assignment to photos
                subsite_lookup[self.ss_slug(ss['site_code'], ss['subsite'])] = subsite.pk

            print(subsite_lookup)

            photo_filenames = df['file_name'].drop_duplicates().to_list()
            print(f'Found {len(photo_filenames)} photo filenames in CSV.')

            photo_objs = Photo.objects.filter(
                photo_file_name__in=photo_filenames
            ).select_related('park')

            print(f'Found {photo_objs.count()} matching photo filenames in database.')

            update_photos = []

            for p in photo_objs:
                subsite_match = df[(df['file_name'] == p.photo_file_name) & (df['site_code'] == p.park.site_code)].iloc[0]
                p.subsite_id = subsite_lookup[self.ss_slug(subsite_match['site_code'], subsite_match['subsite'])]
                update_photos.append(p)

            print(f"Setting SubSite on {len(update_photos)} Photo instances...")
            Photo.objects.bulk_update(update_photos, fields=['subsite_id'])


            

