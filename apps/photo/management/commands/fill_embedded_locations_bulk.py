import os
import datetime
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point

from apps.photo.models import Photo
from apps.photo.utils.box import get_box_client, get_box_file_as_tempfile
from apps.photo.utils.image_processing import get_gps_info


class Command(BaseCommand):
    '''Check existing Photo objects for embedded location info and add to model if found.'''

    box = get_box_client()

    def add_arguments(self, parser):

        parser.add_argument('-d', '--start-date', type=datetime.date.fromisoformat, default=None,
                        help='Only check Photo objects uploaded on or after this date (YYYY-MM-DD)')

    def get_location_info(self, box_id):
        infile = get_box_file_as_tempfile(self.box, box_id)
        location_info = get_gps_info(infile)
        os.remove(infile)
        if location_info:
            return Point(float(location_info['longitude']), float(location_info['latitude']))
        
        return False

    def handle(self, *args, **kwargs):
        '''Box is slow, so saving one row at a time is not really slower, and you don't lose partial progress'''
        # update_objs = []

        filter_kwargs = {
            'location_embedded__isnull': True
        }

        start_date = kwargs['start_date']
        
        if start_date:
            filter_kwargs['dt_imported__gte'] = start_date

        for p in Photo.objects.filter(**filter_kwargs):
            embedded_point = self.get_location_info(p.box_id)
            if embedded_point:
                print(p.photo_file_name, embedded_point)
                p.location_embedded = embedded_point
                p.save()
                # update_objs.append(p)

        # Photo.objects.bulk_update(update_objs, ['location_embedded'])
