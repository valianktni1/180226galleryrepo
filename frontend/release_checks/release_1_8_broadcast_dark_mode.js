const fs = require('fs');
const path = require('path');

const read = (...parts) => fs.readFileSync(path.join(__dirname, '..', ...parts), 'utf8');
const dashboard = read('src', 'pages', 'AdminDashboard.js');
const detail = read('src', 'pages', 'AdminGalleryDetail.js');
const settings = read('src', 'pages', 'AdminSettings.js');
const activity = read('src', 'pages', 'AdminActivity.js');
const health = read('src', 'pages', 'AdminSystemHealth.js');
const toggle = read('src', 'components', 'AdminThemeToggle.js');
const api = read('src', 'lib', 'api.js');
const css = read('src', 'App.css');

for (const snippet of [
  'getCurrentBroadcastCampaign', 'pauseBroadcastCampaign', 'resumeBroadcastCampaign',
  'cancelBroadcastCampaign', 'data-testid="broadcast-progress"',
  'setInterval(poll, 5000)', 'Next batch in', 'A broadcast is already active',
]) {
  if (!dashboard.includes(snippet) && !api.includes(snippet)) {
    throw new Error(`Release 1.8 check failed: missing ${snippet}`);
  }
}

for (const [name, source] of Object.entries({ dashboard, detail, settings, activity, health })) {
  if (!source.includes('<AdminThemeToggle />') || !source.includes('data-admin-page')) {
    throw new Error(`Release 1.8 check failed: ${name} is not dark-mode scoped`);
  }
}

for (const snippet of ['wbm_admin_theme', 'document.documentElement.classList.toggle("admin-dark"', 'document.documentElement.classList.remove("admin-dark"']) {
  if (!toggle.includes(snippet)) throw new Error(`Release 1.8 check failed: missing ${snippet}`);
}
for (const snippet of ['html.admin-dark', '--admin-bg:', '[data-admin-page]']) {
  if (!css.includes(snippet)) throw new Error(`Release 1.8 check failed: missing CSS ${snippet}`);
}

console.log('Release 1.8 broadcast and admin dark-mode checks passed');
