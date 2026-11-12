"""Save gallery references atomically and remove unreferenced files after commit."""
from django.db import transaction
from .models import Listing, ListingPhoto


def schedule_photo_cleanup(storage, names):
    for name in set(names):
        if not name:
            continue
        def cleanup(name=name):
            if not Listing.objects.filter(photo=name).exists() and not ListingPhoto.objects.filter(image=name).exists():
                storage.delete(name)
        transaction.on_commit(cleanup, robust=True)


@transaction.atomic
def save_gallery(listing, items, cover_token, previous_names):
    field = Listing._meta.get_field('photo')
    storage = field.storage
    uploaded, resolved = [], []
    try:
        for token, photo in items:
            if getattr(photo, '_committed', False):
                name = photo.name
            else:
                name = storage.save(field.generate_filename(listing, photo.name), photo)
                uploaded.append(name)
            resolved.append((token, name))
        cover = next((name for token, name in resolved if token == cover_token), resolved[0][1] if resolved else '')
        remaining = [name for token, name in resolved if token != cover_token]
        if resolved and cover_token not in {token for token, _ in resolved}:
            remaining = [name for _, name in resolved][1:]
        listing.extra_photos.all().delete()
        Listing.objects.filter(pk=listing.pk).update(photo=cover)
        listing.photo = cover
        ListingPhoto.objects.bulk_create([ListingPhoto(listing=listing, image=name, position=index)
                                         for index, name in enumerate(remaining)])
    except Exception:
        for name in uploaded:
            storage.delete(name)
        raise
    schedule_photo_cleanup(storage, set(previous_names) - {name for _, name in resolved})
