import csv
import pandas as pd

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point

from apps.park.models import Park, State, SiteType
from apps.photo.utils.gsheets import gsheets_login, get_gsheets_df

from django.conf import settings

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('-f', '--infile', type=str,
                        help='Path to CSV file of dumped sites.')
        
        parser.add_argument('-d', '--delete', action='store_true',
                        help='Delete existing records before import.')
        
    def clear_all(self):
        State.objects.all().delete()
        SiteType.objects.all().delete()
        Park.objects.all().delete()

    def add_box_folder_ids(self, site_data):
        """ TODO: Box folder IDs are found in a separate sheet, at least for round 1. Not sure yet how to collect folder names for post-batch-1 sites, of which there are more than 100."""

        service = gsheets_login()
        supplemental_df = get_gsheets_df(service, settings.GSHEETS_PHOTOS_IMPORT_ID, settings.GSHEETS_BOX_FOLDER_IMPORT_SHEET_NAME)

        # Get Box folder Ids
        site_data_df = pd.DataFrame(site_data)
        site_data_df = site_data_df.merge(
            supplemental_df[['folder name', 'folder link']],
            how="left",
            left_on="alpha_code",
            right_on="folder name"
        ).fillna(value='')
        site_data_df['box_folder_id'] = site_data_df['folder link'].str.replace('https://umn.app.box.com/folder/', '')

        return site_data_df.to_dict(orient='records')
        
    def populate_states(self, site_data):
        all_states = []
        for row in site_data:
            row_states = row['states'].split('|')
            all_states += row_states
        all_states = sorted(list(set(all_states)))

        for state in all_states:
            state, state_created = State.objects.get_or_create(
                name=state
            )

    def populate_site_types(self, site_data):
        all_types = []
        for row in site_data:
            row_types = row['type'].split('|')
            all_types += row_types
        all_types = sorted(list(set(all_types)))

        for site_type in all_types:
            site_type, type_created = SiteType.objects.get_or_create(
                name=site_type
            )

    def populate_sites(self, site_data):

        for row in site_data:

            centerpoint = Point(float(row['longitude']), float(row['latitude']))

            park, park_created = Park.objects.get_or_create(
                name=row['name'],
                site_code=row['alpha_code'],
                website=row['website'],
                box_folder_id=row['box_folder_id'],
                centerpoint=centerpoint
            )

            states = State.objects.filter(name__in=row['states'].split('|'))
            for state in states:
                park.states.add(state)
            types = SiteType.objects.filter(name__in=row['type'].split('|'))
            for site_type in types:
                park.site_types.add(site_type)

    def handle(self, *args, **kwargs):
        infile = kwargs['infile']
        clear_first = kwargs['delete']
        if not infile:
            print('Missing input CSV path. Please specify with --infile.')
        else:

            if clear_first:
                self.clear_all()

            with open(infile, mode='r') as csv_file:
                # Create a DictReader object
                csv_reader = csv.DictReader(csv_file)
                site_data = list(csv_reader)
                site_data = self.add_box_folder_ids(site_data)

                self.populate_states(site_data)
                self.populate_site_types(site_data)
                self.populate_sites(site_data)
