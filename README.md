# SOS database

A scratch version of a Django database for Save Our Signs

## Building DB from scratch
```
python manage.py import_park_sites
python manage.py import_photos_gsheet --reload_objs.  # First batch files
python manage.py import_photos_box  # Files that weren't in first batch
python manage.py box_photos_to_private_s3
```

## Steps for checking for new form entries
```python
python manage.py import_photos_box
# If new photos found...
python manage.py box_photos_to_private_s3
```

## Workflow

1. Qualtrics form
2. Google sheet import for previous batch only because it contains moderations
3. Box images/spreadsheet
4. DB import and copy of images to private S3
5. Admin editing
6. Push to live public S3

-Sept. 24 cutoff -- get only newer ones from Box

## Bulk uploads



## Potential models

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