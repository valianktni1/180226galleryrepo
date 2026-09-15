const fs = require('fs');
const path = require('path');

const read = (...parts) => fs.readFileSync(path.join(__dirname, '..', ...parts), 'utf8');
const app = read('src', 'App.js');
const dashboard = read('src', 'pages', 'AdminDashboard.js');
const health = read('src', 'pages', 'AdminSystemHealth.js');
const api = read('src', 'lib', 'api.js');

const requirements = [
  [app, 'path="/admin/health"'],
  [dashboard, 'data-testid="health-btn"'],
  [dashboard, 'data-testid="open-health-panel-btn"'],
  [api, "apiClient.get('/admin/system-health')"],
  [health, 'data-testid="system-health-page"'],
  [health, 'Read-only monitoring'],
  [health, 'setInterval(() => load(true), 15000)'],
  [health, 'This screen cannot restart, delete or change anything.'],
  [health, 'health.protection.database_backup'],
  [health, 'health.protection.offsite_backup'],
];

for (const [source, snippet] of requirements) {
  if (!source.includes(snippet)) {
    throw new Error(`Release 1.7 check failed: missing ${snippet}`);
  }
}

for (const forbidden of ['restartService', 'deleteBackup', 'runCommand']) {
  if (health.includes(forbidden)) {
    throw new Error(`Release 1.7 check failed: health page contains mutation control ${forbidden}`);
  }
}

console.log('Release 1.7 system health checks passed');
