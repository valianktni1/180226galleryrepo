const fs = require('fs');
const path = require('path');

const gallery = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'pages', 'AdminGalleryDetail.js'),
  'utf8'
);
const api = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'lib', 'api.js'),
  'utf8'
);

const galleryRequirements = [
  'data-testid="add-subfolder-btn"',
  'data-testid="new-subfolder-name"',
  'data-testid="confirm-add-subfolder"',
  'createSubfolder(id, name)',
  'subfolders: res.data.subfolders',
  'file_counts: res.data.file_counts',
  'name="new-share-password" autoComplete="new-password"',
  'name="edit-share-password" autoComplete="new-password"',
];

for (const snippet of galleryRequirements) {
  if (!gallery.includes(snippet)) {
    throw new Error(`Release 1.5 check failed: missing ${snippet}`);
  }
}

if (!api.includes("apiClient.post(`/admin/galleries/${galleryId}/subfolders`, { name })")) {
  throw new Error('Release 1.5 check failed: Add Folder API client is missing');
}

console.log('Release 1.5 Add Folder and password autofill checks passed');
