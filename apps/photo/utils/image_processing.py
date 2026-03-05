import re
import os
import requests
import argparse
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
from urllib.parse import urlsplit
import exifread as ef

from io import BytesIO


def remove_exif(im):
    '''Input: Open PIL image. Output: Open PIL image with no exif'''
    # Reset orientation if needed before removing exif
    # print('pre transpose')
    im = ImageOps.exif_transpose(im)
    # print('post transpose')

    # Copy image data without moving metadata
    data = list(im.getdata())
    orig_mode = im.mode
    orig_size = im.size

    # Can we close original im at this point?
    im.close()
    # print('post close')

    im_flat = Image.new(orig_mode, orig_size)
    # print('post new image')
    try:
        im_flat.putdata(data)
        # print('post put')
    except TypeError:
        # When the above putdata() was getting run on jpegs before sometimes (often) it thought there was more than one page, might have been some kind of extra channel. This try block is probably unnecessary now.
        return None
    im_flat = im_flat.convert('RGB')
    # print('post convert')
    return im_flat


def get_jpg_filename(filename):
    # Normalize file name on assumption it will be converted to .jpg
    return re.sub(r'\.[A-Za-z]{3,5}$', '.jpg', filename)


def image_to_s3(s3, im, bucket_name, out_key, full_link_path, acl=None, storage_class='GLACIER_IR'):
    '''Input: Open PIL image. Output: S3 URL of image, now converted to .jpg'''
    out_jpg_buffer = BytesIO()
    im.save(out_jpg_buffer, format="JPEG")
    out_jpg_buffer.seek(0)

    args = {
        'Body': out_jpg_buffer,
        'Bucket': bucket_name,
        'Key': out_key,
        'StorageClass': storage_class,
        'ContentType': 'image/jpeg',
    }
    if acl == 'public-read':
        args['ACL'] = 'public-read'

    put_result = s3.put_object(**args)

    return full_link_path


def thumbnail_to_s3(s3, im, bucket_name, out_key, full_link_path, acl=None, storage_class='GLACIER_IR'):
    '''Input: Open PIL image. Output: S3 URL of shrunken image, now converted to .jpg'''
    max_size = (200, 200)
    im.thumbnail(max_size)

    out_jpg_buffer = BytesIO()
    im.save(out_jpg_buffer, format="JPEG")
    out_jpg_buffer.seek(0)

    args = {
        'Body': out_jpg_buffer,
        'Bucket': bucket_name,
        'Key': out_key,
        'StorageClass': storage_class,
        'ContentType': 'image/jpeg',
    }
    if acl == 'public-read':
        args['ACL'] = 'public-read'

    put_result = s3.put_object(**args)

    return full_link_path


def get_current_s3_matches(s3, bucket_name, prefix):

    matching_keys = []
    key_filter = r'.+\.jpg$'

    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    for page in pages:
        if 'Contents' in page.keys():
            matching_keys += [obj['Key'] for obj in page['Contents'] if re.match(key_filter, obj['Key'])]

    return matching_keys


def get_exif_data_general(im):
    # im = ImageOps.exif_transpose(im)

    exif_data = im.getexif()
    if not exif_data:
        print("No EXIF data found.")
        return None
    
    labeled_data = {}
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, tag_id)
        labeled_data[tag_name] = value
    print(labeled_data)
    
    # print(exif_data)
    return labeled_data


def convert_to_degrees(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    try:
        d = float(value.values[0].num) / float(value.values[0].den)
        m = float(value.values[1].num) / float(value.values[1].den)
        s = float(value.values[2].num) / float(value.values[2].den)

        return d + (m / 60.0) + (s / 3600.0)
    except ZeroDivisionError:
        print('Cannot divide by 0...')
        print(value)
        return None


def get_gps_info(file_path):
    '''
    From Melinda: returns gps data if present other wise returns empty dictionary
    '''
    with open(file_path, 'rb') as f:
        tags = ef.process_file(f)
        latitude = tags.get('GPS GPSLatitude')
        latitude_ref = tags.get('GPS GPSLatitudeRef')
        longitude = tags.get('GPS GPSLongitude')
        longitude_ref = tags.get('GPS GPSLongitudeRef')
        if latitude:
            lat_value = convert_to_degrees(latitude)
            if lat_value:
                if latitude_ref.values != 'N':
                    lat_value = -lat_value
            else:
                return None
        else:
            return None
        if longitude:
            lon_value = convert_to_degrees(longitude)
            if lon_value:
                if longitude_ref.values != 'E':
                    lon_value = -lon_value
            else:
                return None
        else:
            return None
        return {'latitude': lat_value, 'longitude': lon_value}