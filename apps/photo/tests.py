from django.test import TestCase

from apps.photo.models import ManualCorrection
from apps.photo.utils.export import build_public_manifest, dump_cx_model_backups

class ExportTestCase(TestCase):
    fixtures = ['state.json', 'sitetype.json', 'park.json', 'photo.json', 'manualcorrections.json']

    public_fields = [
        'site_code',
        'site_name',
        'site_type',
        'file_name',
        'title',
        'date_taken',
        'main_image_url',
        'thumb_url',
        'longitude',
        'latitude',
        'location_source',
        'states',
        'website',
    ]

    def test_export_fields(self):
        '''Are the expected export fields, and only those fields, in manifest export df?'''
        export_df = build_public_manifest()
        self.assertEqual(set(self.public_fields), set(export_df.columns))

    def test_manual_corrections_creation(self):
        '''Manual Correction should have the same photo_file_name value as the parent photo's photo_file_name'''
        mc = ManualCorrection.objects.get(pk=1)
        mc.save()

        self.assertEqual(mc.photo.photo_file_name, mc.photo_file_name)

    def test_manual_corrections_dump(self):
        '''Manual Correction dump should not include a lookup to the parent photo primary key,
        since that will be changed on re-import'''
        export_df = dump_cx_model_backups('photo', 'ManualCorrection')
        self.assertNotIn('photo_id', list(export_df.columns))
