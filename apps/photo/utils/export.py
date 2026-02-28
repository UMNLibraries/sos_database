import os
import datetime
import pandas as pd
from django.db.models import Func, FloatField
from django.contrib.postgres.aggregates import ArrayAgg
from django.conf import settings
from django.apps import apps

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
        'revisedphoto__main_image_url',
        'thumb_url',
        'revisedphoto__thumb_url',
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

    # Use corrected photo/thumb if revised one present
    public_df['main_image_url'] = public_df['revisedphoto__main_image_url'].combine_first(public_df['main_image_url'])
    public_df['thumb_url'] = public_df['revisedphoto__thumb_url'].combine_first(public_df['thumb_url'])

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

    # final_df.to_csv(PUBLIC_MANIFEST_PATH, index=False)

    return final_df

    # from apps.photo.utils.export import build_public_manifest
    # build_public_manifest()


def dump_cx_model_backups(app_name, model_name):
    model = apps.get_model(app_name, model_name)

    objs = model.objects.all().values()

    df = pd.DataFrame(objs)
    if df.shape[0] == 0:
        print (f"No {model_name} records found.")
        return False
    df.rename(columns={'id': 'db_id'}, inplace=True)

    # Drop primary key of photo foreign key because it will have changed on re-import
    df.drop(
        columns=['photo_id'], inplace=True, errors='ignore')

    print(df)
    # outfile = save_backup_file(df, model_name.lower())

    return df


def save_backup_file(df, filename_root):
    backup_dir = os.path.join(settings.BASE_DIR, 'data', 'backup')
    os.makedirs(backup_dir, exist_ok=True)

    outfile = os.path.join(backup_dir,
                            f'{filename_root}_{datetime.datetime.now().date()}.csv')
    # print(outfile)
    df.to_csv(outfile, index=False)

    return outfile


def fill_final_value(attr):
    '''Find objs without a _final value set and fill them with initial import values'''

    update_objs = []

    attr_filter = {
        f'{attr}_final__isnull': True,
    }

    for p in Photo.objects.filter(**attr_filter):
        # Set final value to initial value
        setattr(p, f"{attr}_final", getattr(p, attr))
        update_objs.append(p)

    Photo.objects.bulk_update(update_objs, [f'{attr}_final']) 