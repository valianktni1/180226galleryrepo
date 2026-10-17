const fs = require('fs');
const path = require('path');

const read = (file) => fs.readFileSync(path.resolve(__dirname, '..', file), 'utf8');
const app = read('src/App.js');
const api = read('src/lib/api.js');
const dashboard = read('src/pages/AdminDashboard.js');
const detail = read('src/pages/AdminGalleryDetail.js');
const notifications = read('src/pages/AdminNotifications.js');
const mobileNav = read('src/components/AdminMobileNav.js');

const checks = [
  [app.includes('/admin/notifications') && app.includes('<AdminMobileNav />'), 'notification route and mobile nav'],
  [api.includes('getAdminNotifications') && api.includes('updateGalleryWorkflowStatus'), 'admin centre API helpers'],
  [dashboard.includes('notifications-btn') && dashboard.includes('workflowLabels'), 'dashboard updates and gallery status badges'],
  [detail.includes('gallery-status-journey') && detail.includes('album_choices_received'), 'gallery status journey'],
  [notifications.includes('Notification Centre') && notifications.includes('Mark all read'), 'notification centre interface'],
  [['Galleries', 'Uploads', 'Activity', 'Health', 'Settings'].every((label) => mobileNav.includes(label)), 'five mobile admin shortcuts'],
];

for (const [passed, label] of checks) {
  if (!passed) {
    console.error(`Release 2.3 check failed: ${label}`);
    process.exit(1);
  }
}

console.log('Release 2.3 admin centre checks passed');
