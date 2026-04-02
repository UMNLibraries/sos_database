import pandas as pd

from django.core.management.base import BaseCommand

from apps.park.models import Park, DOIFlag, FLAG_TYPE_CHOICES

# from django.conf import settings

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('-f', '--infile', type=str,
                        help='Path to CSV file of dumped sites.')

    def handle(self, *args, **kwargs):
        infile = kwargs['infile']
        if not infile:
            print('Missing input CSV path. Please specify with --infile.')
        else:

            parks = Park.objects.all()
            status_df = pd.read_csv(infile)
            
            #Make column names uppercase for easier matching
            status_df.columns = status_df.columns.str.upper().str.replace(' ', '')

            print(status_df)

            for park in parks:
                df_row = status_df[status_df['PARKCODE'] == park.site_code]
                if df_row.shape[0] > 0:
                    # print(df_row.iloc[0])
                    for choice in FLAG_TYPE_CHOICES:
                        if choice[1] != 'Other':
                            value = df_row.iloc[0][choice[1].upper().replace(' ', '')]
                            if value == 'x':
                                flag, created = DOIFlag.objects.get_or_create(
                                    park=park,
                                    flag_type=choice[0]
                                )
                                print(flag)
