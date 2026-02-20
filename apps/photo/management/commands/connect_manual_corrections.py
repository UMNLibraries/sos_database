from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Subquery, OuterRef, F

from apps.photo.models import Photo, ManualCorrection
from apps.photo.utils.export import fill_final_value


class Command(BaseCommand):
    '''Connect newly loaded or reloaded Zooniverse data to existing
    ManualCorrection objects, and set initial "final" values.'''
    batch_config = None  # Set in handle

    # def add_arguments(self, parser):
    #     parser.add_argument('-w', '--workflow', type=str,
    #                         help='Name of Zooniverse workflow to process, e.g. "Ramsey County"')

    def reconnect_manual_corrections(self):
        cx_objs = ManualCorrection.objects.all().only('pk', 'photo_file_name')

        cx_photo_ids = cx_objs.values_list('photo_file_name', flat=True)

        cx_photos_lookup = {sbj['photo_file_name']: sbj['pk'] for sbj in Photo.objects.filter(
            photo_file_name__in=cx_photo_ids
        ).values('pk', 'photo_file_name')}
        print(len(cx_photos_lookup.keys()))

        print(
            f'Attaching {cx_objs.count()} ManualCorrection objects to photo objects...')
        update_cxes = []
        for cx in cx_objs:
            cx.photo_id = cx_photos_lookup[cx.photo_file_name]
            update_cxes.append(cx)
        ManualCorrection.objects.bulk_update(
            update_cxes, ['photo_id'], batch_size=10000)

    def set_string_final(self, attr_root, include_blanks=True):
        null_kwargs = {f'manualcorrection__{attr_root}__isnull': True}
        
        if include_blanks:
            ''' Some fields like geometry don't like blanks even in a filter '''
            blank_kwargs = {f'manualcorrection__{attr_root}__exact': ''}
        else:
            blank_kwargs = {}

        null_kwargs_cx = {f'{attr_root}__isnull': True}

        if include_blanks:
            blank_kwargs_cx = {f'{attr_root}__exact': ''}
        else:
            blank_kwargs_cx = {}

        # This is crazy town, but updating in bulk across foreign keys isn't for wimps
        update_kwargs_outer = {
            f'{attr_root}_final': Subquery(
                ManualCorrection.objects.filter(
                    photo=OuterRef('pk')
                ).exclude(
                    **null_kwargs_cx
                ).exclude(
                    **blank_kwargs_cx
                ).values(attr_root)[:1]
            )
        }

        print(Photo.objects.exclude(
            **null_kwargs
        ).exclude(
            **blank_kwargs
        ).count())

        Photo.objects.exclude(
            **null_kwargs
        ).exclude(
            **blank_kwargs
        ).update(
            **update_kwargs_outer
        )

    def set_final_values(self):
        '''Once you are saving subjects one by one, the code in the model definition handles this. But you need to set initial values all at once, rather than looping through each.'''
        print('Setting "final" values, taking into account re-connected ManualCorrections')

        Photo.objects.filter(
            manualcorrection__isnull=False
        ).update(
            bool_manual_correction=True
        )

        # manually_cxed_subjects = ManualCorrection.objects.all().values_list('photo_file_name', flat=True)

        # Photo.objects.filter(
        #     photo_file_name__in=manually_cxed_subjects
        #     # manualcorrection__bool_covenant__isnull=False
        # ).update(
        #     bool_covenant_final=Subquery(
        #         ManualCorrection.objects.filter(
        #             photo=OuterRef('pk')
        #         ).values('bool_covenant')[:1]
        #     )
        # )

        # Photo.objects.filter(
        #     manualcorrection__deed_date__isnull=False
        # ).update(
        #     deed_date_final=Subquery(
        #         ManualCorrection.objects.filter(
        #             zooniverse_subject=OuterRef('pk')
        #         ).values('deed_date')[:1]
        #     )
        # )

        self.set_string_final('title')
        self.set_string_final('additional_notes')
        self.set_string_final('location', False)  # This needs to be fancier
        self.set_string_final('location_type')

        print('Set everything else w/o manualcorrection to initial import value...')
        # Photo.objects.filter(
        #     manualcorrection__isnull=True
        # ).update(
        #     bool_manual_correction=False,
        #     bool_covenant_final=F('bool_covenant'),
        #     covenant_text_final=F('covenant_text'),
        #     addition_final=F('addition'),
        #     lot_final=F('lot'),
        #     block_final=F('block'),
        #     map_book_final=F('map_book'),
        #     map_book_page_final=F('map_book_page'),
        #     seller_final=F('seller'),
        #     buyer_final=F('buyer'),
        #     deed_date_final=F('deed_date'),
        #     match_type_final=F('match_type'),
        # )
        for attr in ['title', 'additional_notes', 'location', 'location_type']:
            fill_final_value(attr)

    def handle(self, *args, **kwargs):

            self.reconnect_manual_corrections()
            self.set_final_values()
