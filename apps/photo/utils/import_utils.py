from apps.photo.models import Photo, Collection


def set_collections(df):
    '''Create collections and assign images to them for non-qualtrics entries'''
    collection_names = df[df['collection'] != 'qualtrics']['collection'].drop_duplicates().to_list()

    PhotoCollectionRelation = Photo.collections.through

    for collection in collection_names:
        collection_file_name_list = df[df['collection'] == collection].photo_file_name.to_list()
        print(collection)

        matching_photo_pks = Photo.objects.filter(photo_file_name__in=collection_file_name_list).values_list('pk', flat=True)

        collection_obj, created = Collection.objects.get_or_create(
            name=collection
        )

        relations_to_create = []
        for photo_pk in matching_photo_pks:
            relations_to_create.append(
                PhotoCollectionRelation(collection_id=collection_obj.id, photo_id=photo_pk)
            )

        PhotoCollectionRelation.objects.bulk_create(relations_to_create, ignore_conflicts=True)
