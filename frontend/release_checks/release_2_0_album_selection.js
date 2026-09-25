const fs = require('fs');
const path = require('path');

const read = (...parts) => fs.readFileSync(path.join(__dirname, '..', ...parts), 'utf8');
const client = read('src', 'pages', 'ShareView.js');
const admin = read('src', 'pages', 'AdminGalleryDetail.js');
const api = read('src', 'lib', 'api.js');

for (const snippet of [
  'album-selection-guide',
  'Submit Your Album',
  'confirm-album-submission',
  'ready_to_submit',
  'albumLocked',
]) {
  if (!client.includes(snippet)) {
    throw new Error(`Release 2.0 client check failed: missing ${snippet}`);
  }
}

for (const snippet of [
  'album-selection-admin-card',
  'album-mode-${option.mode}',
  '40 + Cover',
  '60 + Cover',
  'Reopen Choices',
  'Email Album Instructions',
]) {
  if (!admin.includes(snippet)) {
    throw new Error(`Release 2.0 admin check failed: missing ${snippet}`);
  }
}

for (const snippet of [
  'updateAlbumSelection',
  'reopenAlbumSelection',
  'sendAlbumSelectionInvitation',
]) {
  if (!api.includes(snippet)) {
    throw new Error(`Release 2.0 API check failed: missing ${snippet}`);
  }
}

console.log('Release 2.0 album selection checks passed');
