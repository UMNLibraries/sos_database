import os

from django.core.management.base import BaseCommand

from apps.photo.utils.export import build_public_manifest

from django.conf import settings


class Command(BaseCommand):

    DATA_DIR = os.path.join(settings.BASE_DIR, 'data')
    SITE_MANIFEST_DIR = os.path.join(DATA_DIR, 'site_manifests')
    
    def handle(self, *args, **kwargs):
        print(f"Exporting main manifest...")
        main_manifest_df = build_public_manifest()
        print(f"Found {main_manifest_df.shape[0]} live images.")
        main_manifest_path = os.path.join(self.DATA_DIR, 'public_manifest_main.csv')
        main_manifest_df.to_csv(main_manifest_path, index=False)

        site_codes = main_manifest_df['site_code'].drop_duplicates().to_list()
        print(f"Exporting {len(site_codes)} site manifests...")

        os.makedirs(self.SITE_MANIFEST_DIR, exist_ok=True)

        for site_code in site_codes:
            site_manifest_df = main_manifest_df[main_manifest_df['site_code'] == site_code]
            site_manifest_path = os.path.join(self.SITE_MANIFEST_DIR, f'sos_public_manifest_{site_code}.xlsx')
            site_manifest_df.to_excel(site_manifest_path, index=False)
