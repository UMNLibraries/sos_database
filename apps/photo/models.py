from django.contrib.gis.db import models
from simple_history.models import HistoricalRecords

from sos_database.storage_backends import PublicMediaStorage

from apps.park.models import Park, State


class Sign(models.Model):
    park = models.ForeignKey(Park, null=True, on_delete=models.SET_NULL)
    title = models.TextField()
    
    # How to handle location?


SCOPE_CHOICES = (
    ('IN', 'In Scope'),
    ('OUT', 'Out of Scope'),
    ('DUP', 'Exact Duplicate'),
)


STATUS_CHOICES = (
    ('LV', 'Live'),
    ('AP', 'Approved, Not Yet Live'),
    ('RD', 'Ready for Review'),
    ('AT', 'Needs Attention'),
    ('SV', 'Save for Later'),
)


LOCATION_TYPE_CHOICES = (
    ('US', 'User-submitted'),
    ('PK', 'Park Centerpoint'),
    ('SOS', 'SOS corrected'),
)


class Photo(models.Model):
    # associations and ids
    park = models.ForeignKey(Park, null=True, on_delete=models.SET_NULL)
    sign = models.ForeignKey(Sign, null=True, on_delete=models.SET_NULL)
    scope = models.CharField(max_length=4, db_index=True, choices=SCOPE_CHOICES)
    status = models.CharField(max_length=4, db_index=True, choices=STATUS_CHOICES)
    box_id = models.CharField(max_length=255, db_index=True)
    box_filename = models.CharField(max_length=255)
    box_foldername = models.CharField(max_length=255)
    photo_file_name = models.CharField(max_length=255)
    original_file_name = models.CharField(max_length=255)

    date_taken = models.DateField(null=True)

    # collection something something? probably separate m2m

    # descriptions
    title = models.TextField(null=True)
    title_final = models.TextField(null=True)
    additional_notes = models.TextField(null=True)
    additional_notes_final = models.TextField(null=True)

    # image urls
    main_image_url = models.ImageField(
        storage=PublicMediaStorage(), null=True)
    thumb_url = models.ImageField(
        storage=PublicMediaStorage(), null=True)

    #location info
    location_orig = models.PointField(srid=4326, null=True)
    location_modified = models.PointField(srid=4326, null=True)
    # location_source
    location_type = models.CharField(max_length=3, choices=LOCATION_TYPE_CHOICES, blank=True)

    # Scope
    # Metadata edits
    # box_foldername
    # photo_file_name
    # title
    # additional_notes
    # date_taken
    # collection
    # park_name
    # # id
    # original_file_name
    # ext
    # longitude
    # latitude
    # location_source
    # type
    # alpha_code
    # box_id
    # box_filename
    # thumb_url
    # main_image_url
    # s3_error


class TitleCorrection(models.Model):
    title = models.TextField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()


class AdditionalNotesCorrection(models.Model):
    additional_notes = models.TextField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
