const fs = require('fs');
const path = require('path');

const detail = fs.readFileSync(
  path.resolve(__dirname, '..', 'src', 'pages', 'AdminGalleryDetail.js'),
  'utf8'
);

const checks = [
  [detail.includes('const THUMBNAIL_FILE_TYPES = new Set(["photo", "video"])'), 'only photos and videos trigger thumbnail polling'],
  [detail.includes('THUMBNAIL_FILE_TYPES.has(f.file_type) && !f.has_thumb'), 'audio and document records cannot start thumbnail polling'],
  [detail.includes('const THUMBNAIL_POLL_MAX_ATTEMPTS = 60'), 'thumbnail polling has a finite retry limit'],
  [detail.includes('thumbPollAttemptsRef.current > THUMBNAIL_POLL_MAX_ATTEMPTS'), 'failed thumbnail jobs stop polling'],
  [detail.includes('setActiveTab(currentTab => currentTab || res.data.subfolders[0])'), 'first tab is selected without recreating the loader'],
  [detail.includes('}, [id, navigate]);'), 'gallery loader is independent of the active tab'],
];

const failed = checks.filter(([passed]) => !passed).map(([, label]) => label);
if (failed.length) {
  console.error(`Release 2.2.3 performance checks failed: ${failed.join(', ')}`);
  process.exit(1);
}

console.log('Release 2.2.3 frontend performance checks passed');
