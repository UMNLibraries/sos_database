import csv

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point

from apps.park.models import Park, State, SiteType


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

                self.populate_states(site_data)
                self.populate_site_types(site_data)
                self.populate_sites(site_data)
