from django.contrib.gis import admin

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


class PhotoAdmin(admin.GISModelAdmin):
    autocomplete_fields = ['park', 'sign']

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
