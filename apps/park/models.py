from django.contrib.gis.db import models


class SiteType(models.Model):
    name = models.CharField(max_length=100, db_index=True)

    def __str__(self):
        return self.name


class State(models.Model):
    name = models.CharField(max_length=255, db_index=True)

    def __str__(self):
        return self.name


class ParkCollection(models.Model):
    '''ParkCollection is used to associate different official NPS units that are part of a larger whole.'''
    name = models.CharField(max_length=255, db_index=True)
    collection_code = models.CharField(max_length=10, db_index=True, null=True, blank=True)

    def __str__(self):
        return self.name


class Park(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    site_code = models.CharField(max_length=10, db_index=True)
    website = models.CharField(max_length=255)
    states = models.ManyToManyField(State)
    site_types = models.ManyToManyField(SiteType)

    collections = models.ManyToManyField(ParkCollection)

    # Initially, imported from PHOTO Google sheet, not park list
    box_folder_id = models.CharField(max_length=255, blank=True)

    centerpoint = models.PointField(srid=4326, null=True)

    def __str__(self):
        return self.name


class SubSite(models.Model):
    '''Subsites are things that SOS creates to denote smaller parts of parks that are generally not official NPS units

    If possible, subsites offered to admin users should only include subsites of the current Park selected.'''
    name = models.CharField(max_length=255, db_index=True)
    subsite_code = models.CharField(max_length=10, db_index=True, null=True, blank=True)
    park = models.ForeignKey(Park, on_delete=models.CASCADE)

    def __str__(self):
        return self.name



FLAG_TYPE_CHOICES = (
    ('FLM', 'Film'),
    ('MON', 'Monuments, statues, and other markers'),
    ('EXH', 'Interior / exterior exhibits'),
    ('SGN', 'Signs and waysides'),
    ('PUB', 'Publications'),
    ('NOT', 'Nothing to report'),
    ('OTH', 'Other'),
)
  

class DOIFlag(models.Model):
    '''Has this park been flagged under one of DOI's categories?'''
    park = models.ForeignKey(Park, on_delete=models.CASCADE)
    flag_type = models.CharField(max_length=4, choices=FLAG_TYPE_CHOICES)
    recommendation = models.CharField(max_length=4, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.park.name}: {self.get_flag_type_display()}"
