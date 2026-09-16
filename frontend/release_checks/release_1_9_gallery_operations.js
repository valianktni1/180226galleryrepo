const fs = require('fs');
const path = require('path');

const read = (...parts) => fs.readFileSync(path.join(__dirname, '..', ...parts), 'utf8');
const detail = read('src', 'pages', 'AdminGalleryDetail.js');
const health = read('src', 'pages', 'AdminSystemHealth.js');
const api = read('src', 'lib', 'api.js');

for (const snippet of [
  'getGalleryReadiness', 'galleryReadiness', 'Gallery Ready Check',
  'Videos never delay this step', 'confirm-gallery-notification',
  'galleryReadiness.preview.gallery_link', 'galleryReadiness.preview.password',
]) {
  if (!detail.includes(snippet) && !api.includes(snippet)) {
    throw new Error(`Release 1.9 readiness check failed: missing ${snippet}`);
  }
}

for (const snippet of [
  'runMaintenanceScan', 'Safe Scan', 'video-processing-queue',
  'maintenance-results', 'This screen cannot restart, delete or change anything',
]) {
  if (!health.includes(snippet) && !api.includes(snippet)) {
    throw new Error(`Release 1.9 operations check failed: missing ${snippet}`);
  }
}

console.log('Release 1.9 gallery operations checks passed');
