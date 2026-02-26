from django.core.management.base import BaseCommand

from apps.photo.models import Photo, SCOPE_CHOICES, LOCATION_TYPE_CHOICES
from apps.photo.utils.export import fill_final_value


class Command(BaseCommand):
    '''Write initial values to _final fields from original values. Probably doesn't need to be run again.'''

    def handle(self, *args, **kwargs):
        for attr in ['title', 'additional_notes']:
            fill_final_value(attr)
