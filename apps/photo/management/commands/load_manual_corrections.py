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

            # TODO: Make sure ManualCorrection is a CSVModel
            mapping = {
                # model: csv
                'zoon_subject_id': 'zoon_subject_id',
                'zoon_workflow_id': 'zoon_workflow_id',
                'bool_covenant': 'bool_covenant',
                'covenant_text': 'covenant_text',
                'addition': 'addition',
                'lot': 'lot',
                'block': 'block',
                'map_book': 'map_book',
                'map_book_page': 'map_book_page',
                'seller': 'seller',
                'buyer': 'buyer',
                'deed_date': 'deed_date',
                'date_added': 'date_added',
                'date_updated': 'date_updated',
                'match_type': 'match_type',
                'comments': 'comments',
            }

            insert_count = ManualCorrection.objects.from_csv(
                infile, mapping=mapping)
            print("{} records inserted".format(insert_count))

            management.call_command(
                'connect_manual_corrections', workflow=workflow_name)
