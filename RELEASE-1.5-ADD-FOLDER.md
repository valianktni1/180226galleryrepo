# Release 1.5 - Add Folder

## Purpose

This release lets Mark add a missing folder to an existing gallery without
recreating the gallery, moving files or changing its share links. It also stops
browsers and common password managers from unexpectedly filling the password
field when a share is created or edited.

## Add Folder

- A compact `Add Folder` control appears beside the existing folder tabs.
- Standard missing folders are offered as quick choices, including
  `Album Favourites`.
- A custom folder name can also be entered.
- The backend validates the name and proves that its path remains within the
  selected gallery.
- Empty names, path characters, unsafe names and case-insensitive duplicates
  are refused.
- The physical folder, gallery folder list and zero file count are created
  together.
- The newly added folder opens immediately in the admin gallery.

## Share password autofill

- Create Share and Edit Share password inputs now identify themselves as new
  passwords and opt out of common password-manager autofill.
- Passwords can still be entered, generated, changed or removed deliberately.
- Existing share passwords are unchanged.

## Unchanged

- Existing gallery folders and files.
- Whole-gallery and folder-specific share links.
- Uploads, downloads, favourites, album submission and cover selection.
- Backups and the 90-day Guest Upload cleanup.
- Video transcoding, GPU acceleration and playback.
- MongoDB data belonging to existing galleries.

## Deployment

Both backend and frontend change in this release. They should be built and
tested before recreating either live container. MongoDB and NGINX video do not
need rebuilding or restarting.
