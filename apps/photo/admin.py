from django.contrib.gis import admin
from dalf.admin import DALFModelAdmin, DALFRelatedOnlyField, DALFRelatedFieldAjax

from apps.photo.models import Photo,  Sign
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

    autocomplete_fields = ['states', 'site_types']

    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -98,
            'default_lat': 39,
            'default_zoom': 6
        },
    }


class SignAdmin(admin.ModelAdmin):
    search_fields = ['title']


class PhotoAdmin(admin.GISModelAdmin, DALFModelAdmin):
    autocomplete_fields = ['park', 'sign']

    readonly_fields = ['box_id', 'box_filename', 'photo_file_name', 'original_file_name', 'date_taken', 'title', 'additional_notes']

    # TODO: Change these to "_final" once those are populated
    search_fields = ['title', 'additional_notes', 'photo_file_name']

    list_display = ['__str__', 'title', 'scope', 'status', 'date_taken']

    list_filter = (
        ('park', DALFRelatedFieldAjax),  # enable ajax completion for category field (FK)
        'scope',
        'status',
    )

    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -98,
            'default_lat': 39,
            'default_zoom': 6
        },
    }

admin.site.register(State, StateAdmin)
admin.site.register(SiteType, SiteTypeAdmin)
admin.site.register(Park, ParkAdmin)
admin.site.register(Sign, SignAdmin)
admin.site.register(Photo, PhotoAdmin)
