# SOS database

A Django database to manage Save Our Signs submissions and images.

## Building DB from scratch
```
python manage.py import_park_sites
python manage.py import_photos_gsheet --reload_objs.  # First batch files
python manage.py import_photos_box  # Files that weren't in first batch
python manage.py import_photos_bulk
python manage.py box_photos_to_private_s3
```

## To check for new form entries
```python
python manage.py check_form_updates
```

## To check for new bulk uploads
```python
python manage.py import_photos_bulk
python manage.py box_photos_to_private_s3
```

## To update the GeoJSON that powers the parks map
```python
python manage.py export_parks_map --upload
```

## To upload approved images to public storage and re-export manifest
```python
python manage.py update_live_photos
python manage.py export_manifests --upload
python manage.py export_parks_map --upload
```

## General workflow explanation

1. Entry submitted to Qualtrics form
2. Qualtrics output and Box details sent to spreadsheet in Box
4. DB import and copy of images to private S3
5. Admin editing
6. Push to live public S3

Images from before Sept. 24 cutoff were imported from the original Google sheet

## Bulk uploads
TK

## Potential models (old, just keeping in case we want to revisit)

State

Collection/Tag for things that have been targeted

Collection should either be one-site or cross-site

Site
-Can cross state boundaries, m2m needed
-Some sites are units of others
    Ft. Vancouver
    Can we add manual sites

Sign
-multiple photos can be assigned

Photo

-Separate model for modified comment
-Redact email addresses/phone numbers while importing into Django

PhotoText
-OCR of photo

Action
-Something happening to a sign
-Could be type of source - media report vs. self-reported
-Or you could require person to submit a "before" photo, from either our archive, or separate upload

ModerationComment

MediaStory
-Connected to multiple sites/signs

Topic tags + Internal tags