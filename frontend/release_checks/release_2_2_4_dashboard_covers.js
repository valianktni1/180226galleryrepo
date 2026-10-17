const fs = require('fs');
const path = require('path');

const dashboard = fs.readFileSync(
  path.resolve(__dirname, '..', 'src', 'pages', 'AdminDashboard.js'),
  'utf8'
);

const coverImagePattern = /g\.cover_thumb[\s\S]*?<img[\s\S]*?loading="lazy"\s+decoding="async"[\s\S]*?className="w-full h-full object-cover"/;

if (!coverImagePattern.test(dashboard)) {
  console.error('Release 2.2.4 check failed: dashboard gallery covers must lazy-load and decode asynchronously');
  process.exit(1);
}

console.log('Release 2.2.4 dashboard cover checks passed');
