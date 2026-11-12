# Marketplace and photo-gallery refresh

## Result

Listing cards use a single 4:3 cover image, a two-line title, current quantity, location, deadline, one small recovery-category badge and a quiet View listing action. The entire card opens the listing. Match boxes, repeated creation metadata, the extra FREE badge and the filled action shelf are removed; recommendation ordering, nearby sorting and stock updates remain.

The supporting palette uses ivory `#F6F3EB`, white surfaces, charcoal `#20282D` and slate `#596873`. Muted blue `#356A91` identifies information/collection states; terracotta `#A84632` identifies urgent deadlines and problems. Category badges use green for human food, blue for feed and earthy brown for compost. The existing main brand colors remain available for brand elements. Sign-in and registration use neutral form panels without the yellow top stripe, decorative rings or yellow focus treatment.

The Send test phone alert button is removed. Phone notification opt-in/out still works, with copy updated to describe normal account and collection alerts.

## Listing photos

- Up to five photos per listing, each JPG/PNG/WebP and at most 4 MB.
- The first new photo is the default cover; donors can choose another cover.
- Editing supports removing saved photos and adding replacements within the five-photo total. Existing listing edit restrictions still apply.
- Only the cover appears on cards. Listing details show thumbnail navigation for all photos, with keyboard arrow/Home/End support.
- Existing single-cover listings continue working without a data migration.
- Images are resized to at most 1600×1600 and converted to JPEG without source EXIF metadata.
- Additional photos use authenticated URLs and the same visibility rules as their parent listing. Storage remains private.
- Removed images are deleted after commit only when no listing/gallery still references them. Hard-deleting an unused listing also cleans up its additional photos.

Migration `0028_listingphoto` adds four possible additional-photo positions alongside the existing cover field. Database transactions protect gallery reference updates; file uploads themselves remain external storage operations. Failed uploads are cleaned up when the gallery save fails, but a later process/transaction failure can still leave an unreferenced file, as with the existing single-image upload path.

## Verification

- Complete isolated Django suite: 135 tests passed.
- New gallery tests cover five/six uploads, invalid/oversized images, cover changes, edit limits, access controls, legacy covers and cleanup.
- `qa/marketplace_auth_check.py`: 16 rendered pages at 320/390/820/1440px, with automated WCAG A/AA samples at 390/1440px. Includes public account pages, all three account roles, five-photo previews, removal, cover selection and gallery keyboard navigation.
- Production-mode static build and system checks pass.
- Phone opt-in/out browser checks pass without the removed test button.
- Stock refresh, header and installation-control browser checks pass.

Live verification is performed after the release becomes live. Automated accessibility checks do not replace manual accessibility/user acceptance testing.
