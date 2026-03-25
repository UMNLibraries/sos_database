import os
import pandas as pd

from django.core.management.base import BaseCommand
from django.db.models import Count

from django.conf import settings

from apps.park.models import Park
from apps.photo.models import Photo

class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        photos_by_park = Photo.objects.filter(status='RD').values('park__id', 'park__name').annotate(photo_count=Count("id"))

        df = pd.DataFrame(photos_by_park)
        df = df[df['photo_count'] > 0].reset_index().sort_values('photo_count', ascending=False)
        df['park_link'] = 'http://3.209.246.30/admin/photo/photo/?status__exact=RD&park__id__exact=' + df['park__id'].astype(str)

        print(df)
        out_path = os.path.join(settings.BASE_DIR, 'data', 'moderation_sites.csv')
        df.to_csv(out_path, index=False)



