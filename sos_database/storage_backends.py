from django.core.files.storage import storages
from storages.backends.s3 import S3Storage
# https://testdriven.io/blog/storing-django-static-and-media-files-on-amazon-s3/


class StaticStorage(S3Storage):
    '''Not actually being used?'''
    location = 'static'
    default_acl = 'public-read'


class PublicMediaStorage(S3Storage):
    location = 'media'
    default_acl = 'public-read'
    file_overwrite = False


class PrivateMediaStorage(S3Storage):
    location = 'media'
    default_acl = 'private'
    file_overwrite = False
    custom_domain = False
