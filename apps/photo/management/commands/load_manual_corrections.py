import pandas as pd

from django.core import management
from django.core.management.base import BaseCommand

from apps.photo.models import ManualCorrection


class Command(BaseCommand):
    '''Load a downloaded CSV of ManualCorrection objects into the database and join to Photos.'''

    def add_arguments(self, parser):

        parser.add_argument('-f', '--infile', type=str,
                            help='Path to CSV file of dumped corrections')

    def handle(self, *args, **kwargs):
        infile = kwargs['infile']
        
        if not infile:
            print('Missing infile path. Please specify with --infile.')
            return False
        else:

            print("Loading manual corrections...")

            mapping = {
                # model_value: csv_value
                'photo_file_name': 'photo_file_name',
                'title': 'title',
                'additional_notes': 'additional_notes',
                'location': 'location',
                'location_type': 'location_type',
                'comments': 'comments',
                'date_created': 'date_created',
                'date_modified': 'date_modified',
            }

            insert_count = ManualCorrection.objects.from_csv(
                infile, mapping=mapping)
            print("{} records inserted".format(insert_count))

            management.call_command(
                'connect_manual_corrections')
