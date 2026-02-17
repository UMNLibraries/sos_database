from django.core.management.base import BaseCommand

from apps.photo.models import Photo, SCOPE_CHOICES, LOCATION_TYPE_CHOICES


class Command(BaseCommand):
    '''Write initial values to _final fields from original values. Probably doesn't need to be run again.'''

    def fill_final_value(self, attr):

        update_objs = []

        attr_filter = {
            f'{attr}_final__isnull': True,
        }

        for p in Photo.objects.filter(**attr_filter):
            # Set final value to initial value
            setattr(p, f"{attr}_final", getattr(p, attr))
            update_objs.append(p)

        Photo.objects.bulk_update(update_objs, [f'{attr}_final']) 

    def handle(self, *args, **kwargs):
        for attr in ['title', 'additional_notes', 'location', 'location_type']:
            self.fill_final_value(attr)
