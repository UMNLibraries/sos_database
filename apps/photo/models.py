from django.dispatch import receiver
from django.contrib.gis.db import models
from django.utils.html import mark_safe
from simple_history.models import HistoricalRecords

from sos_database.storage_backends import PrivateMediaStorage

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
    sign = models.ForeignKey(Sign, null=True, blank=True, on_delete=models.SET_NULL)
    scope = models.CharField(max_length=4, blank=True, db_index=True, choices=SCOPE_CHOICES)
    status = models.CharField(max_length=4, db_index=True, choices=STATUS_CHOICES)
    box_id = models.CharField(max_length=255, db_index=True)
    box_filename = models.CharField(max_length=255)
    # box_foldername = models.CharField(max_length=255)
    photo_file_name = models.CharField(max_length=255)
    original_file_name = models.CharField(max_length=255)

    date_taken = models.DateField(null=True)
    dt_form = models.DateTimeField(null=True)
    dt_imported = models.DateTimeField(null=True, auto_now_add=True)

    # collection something something? probably separate m2m

    # descriptions
    title = models.TextField(null=True, blank=True, verbose_name="Title (original)")
    title_final = models.TextField(null=True, blank=True)
    additional_notes = models.TextField(null=True, blank=True, verbose_name="Additional notes (original)")
    additional_notes_final = models.TextField(null=True, blank=True)

    # image urls
    main_image_url = models.ImageField(
        storage=PrivateMediaStorage(), upload_to="images", max_length=255, null=True, blank=True)
    thumb_url = models.ImageField(
        storage=PrivateMediaStorage(), upload_to="thumbs", max_length=255, null=True, blank=True)

    #location info
    location = models.PointField(srid=4326, null=True, blank=True, verbose_name="Location (original)")
    location_final = models.PointField(srid=4326, null=True, blank=True)
    # location_source
    location_type = models.CharField(max_length=3, choices=LOCATION_TYPE_CHOICES, blank=True, verbose_name="Location type (original)")
    location_type_final = models.CharField(max_length=3, choices=LOCATION_TYPE_CHOICES, blank=True)

    bool_manual_correction = models.BooleanField(default=False)

    def __str__(self):
        if self.title_final:
            return f"{self.park.name} {self.id}: '{self.title_final}'"
        return f"{self.park.name} {self.id}"
    
    @property
    def image_preview(self):
        """Used to display Photo in admin view."""
        return mark_safe(f'<a href="{self.main_image_url.url}" target="_blank"><img src="{self.main_image_url.url}" width="500" /></a>')
    
    @property
    def thumbnail_preview(self):
        """Used to display Photo in admin view."""
        return mark_safe(f'<a href="{self.thumb_url.url}" target="_blank"><img src="{self.thumb_url.url}" width="100" /></a>')

    def get_final_value(self, obj, attr, blank_value=""):
        if getattr(obj, attr) not in [None, blank_value]:
            return getattr(obj, attr)
        return getattr(self, attr)
    
    def get_final_values(self):
        self.bool_manual_correction = False
        if self.manualcorrection_set.count() > 0:
            self.title_final = self.get_final_value(self.manualcorrection_set.first(), 'title')
            if self.title_final != self.title:
                self.bool_manual_correction = True

            self.additional_notes_final = self.get_final_value(self.manualcorrection_set.first(), 'additional_notes')
            if self.additional_notes_final != self.additional_notes:
                self.bool_manual_correction = True

            self.location_final = self.get_final_value(self.manualcorrection_set.first(), 'location')
            if self.location_final != self.location:
                self.bool_manual_correction = True

            self.location_type_final = self.get_final_value(self.manualcorrection_set.first(), 'location_type')
            if self.location_type_final != self.location_type:
                self.bool_manual_correction = True
        else:
            self.title_final = self.title
            self.additional_notes_final = self.additional_notes
            self.location_final = self.location
            self.location_type_final = self.location_type

    def save(self, *args, **kwargs):
        if self.pk:
            self.get_final_values()
            
        super(Photo, self).save(*args, **kwargs)
        

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


class ManualCorrection(models.Model):
    photo = models.ForeignKey(Photo, null=True, on_delete=models.SET_NULL)
    photo_file_name = models.CharField(max_length=255, null=True)
    title = models.TextField(null=True, blank=True)
    additional_notes = models.TextField(null=True, blank=True)
    location = models.PointField(srid=4326, null=True, blank=True)
    location_type = models.CharField(max_length=3, choices=LOCATION_TYPE_CHOICES, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        self.photo_file_name = self.photo.photo_file_name
        super(ManualCorrection, self).save(*args, **kwargs)

        self.photo.save()


@receiver(models.signals.post_delete, sender=ManualCorrection)
def model_delete(sender, instance, **kwargs):
    try:
        instance.photo.get_final_values()
        instance.photo.save()
    except AttributeError:
        pass
