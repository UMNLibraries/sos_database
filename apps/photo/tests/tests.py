import os
import datetime
# from io import StringIO
# from tempfile import NamedTemporaryFile

from django.test import TestCase
from django.contrib.gis.geos import Point
# from django.core.management import call_command

from PIL import Image

from apps.photo.models import ManualCorrection, Photo
from apps.photo.utils.box import get_box_client, get_box_file_as_tempfile
from apps.photo.utils.export import build_public_manifest, dump_cx_model_backups
from apps.photo.utils.image_processing import remove_exif, get_exif_data_general, get_gps_info
from apps.photo.management.commands.import_photos_box import Command as ImportPhotosBox

from django.conf import settings


class BoxImportTestCase(TestCase):

    def test_qualtrics_date_parser(self):
        '''Values separated by slashes OR dashes should be parsed as dates
        due to overly flexible input standards on Qualrics date picker'''

        parsed_date = ImportPhotosBox.parse_qualtrics_date(None, 'asdfs')
        self.assertEqual(parsed_date, None)

        parsed_date = ImportPhotosBox.parse_qualtrics_date(None, '01/02/2025')
        self.assertEqual(parsed_date, datetime.date(2025,1,2))

        parsed_date = ImportPhotosBox.parse_qualtrics_date(None, '01-02-2025')
        self.assertEqual(parsed_date, datetime.date(2025,1,2))


class ImageLocationTestCase(TestCase):

    def test_exif_general(self):
        infile = os.path.join(settings.BASE_DIR, '../', 'apps', 'photo', 'tests', 'test_images', 'bird_test_1.JPG')
        im = Image.open(infile)

        exif_data = get_exif_data_general(im)
        self.assertEqual(exif_data['ImageDescription'], 'Test bird 1 EXIF description')

        self.assertEqual(im.mode, 'RGB')

    def test_exif_removal(self):
        infile = os.path.join(settings.BASE_DIR, '../', 'apps', 'photo', 'tests', 'test_images', 'bird_test_1.JPG')
        im = Image.open(infile)

        exif_data = get_exif_data_general(im)
        self.assertEqual(exif_data['ImageDescription'], 'Test bird 1 EXIF description')

        im = remove_exif(im)
        exif_data = get_exif_data_general(im)
        self.assertEqual(exif_data, None)

    def test_exif_location_none(self):
        # Image with no location info
        infile = os.path.join(settings.BASE_DIR, '../', 'apps', 'photo', 'tests', 'test_images', 'bird_test_1.JPG')
        im = Image.open(infile)

        self.assertEqual(im.mode, 'RGB')

        exif_data = get_gps_info(infile)
        self.assertEqual(exif_data, None)

    def test_exif_location_GIMP(self):
        # Image with location info from Apple Photos
        infile = os.path.join(settings.BASE_DIR, '../', 'apps', 'photo', 'tests', 'test_images', 'bird_test_1_gps_ApplePhotos.jpeg')
        im = Image.open(infile)

        self.assertEqual(im.mode, 'RGB')

        exif_data = get_gps_info(infile)
        self.assertEqual(exif_data, {'latitude': 45.0, 'longitude': -93.0})

    def test_exif_location_heic(self):
        infile = os.path.join(settings.BASE_DIR, '../', 'apps', 'photo', 'tests', 'test_images', 'MTKYqCDUdbGxAvQdgt5tcU_Gateway_Arch_NP_1.heic')

        im = Image.open(infile)

        self.assertEqual(im.mode, 'RGB')

        exif_data = get_gps_info(infile)
        self.assertEqual(exif_data, {'latitude': 38.625058333333335, 'longitude': -90.18673611111112})

    def test_exif_location_heic_box(self):

        box = get_box_client()
        infile = get_box_file_as_tempfile(box, 1997129408417)

        exif_data = get_gps_info(infile)
        self.assertEqual(exif_data, {'latitude': 38.625058333333335, 'longitude': -90.18673611111112})

        # delete tempfile
        os.remove(infile)


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

        # Location logic
        # if embedded location in image, save to location_embedded
        # By default, set location_type to park centerpoint and extract location from Park model to set location_final
        # If location type set to US, extract location from location_embedded
        # If manual correction, use manualcorrection value for location_final and location_type_final
    
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
        self.assertEqual(p_2.location_final, p_2.park.centerpoint)
        self.assertEqual(p_2.location_type_final, 'PK')

        # # Now re-import ManualCorrection objects using command and look for cx values again
        # # This is difficult to test with file reload because it causes transaction errors.
        # out = StringIO()
        # call_command('load_manual_corrections', infile=temp_file.name, stdout=out, stderr=StringIO())

        # # mc_2 = ManualCorrection.objects.get(pk=2)
        # p_2 = Photo.objects.get(pk=2)
        # self.assertEqual(p_2.title_final, 'test manual cx title')

    def test_embedded_location_save(self):
        '''P_1 has an embedded location set. By default should still be part centerpoint.
        But if we change the location_type value to US, should use embedded location. If we change it back,
        should use park centroid again'''
        p_1 = Photo.objects.get(pk=1)
        self.assertEqual(p_1.location_final, p_1.park.centerpoint)
        self.assertEqual(p_1.location_type, 'PK')
        self.assertEqual(p_1.location_type_final, 'PK')

        p_1.location_type = 'US'
        p_1.save()
        self.assertEqual(p_1.location_final, p_1.location_embedded)
        self.assertEqual(p_1.location_type_final, 'US')

        p_1.location_type = 'PK'
        p_1.save()
        self.assertEqual(p_1.location_final, p_1.park.centerpoint)
        self.assertEqual(p_1.location_type_final, 'PK')

    def test_new_manual_correction_location_save(self):
        '''Saving a new manual correction with a location should set final location
        to the manual correction location and set location_type to SOS'''

        p_3 = Photo.objects.get(pk=3)
        p_3.save()

        self.assertEqual(p_3.title_final, 'Initial title')
        self.assertEqual(p_3.location_final, p_3.park.centerpoint)
        self.assertEqual(p_3.location_type_final, 'PK')
        self.assertEqual(p_3.location_type, 'PK')

        new_mc = ManualCorrection(
            photo=p_3,
            # photo_file_name = models.CharField(max_length=255, null=True)
            title='test title 3',
            additional_notes='test description 3',
            location=Point(-94.2,46.2),
            comments='test comment 3'
        )
        new_mc.save()

        # p_3 = Photo.objects.get(pk=3)
        self.assertEqual(p_3.title_final, new_mc.title)
        self.assertEqual(p_3.location_final, new_mc.location)
        self.assertEqual(p_3.location_type_final, 'SOS')
        self.assertEqual(p_3.location_type, 'SOS')

        new_mc.delete()

        # p_3 = Photo.objects.get(pk=3)
        self.assertEqual(p_3.title_final, 'Initial title')
        self.assertEqual(p_3.location_final, p_3.park.centerpoint)
        self.assertEqual(p_3.location_type_final, 'PK')
        self.assertEqual(p_3.location_type, 'PK')



