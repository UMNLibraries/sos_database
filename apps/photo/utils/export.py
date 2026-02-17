import os
import pandas as pd
from django.db.models import Func, FloatField
from django.contrib.postgres.aggregates import ArrayAgg
from django.conf import settings

from apps.photo.models import Photo

def build_public_manifest():
    '''Create public manifest CSV matching legacy format using Django model'''

    PUBLIC_MANIFEST_PATH = os.path.join(settings.BASE_DIR, 'data', 'public_manifest_main_TEST.csv')

    photos = Photo.objects.filter(
        scope='IN',
        status__in=['LV', 'AP']
    ).annotate(
        states=ArrayAgg('park__states__name'),
        site_type=ArrayAgg('park__site_types__name'),
        longitude=Func('location_final', function='ST_X', output_field=FloatField()),
        latitude=Func('location_final', function='ST_Y', output_field=FloatField()),
    ).values(
        'park__site_code',
        'park__name',
        'site_type',
        'photo_file_name',
        'title_final',
        'date_taken',
        'main_image_url',
        'thumb_url',
        'longitude',
        'latitude',
        'location_type_final',
        'states',
        'park__website',
    )

    print(photos)

    public_df = pd.DataFrame(photos)
    public_df = public_df.rename(columns={
        'park__site_code': 'site_code',
        'park__name': 'site_name',
        'photo_file_name': 'file_name',
        'title_final': 'title',
        'location_type_final': 'location_source',
        'park__website': 'website',
    })
    
    # Separate states with pipes
    public_df['states'] = public_df['states'].apply(lambda x: '|'.join(list(set(x))))

    # Separate site types with pipes
    public_df['site_type'] = public_df['site_type'].apply(lambda x: '|'.join(list(set(x))))

    # Sort by site_code
    public_df = public_df.sort_values('site_code')

    print(public_df[['main_image_url']].drop_duplicates())
    print(public_df)

    # final values we're shooting for...
    public_fields = [
        'site_code',
        'site_name',
        'site_type',
        'file_name',
        'title',
        'date_taken',
        'main_image_url',
        'thumb_url',
        'longitude',
        'latitude',
        'location_source',
        'states',
        'website',
    ]
    

    final_df = public_df[public_fields]
    print(final_df)

    final_df.to_csv(PUBLIC_MANIFEST_PATH, index=False)

    return final_df

    # from apps.photo.utils.export import build_public_manifest
    # build_public_manifest()
