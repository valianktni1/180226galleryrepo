const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const api = fs.readFileSync(path.join(root, 'src/lib/api.js'), 'utf8');
const share = fs.readFileSync(path.join(root, 'src/pages/ShareView.js'), 'utf8');
const dashboard = fs.readFileSync(path.join(root, 'src/pages/AdminDashboard.js'), 'utf8');
const health = fs.readFileSync(path.join(root, 'src/pages/AdminSystemHealth.js'), 'utf8');

const required = [
  [api, 'startShareFavouritesDownload'],
  [api, '/favourites-download-jobs'],
  [share, 'startShareFavouritesDownload(token)'],
  [share, 'label: "Favourites"'],
  [dashboard, 'Backup queued'],
  [health, 'heavy_queue'],
  [health, 'backups receive a safe exclusive turn'],
];

for (const [source, marker] of required) {
  if (!source.includes(marker)) throw new Error(`Missing Release 2.1 marker: ${marker}`);
}

for (const legacy of ['/download-subfolder', '/download-zip', '/download-album', '/download-favourites']) {
  if (api.includes(legacy)) throw new Error(`Legacy download API remains: ${legacy}`);
}

console.log('Release 2.1 frontend reliability checks passed');
