import re
import os
import requests
import argparse
from PIL import Image, ImageOps
from urllib.parse import urlsplit

from io import BytesIO


def remove_exif(im):
    '''Input: Open PIL image. Output: Open PIL image with no exif'''
    # Reset orientation if needed before removing exif
    im = ImageOps.exif_transpose(im)

    # Copy image data without moving metadata
    data = list(im.getdata())
    im_flat = Image.new(im.mode, im.size)
    try:
        im_flat.putdata(data)
    except TypeError:
        # When the above putdata() was getting run on jpegs before sometimes (often) it thought there was more than one page, might have been some kind of extra channel. This try block is probably unnecessary now.
        return None
    im_flat = im_flat.convert('RGB')
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
