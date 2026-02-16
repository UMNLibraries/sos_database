import pandas as pd
from django.contrib.postgres.aggregates import ArrayAgg

from apps.photo.models import Photo

def build_public_manifest():
    '''Create public manifest CSV matching legacy format using Django model'''

    photos = Photo.objects.filter(
        scope='IN',
        status__in=['LV', 'AP']
    ).annotate(
        states=ArrayAgg('park__states__name'),
        site_type=ArrayAgg('park__site_types__name'),
    ).values(
        'park__site_code',
        'park__name',
        # 'park__site_types__name',
        'site_type',
        'photo_file_name',
        'title_final',
        'date_taken',
        'main_image_url',
        'thumb_url',
        'location_final',
        # 'location_final__point__y',
        # 'location_final__point__x',
        'location_type_final',
        'states',
        # 'park__states__name',
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
    public_df['states'] = public_df['states'].apply(lambda x: '|'.join(x))

    # Separate site types with pipes
    public_df['site_type'] = public_df['site_type'].apply(lambda x: '|'.join(x))

    # TODO: Extract lat/lng from locations

    # Sort by site_code
    public_df = public_df.sort_values('site_code')

    print(public_df[['main_image_url']].drop_duplicates())
    print(public_df)

    # from apps.photo.utils.export import build_public_manifest
    # build_public_manifest()

    # final values we're shooting for...
    # public_fields = [
        # 'site_code',
        # 'site_name',
        # 'site_type',
        # 'file_name',
        # 'title',
        # 'date_taken',
        # 'main_image_url',
        # 'thumb_url',
        # 'longitude',
        # 'latitude',
        # 'location_source',
        # 'states',
        # 'website',
    # ]

    # public_df = pd.read_csv(self.logging_manifest_path)
    # print(public_df)

    # # Join to geo info
    # geo_df = pd.read_csv('data/NPS_latlong_alpha_points.csv')
    # public_df = public_df.drop(columns=[
    #     'longitude',
    #     'latitude',
    #     'location_source',
    #     # 'website',
    # ]).merge(
    #     geo_df[[
    #         'alpha_code',
    #         'longitude',
    #         'latitude',
    #         'location_source',
    #         'states',
    #         'website',
    #     ]],
    #     how="left",
    #     left_on="box_foldername",
    #     right_on="alpha_code"
    # )

    # public_df = public_df[public_df['s3_error'] == False][[
    #     'box_foldername',
    #     'park_name',
    #     'type',
    #     'photo_file_name',
    #     'title',
    #     'date_taken',
    #     'main_image_url',
    #     'thumb_url',
    #     'longitude',
    #     'latitude',
    #     'location_source',
    #     'states',
    #     'website',
    # ]].rename(
    #     columns={
    #         'box_foldername': 'site_code',
    #         'park_name': 'site_name',
    #         'type': 'site_type',
    #         'photo_file_name': 'file_name',
    #     }
    # ).sort_values('site_code')
    
    # public_df.to_csv(self.public_manifest_path, index=False)

    # return public_df
