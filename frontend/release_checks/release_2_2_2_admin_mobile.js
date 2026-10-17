const fs = require('fs');
const path = require('path');

const frontend = path.resolve(__dirname, '..', 'src');
const read = (relative) => fs.readFileSync(path.join(frontend, relative), 'utf8');
const dashboard = read('pages/AdminDashboard.js');
const detail = read('pages/AdminGalleryDetail.js');
const css = read('index.css');

const checks = [
  [dashboard.includes('data-testid="admin-mobile-toolbar"') && dashboard.includes('overflow-x-auto lg:w-auto'), 'dashboard toolbar is locally scrollable'],
  [detail.includes('data-testid="admin-gallery-mobile-toolbar"') && detail.includes('overflow-x-auto lg:w-auto'), 'gallery toolbar is locally scrollable'],
  [dashboard.includes('w-full min-w-0 overflow-x-hidden') && detail.includes('w-full min-w-0 overflow-x-hidden'), 'admin pages cannot widen the phone viewport'],
  [dashboard.includes('flex flex-col sm:flex-row sm:items-center') && dashboard.includes('w-full sm:w-64'), 'dashboard sort and search stack on phones'],
  [detail.includes('grid grid-cols-1 sm:grid-cols-2 gap-2') && detail.includes('flex flex-col sm:flex-row sm:items-center gap-2'), 'share form stacks narrow controls'],
  [detail.includes('admin-mobile-dialog') && dashboard.includes('admin-mobile-dialog'), 'admin dialogs opt into phone sizing'],
  [css.includes('@media (max-width: 767px)') && css.includes('.admin-mobile-dialog') && css.includes('max-width: none !important'), 'admin dialog mobile viewport guard'],
];

const failed = checks.filter(([passed]) => !passed).map(([, label]) => label);
if (failed.length) {
  console.error(`Release 2.2.2 admin mobile checks failed: ${failed.join(', ')}`);
  process.exit(1);
}

console.log('Release 2.2.2 admin mobile source checks passed');
