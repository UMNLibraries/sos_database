from PIL import Image
from io import BytesIO

from django.dispatch import receiver
from django.contrib.gis.db import models
from django.utils.html import mark_safe
from django.core.files.base import ContentFile
from simple_history.models import HistoricalRecords
from postgres_copy import CopyManager

from sos_database.storage_backends import PrivateMediaStorage

from apps.park.models import Park, State
from apps.photo.utils.image_processing import remove_exif


class Sign(models.Model):
    park = models.ForeignKey(Park, null=True, on_delete=models.SET_NULL)
    title = models.TextField()
    
    # How to handle location?
    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.park.site_code}: {self.title}"


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
    ('RJ', 'Rejected'),
)


LOCATION_TYPE_CHOICES = (
    ('US', 'User-submitted'),
    ('PK', 'Park Centerpoint'),
    ('SOS', 'SOS corrected'),
)


'''
Normal - This photo shows a sign in an NPS site. I do not think it has been changed in response to recent executive orders
Altered - This photo shows a site of removal/censorship. It shows a sign that has been altered in response to recent executive orders OR it shows an empty space that used to have a sign.
Artistic - This photo shows a creative response to a sign change/removal. For example in Philadelphia, protestors taped posters reading "history is real" on the wall where an exhibit on slavery was removed.
Other - Other
'''
PHOTO_TYPE_CHOICES = (
    ('NML', 'Normal'),
    ('ALT', 'Altered'),
    ('ART', 'Artistic'),
    ('OTH', 'Other'),
)


REVIEW_REASON_CHOICES = (
    ('SCP', 'Not sure if in scope'),
    ('BOD', 'Person or identifiable body part'),
    ('PER', 'Personally identifying information'),
    ('RFL', 'Reflection'),
    ('IMG', 'Poor image quality'),
    ('ROT', 'Image needs to be rotated'),
)


class Collection(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    bool_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Photo(models.Model):
    # associations and ids
    park = models.ForeignKey(Park, null=True, on_delete=models.SET_NULL)
    sign = models.ForeignKey(Sign, null=True, blank=True, on_delete=models.SET_NULL)
    scope = models.CharField(max_length=4, blank=True, db_index=True, choices=SCOPE_CHOICES)
    status = models.CharField(max_length=4, db_index=True, choices=STATUS_CHOICES, null=True, blank=True)
    review_reason = models.CharField(max_length=4, db_index=True, choices=REVIEW_REASON_CHOICES, null=True, blank=True)
    photo_type = models.CharField(max_length=4, db_index=True, choices=PHOTO_TYPE_CHOICES, default="NML")
    box_id = models.CharField(max_length=255, db_index=True)
    # box_filename = models.CharField(max_length=255)
    # box_foldername = models.CharField(max_length=255)
    photo_file_name = models.CharField(max_length=255)
    original_file_name = models.CharField(max_length=255)

    date_taken = models.DateField(null=True)
    dt_form = models.DateTimeField(null=True, verbose_name="Date submitted")
    dt_imported = models.DateTimeField(null=True, auto_now_add=True)

    # collection something something? probably separate m2m
    collections = models.ManyToManyField(Collection, blank=True)

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
    bool_exif_location = models.BooleanField(null=True)  # Has this image been checked for internal location info?
    location_embedded = models.PointField(srid=4326, null=True, blank=True, verbose_name="Location (Embedded in photo)")
    # location = models.PointField(srid=4326, null=True, blank=True, verbose_name="Location (original)")
    location_final = models.PointField(srid=4326, null=True, blank=True, verbose_name="Location (current)")
    # location_source
    location_type = models.CharField(max_length=3, choices=LOCATION_TYPE_CHOICES, blank=True, verbose_name="Location type")
    location_type_final = models.CharField(max_length=3, choices=LOCATION_TYPE_CHOICES, blank=True)

    bool_manual_correction = models.BooleanField(default=False)

    def __str__(self):
        if self.title_final:
            return f"{self.park.name} {self.id}: '{self.title_final}'"
        return f"{self.park.name} {self.id}"
    
    @property
    def image_preview(self):
        """Used to display Photo in admin view."""
        if self.revisedphoto_set.count() > 0:
            revised_photo = self.revisedphoto_set.first()
            return mark_safe(f'<a href="{revised_photo.main_image_url.url}" target="_blank"><img src="{revised_photo.main_image_url.url}" width="500" /></a>')
        else:
            return mark_safe(f'<a href="{self.main_image_url.url}" target="_blank"><img src="{self.main_image_url.url}" width="500" /></a>')
    
    @property
    def thumbnail_preview(self):
        """Used to display Photo in admin view."""
        if self.revisedphoto_set.count() > 0:
            revised_photo = self.revisedphoto_set.first()
            return mark_safe(f'<a href="{revised_photo.thumb_url.url}" target="_blank"><img src="{revised_photo.thumb_url.url}" width="100" /></a>')
        else:
            return mark_safe(f'<a href="{self.thumb_url.url}" target="_blank"><img src="{self.thumb_url.url}" width="100" /></a>')

    def get_final_value(self, obj, attr, blank_value=""):
        if getattr(obj, attr) not in [None, blank_value]:
            return getattr(obj, attr)
        return getattr(self, attr)
    
    def get_final_value_nullable(self, obj, attr, blank_value="blank"):
        if getattr(obj, attr) and getattr(obj, attr).lower() == blank_value:
            return None
        elif getattr(obj, attr) not in [None, '']:
            return getattr(obj, attr)
        return getattr(self, attr)
    
    def check_embedded_location(self):
        if self.location_type == 'US' and self.location_embedded:
            self.location_final = self.location_embedded
            self.location_type_final = 'US'
        else:
            self.location_final = self.park.centerpoint
            self.location_type_final = 'PK'
            self.location_type = 'PK'
    
    def get_final_values(self):
        self.bool_manual_correction = False
        if self.manualcorrection_set.count() > 0:
            # Allow blank values to overwrite (blank_value set to False)...
            self.title_final = self.get_final_value_nullable(self.manualcorrection_set.first(), 'title')
            if self.title_final != self.title:
                self.bool_manual_correction = True

            # Allow blank values to overwrite (blank_value set to False)...
            self.additional_notes_final = self.get_final_value_nullable(self.manualcorrection_set.first(), 'additional_notes')
            # if not self.additional_notes_final:
            #     self.additional_notes_final = None
            if self.additional_notes_final != self.additional_notes:
                self.bool_manual_correction = True

            # Location logic
            # if embedded location in image, save to location_embedded
            # By default, set location_type to park centerpoint and extract location from Park model to set location_final
            # If location type set to US, extract location from location_embedded
            # If manual correction, use manualcorrection value for location_final and location_type_final

            if self.manualcorrection_set.first().location:
                self.location_final = self.manualcorrection_set.first().location
                self.location_type_final = 'SOS'
                self.location_type = 'SOS'
                self.bool_manual_correction = True
            else:
                self.check_embedded_location()

        else:
            self.title_final = self.title
            self.additional_notes_final = self.additional_notes

            self.check_embedded_location()

    

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
    # location_type = models.CharField(max_length=3, choices=LOCATION_TYPE_CHOICES, null=True, blank=True)
    comments = models.TextField(null=True, blank=True, verbose_name="Internal comment")
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    objects = CopyManager()

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


class RevisedPhoto(models.Model):
    '''Possible addition for cropped photos'''
    photo = models.ForeignKey(Photo, null=True, on_delete=models.SET_NULL)
    photo_file_name = models.CharField(max_length=255, null=True)

    # image urls
    main_image_url = models.ImageField(
        storage=PrivateMediaStorage(), upload_to="images", max_length=255, null=True, blank=True)
    thumb_url = models.ImageField(
        storage=PrivateMediaStorage(), upload_to="thumbs", max_length=255, null=True, blank=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def save_thumbnail(self):
        if self.main_image_url and not self.thumb_url:
            im = Image.open(self.main_image_url)
            im = remove_exif(im)
            max_size = (200, 200)
            im.thumbnail(max_size)

            # Save the thumbnail to a BytesIO object
            temp_thumb = BytesIO()
            im.save(temp_thumb, format='JPEG') # Convert to JPEG
            temp_thumb.seek(0)

            # Create a ContentFile and save it to the thumbnail field
            # 'save=False' prevents an infinite save loop
            self.thumb_url.save(
                self.main_image_url.name,
                ContentFile(temp_thumb.read()),
                save=False
            )
            temp_thumb.close()

            # Call the real save() method again to save the thumbnail field value
            super(RevisedPhoto, self).save(update_fields=['thumb_url'])

    def save(self, *args, **kwargs):
        self.photo_file_name = self.photo.photo_file_name

        super(RevisedPhoto, self).save(*args, **kwargs)

        self.save_thumbnail()
        self.photo.save()


@receiver(models.signals.post_delete, sender=RevisedPhoto)
def model_delete(sender, instance, **kwargs):
    try:
        instance.photo.get_final_values()
        instance.photo.save()
    except AttributeError:
        pass
