from django.contrib.gis import admin
from dalf.admin import DALFModelAdmin, DALFRelatedOnlyField, DALFRelatedFieldAjax
from django.contrib.gis.db import models
from django.forms import TextInput, Textarea
from django.contrib.gis.forms.widgets import OSMWidget

from apps.photo.models import Photo,  Sign, ManualCorrection, RevisedPhoto
from apps.park.models import State, Park, SiteType


class SiteTypeAdmin(admin.ModelAdmin):
    search_fields = ['name']
    ordering = ['name']


class StateAdmin(admin.ModelAdmin):
    search_fields = ['name']
    ordering = ['name']


class ParkAdmin(admin.GISModelAdmin):
    search_fields = ['name']
    ordering = ['name']

    autocomplete_fields = ['states', 'site_types', 'parent_site']

    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -98,
            'default_lat': 39,
            'default_zoom': 6
        },
    }


class SignAdmin(admin.ModelAdmin):
    search_fields = ['title']


class ManualCorrectionInline(admin.StackedInline):
    model = ManualCorrection
    extra = 0
    exclude = ['photo_file_name']


    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in ('poly', 'location'):
            kwargs['widget'] = OSMWidget(attrs={
                    'default_lon': -98,
                    'default_lat': 39,
                    'default_zoom': 6,
                    # 'modifiable': False
                })
        return super().formfield_for_dbfield(db_field,**kwargs)
    

class RevisedPhotoInline(admin.StackedInline):
    model = RevisedPhoto
    extra = 0
    # readonly_fields = []
    exclude = ['thumb_url', 'photo_file_name']
       

class PhotoAdmin(admin.GISModelAdmin, DALFModelAdmin):
    # TODO: Change these to "_final" once those are populated
    search_fields = ['title', 'title_final', 'additional_notes', 'additional_notes_final', 'photo_file_name']

    list_display = ['__str__', 'title_final', 'scope', 'status', 'date_taken']

    list_filter = (
        ('park', DALFRelatedFieldAjax),  # enable ajax completion for category field (FK)
        'scope',
        'status',
        'photo_type',
    )

    autocomplete_fields = ['park', 'sign']

    inlines = [
        ManualCorrectionInline,
        RevisedPhotoInline
    ]

    fieldsets = (
        ('Basic info', {
            'fields': (
                'image_preview',
                'park',
                'sign',
                'date_taken',
                'dt_form',
                'get_title',
                'title',
                'get_additional_notes',
                'additional_notes',
                'photo_type',
                'scope',
                'status',
                'location_type',
                'bool_manual_correction',
                'location_final',
                'location_embedded',
                # 'location_final',
                'get_location_type',
            )
        }),
        ('Additional metadata', {
            'fields': (
                'box_id',
                'photo_file_name',
                'original_file_name',
                'main_image_url',
            )
        }),
   )

    readonly_fields = ['bool_manual_correction', 'box_id', 'dt_form', 'get_title', 'get_additional_notes', 'get_location_type', 'image_preview', 'photo_file_name', 'original_file_name', 'date_taken', 'title', 'additional_notes']

    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -98,
            'default_lat': 39,
            'default_zoom': 6,
            'modifiable': False
        },
    }

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 80})}, # Override all TextFields
    }

    def get_title(self, obj):
        if obj.title_final != '':
            return obj.title_final
        return obj.title
    get_title.short_description = 'Current Title'

    def get_additional_notes(self, obj):
        if obj.additional_notes_final != '':
            return obj.additional_notes_final
        return obj.additional_notes
    get_additional_notes.short_description = 'Current Additional Notes'

    def get_location_type(self, obj):
        if obj.location_type_final != '':
            return obj.get_location_type_final_display()
        return obj.get_location_type_display()
    get_location_type.short_description = 'Current Location Type'

    def image_preview(self, obj):
        return obj.image_preview

    image_preview.short_description = 'Image Preview'
    image_preview.allow_tags = True

    def thumbnail_preview(self, obj):
        return obj.thumbnail_preview

    thumbnail_preview.short_description = 'Thumbnail Preview'
    thumbnail_preview.allow_tags = True

admin.site.register(State, StateAdmin)
admin.site.register(SiteType, SiteTypeAdmin)
admin.site.register(Park, ParkAdmin)
admin.site.register(Sign, SignAdmin)
admin.site.register(Photo, PhotoAdmin)
