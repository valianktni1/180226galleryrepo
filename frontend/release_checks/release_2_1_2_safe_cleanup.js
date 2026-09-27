const fs = require('fs');
const path = require('path');

const read = (...parts) => fs.readFileSync(path.join(__dirname, '..', ...parts), 'utf8');
const api = read('src', 'lib', 'api.js');
const health = read('src', 'pages', 'AdminSystemHealth.js');

for (const marker of [
  'runMaintenanceCleanup',
  '/admin/maintenance-cleanup',
  'DELETE GENERATED FILES',
]) {
  if (!api.includes(marker)) throw new Error(`Missing Release 2.1.2 API marker: ${marker}`);
}

for (const marker of [
  'Review cleanup',
  'Protected orphan web videos',
  'Original photographs, original videos, backups and database records are never included.',
  'confirm-maintenance-cleanup',
]) {
  if (!health.includes(marker)) throw new Error(`Missing Release 2.1.2 UI marker: ${marker}`);
}

console.log('Release 2.1.2 safe cleanup frontend checks passed');
