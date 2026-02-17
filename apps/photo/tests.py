from django.test import TestCase

from apps.photo.utils.export import build_public_manifest

class ExportTestCase(TestCase):
    fixtures = ['state.json', 'sitetype.json', 'park.json', 'photo.json']

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
