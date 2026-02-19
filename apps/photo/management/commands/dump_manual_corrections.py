from django.core.management.base import BaseCommand

from apps.photo.utils.export import dump_cx_model_backups, save_backup_file


class Command(BaseCommand):
    '''Save a CSV of ManualCorrection objects for archiving and later reloading.'''

    # def add_arguments(self, parser):
    #     pass

    def handle(self, *args, **kwargs):
        df = dump_cx_model_backups('photo', 'ManualCorrection')
        outfile = save_backup_file(df, 'manualcorrection')
        return outfile
