from django.contrib.gis.db import models


class SiteType(models.Model):
    name = models.CharField(max_length=100, db_index=True)

    def __str__(self):
        return self.name

class State(models.Model):
    name = models.CharField(max_length=255, db_index=True)

    def __str__(self):
        return self.name


class Park(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    site_code = models.CharField(max_length=10, db_index=True)
    website = models.CharField(max_length=255)
    states = models.ManyToManyField(State)
    site_types = models.ManyToManyField(SiteType)

    # Initially, imported from PHOTO Google sheet, not park list
    box_folder_id = models.CharField(max_length=255, blank=True)

    centerpoint = models.PointField(srid=4326, null=True)

    def __str__(self):
        return self.name