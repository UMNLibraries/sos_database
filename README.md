# SOS database

A scratch version of a Django database for Save Our Signs

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