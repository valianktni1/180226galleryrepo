# Release 2.4: personal WBM booking intake

Deploy this gallery release before booking V8.80. The connection defaults off.
Gallery Settings → Booking connection creates a key, shown once, stored hashed.
Enable it there, then paste the key into booking Settings → Wedding galleries.
Review package/extra/adjustment folder and album settings there before enabling.

After a new accepted quote's full booking fee is recorded, booking sends the
first names, lead email, wedding date and explicit folder/album flags. No other
couple information is needed. No email or main gallery share is created here.

Creates `John & Nikki 20.10.26`, relevant Wedding Images / Video / SelfieBooth,
Album Favourites plus Off/40/60 album mode, and Guest Uploads only for full-day.
The full-day upload-only guest share uses `johnnikkiguestuploads`, suffix 2, 3…
if occupied. Its expiry is 00:01 UTC on day 3 after the wedding, exactly matching
the established auto-expiry rule. QR-design email is still sent manually.

Retries use an immutable booking request, stable gallery/share IDs, a leased
Mongo reservation and a unique token index. Interrupted creation resumes. Same
folder-name conflicts are flagged, never adopted or merged. Existing completed
galleries and shares are not overwritten or recreated. Manual editing and
creation remain; later package changes are reviewed in booking, not auto-applied.
Protected/imported/old bookings and test records are excluded by booking.

The key only authorises status and new-gallery intake, not admin sign-in,
updates, deletion, email or existing-gallery browsing. Admin key rotation pauses
intake until enabled again and the replacement key is saved in booking.

Validation uses temporary files, mock Mongo, disposable SQLite and intercepted
browser APIs. Backend tests cover auth/pause/rotation, album modes, duplicate
slugs/folders, expiry, changed requests, removed galleries, interrupted creation,
and manual-edit preservation. Existing album/share/path tests pass. Production
React build succeeds with the two pre-existing hook warnings in AdminActivity
and ShareView. Browser checks cover 320/390/1280px, both themes, explicit key
creation/enable and no automatic writes. The real booking worker → real gallery
intake contract creates exactly one gallery/share with no email records.

`deploy-release-2.4.sh` backs up Mongo, checks compressed archive integrity,
retains current images, builds pinned sources, preflights both images and only
then restarts backend/frontend. It does not restart Mongo or alter user files,
live compose, .env or permissions. A private repo uses a prompted GitHub read
token passed only as a BuildKit secret. Rollback command is printed before
building. The same script is available as DEPLOY-GALLERY-V2.4.sh in the public
booking repo for easy download. No planner deployment is required.

Tests: install backend/requirements.txt and backend/requirements-test.txt;
run `PYTHONPATH=backend pytest backend/tests/test_booking_connection.py`.
After frontend production build, run its release_2_4_booking_connection.cjs
with Playwright and WBM_TEST_CHROME pointing to a local Chrome executable.
