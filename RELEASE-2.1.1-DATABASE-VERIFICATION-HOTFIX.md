# Release 2.1.1 — Database Verification Hotfix

Release 2.1.1 corrects the temporary database name used by the Release 2.1
restore-verification check.

The original name combined the production database name, a descriptive suffix
and a UUID. For this installation that produced a 64-character name, while
MongoDB permits at most 63 characters. MongoDB therefore rejected the temporary
verification database before any restore took place.

The temporary name is now a short fixed prefix plus a unique UUID. A regression
test creates 100 names and confirms that every one is unique and within the
MongoDB limit.

This hotfix does not alter the live database, gallery files, share links,
passwords, favourites, album choices or email settings.
