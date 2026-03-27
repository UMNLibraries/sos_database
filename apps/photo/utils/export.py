import os
import datetime
import pandas as pd
import geopandas as gpd
from django.db.models import Func, FloatField, CharField
from django.contrib.postgres.aggregates import ArrayAgg
from django.conf import settings
from django.apps import apps

from apps.photo.models import Photo, LOCATION_TYPE_CHOICES
from apps.park.models import Park


def build_public_manifest():
    '''Create public manifest CSV matching legacy format using Django model'''

    photos = Photo.objects.filter(
        scope='IN',
        status__in=['LV']
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

    # Prepend image URL
    public_df['main_image_url'] = settings.SOS_VIEWER_URL_ROOT + public_df['main_image_url']
    public_df['thumb_url'] = settings.SOS_VIEWER_URL_ROOT + public_df['thumb_url']

    # Convert LOCATION_TYPE_CHOICES
    public_df['location_source'] = public_df['location_source'].apply(lambda x: dict(LOCATION_TYPE_CHOICES)[x])

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

    return final_df


def build_map_gdf():

    # Site name
    # Latitude (park centerpoint)
    # Longitude (park centerpoint)
    # Website
    # Total number of photos submitted for the site
    # Number of photos in "Live" status
    # Number of photos in "Ready for Review" or "Approved, Not Yet Live" status

    # Currently not including...
    # ('AT', 'Needs Attention'),
    # ('SV', 'Save for Later'),

    parks = Park.objects.all().annotate(
        longitude=Func('centerpoint', function='ST_X', output_field=FloatField()),
        latitude=Func('centerpoint', function='ST_Y', output_field=FloatField()),
        center_wkt=Func('centerpoint', function='ST_AsText', output_field=CharField()),
    ).values(
        "name",
        "site_code",
        "website",
        "longitude",
        "latitude",
        "center_wkt"
    )
    parks_df = pd.DataFrame(parks)

    # TODO: How to handle scope?
    photos = Photo.objects.filter(
        status__in=['AT', 'RD', 'AP', 'LV']
    ).exclude(
        scope__in=['OUT', 'DUP']
    ).values(
        "pk",
        "status",
        "park__site_code",
    )

    df = pd.DataFrame(photos)
    df.rename(columns={
        'park__site_code': 'site_code',
    }, inplace=True)

    counts_df = df.groupby([
        'site_code',
        'status',
     ]).agg('count').reset_index()
    counts_df.rename(columns={
        'pk': 'photo_count'
    }, inplace=True)

    approved_counts_df = counts_df[counts_df['status'].isin(['LV', 'AP'])].groupby([
        'site_code',
    ]).agg('sum').reset_index()
    approved_counts_df.rename(columns={
        'photo_count': 'approved_photos'
    }, inplace=True)

    pending_counts_df = counts_df[counts_df['status'].isin(['AT', 'RD'])].groupby([
        'site_code',
    ]).agg('sum').reset_index()
    pending_counts_df.rename(columns={
        'photo_count': 'pending_photos'
    }, inplace=True)

    parks_df = parks_df.merge(
        approved_counts_df.drop(columns=['status']),
        how="left",
        on="site_code"
    ).merge(
        pending_counts_df.drop(columns=['status']),
        how="left",
        on="site_code"
    )

    parks_df.fillna(value=0, inplace=True)
    parks_df['approved_photos'] = parks_df['approved_photos'].astype(int)
    parks_df['pending_photos'] = parks_df['pending_photos'].astype(int)
    parks_df['total_photos'] = parks_df['pending_photos'] + parks_df['approved_photos']

    gs = gpd.GeoSeries.from_wkt(parks_df['center_wkt'])
    gdf = gpd.GeoDataFrame(parks_df, geometry=gs, crs="EPSG:4326")

    gdf.drop(columns=['center_wkt'], inplace=True)

    gdf['sos_live_link'] = settings.SOS_VIEWER_LIVE_LINK + '?site=' + gdf['site_code']

    return gdf


def data_file_to_s3(s3, local_file_path, bucket_name, out_key, acl=None, storage_class='GLACIER_IR', content_type='application/json'):
    '''Input: file path. Output: S3 URL of file.'''

    with open(local_file_path, 'rb') as f:
        args = {
            'Body': f,
            'Bucket': bucket_name,
            'Key': out_key,
            'StorageClass': storage_class,
            'ContentType': content_type,
        }
        
        if acl == 'public-read':
            args['ACL'] = 'public-read'

        put_result = s3.put_object(**args)

        return put_result
    return False


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

    return df


def save_backup_file(df, filename_root):
    backup_dir = os.path.join(settings.BASE_DIR, 'data', 'backup')
    os.makedirs(backup_dir, exist_ok=True)

    outfile = os.path.join(backup_dir,
                            f'{filename_root}_{datetime.datetime.now().date()}.csv')
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
