import os
from django.core.management.base import BaseCommand

from apps.photo.utils.export import build_map_gdf

from django.conf import settings

class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        GEOJSON_PATH = os.path.join(settings.BASE_DIR, 'data', 'site_photo_counts.geojson')

        gdf = build_map_gdf()
        gdf.to_file(GEOJSON_PATH, driver="GeoJSON")