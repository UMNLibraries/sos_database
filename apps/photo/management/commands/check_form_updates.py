from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    
    def handle(self, *args, **kwargs):
        '''2-in-1 management command to check Qualtrics forms for new entries, then update any images found.'''
        call_command('import_photos_box')
        call_command('box_photos_to_private_s3')


        
