const fs = require('fs');
const path = require('path');

const dashboard = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'pages', 'AdminDashboard.js'),
  'utf8'
);
const api = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'lib', 'api.js'),
  'utf8'
);

const dashboardRequirements = [
  'getBackupStatus',
  'setInterval(pollBackupStatus, 2000)',
  'status.status === "running"',
  'backupStatus.galleries_done',
  'backupStatus.galleries_total',
  'disabled={backingUp}',
];

for (const snippet of dashboardRequirements) {
  if (!dashboard.includes(snippet)) {
    throw new Error(`Release 1.4 check failed: missing ${snippet}`);
  }
}

if (!api.includes("apiClient.get('/admin/backup/status')")) {
  throw new Error('Release 1.4 check failed: backup status API client is missing');
}

console.log('Release 1.4 backup responsiveness checks passed');
