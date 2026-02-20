# from io import StringIO
# from tempfile import NamedTemporaryFile

from django.test import TestCase
# from django.core.management import call_command

from apps.photo.models import ManualCorrection, Photo
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

class ManualCorrectionTestCase(TestCase):
    fixtures = ['state.json', 'sitetype.json', 'park.json', 'photo.json', 'manualcorrections.json']

    @classmethod
    def setUpTestData(cls):
        mc = ManualCorrection.objects.get(pk=1)
        mc.save()

        mc_2 = ManualCorrection.objects.get(pk=2)

        p_2 = Photo.objects.get(pk=2)
        p_2.save()

    def test_manual_corrections_creation(self):
        '''Manual Correction should have the same photo_file_name value as the parent photo's photo_file_name'''

        mc = ManualCorrection.objects.get(pk=1)
        self.assertEqual(mc.photo.photo_file_name, mc.photo_file_name)

    def test_manual_corrections_dump(self):
        '''Manual Correction dump should not include a lookup to the parent photo primary key,
        since that will be changed on re-import'''
        export_df = dump_cx_model_backups('photo', 'ManualCorrection')
        self.assertNotIn('photo_id', list(export_df.columns))

    def test_manual_corrections_load(self):
        '''After deletion of manual corrections, initial values should be re-set. After re-import, cx values should be present'''
        # temp_file = NamedTemporaryFile()

        # export_df = dump_cx_model_backups('photo', 'ManualCorrection')
        # export_df.to_csv(temp_file.name, index=False)
    
        p_2 = Photo.objects.get(pk=2)
        mc_2 = ManualCorrection.objects.get(pk=2)
    
        # First check that manual cx has been applied during setup
        self.assertEqual(p_2.title_final, 'test manual cx title')
        self.assertEqual(p_2.additional_notes_final, 'test manual cx additional notes')
        self.assertEqual(p_2.location_final, mc_2.location)
        self.assertEqual(p_2.location_type_final, 'SOS')

        # Now delete the correction and see if value reverts to initial value
        mc_2 = ManualCorrection.objects.get(pk=2)
        mc_2.delete()

        p_2 = Photo.objects.get(pk=2)
        self.assertEqual(p_2.title_final, 'Initial title')
        self.assertEqual(p_2.additional_notes_final, 'Initial additional notes')
        self.assertEqual(p_2.location_final, p_2.location)
        self.assertEqual(p_2.location_type_final, 'PK')

        # # Now re-import ManualCorrection objects using command and look for cx values again
        # # This is difficult to test with file reload because it causes transaction errors.
        # out = StringIO()
        # call_command('load_manual_corrections', infile=temp_file.name, stdout=out, stderr=StringIO())

        # # mc_2 = ManualCorrection.objects.get(pk=2)
        # p_2 = Photo.objects.get(pk=2)
        # self.assertEqual(p_2.title_final, 'test manual cx title')
