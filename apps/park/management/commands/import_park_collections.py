import csv

from django.core.management.base import BaseCommand
from apps.park.models import ParkCollection, Park

from django.conf import settings

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('-f', '--infile', type=str,
                        help='Path to CSV file of dumped sites.')
        
        # parser.add_argument('-d', '--delete', action='store_true',
        #                 help='Delete existing records before import.')

    def handle(self, *args, **kwargs):
        infile = kwargs['infile']
        # clear_first = kwargs['delete']
        if not infile:
            print('Missing input CSV path. Please specify with --infile.')
        else:

            # if clear_first:
            #     self.clear_all()

            with open(infile, mode='r') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                pc_data = list(csv_reader)

                for pc_row in pc_data:
                    if pc_row['how are we feeling?'] == 'Approved':
                        print(pc_row['collection_name'])

                        pc, pc_created = ParkCollection.objects.get_or_create(
                            name=pc_row['collection_name'],
                            collection_code=pc_row['collection_code'],
                        )

                        member_codes = [code.strip() for code in pc_row['member_codes'].split(',')]

                        member_parks = Park.objects.filter(site_code__in=member_codes)
                        for m in member_parks:
                            print(m)
                            m.collections.add(pc)
