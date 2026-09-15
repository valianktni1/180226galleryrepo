const fs = require('fs');
const path = require('path');

const read = (...parts) => fs.readFileSync(path.join(__dirname, '..', ...parts), 'utf8');
const admin = read('src', 'pages', 'AdminGalleryDetail.js');
const share = read('src', 'pages', 'ShareView.js');
const api = read('src', 'lib', 'api.js');
const progress = read('src', 'components', 'DownloadJobProgress.js');

const requirements = [
  [admin, 'startAdminFolderDownload(id, activeTab)'],
  [admin, 'getAdminFolderDownloadStatus(jobId)'],
  [admin, '<DownloadJobProgress job={downloadJob} />'],
  [share, 'startShareFolderDownload(token, activeAlbum)'],
  [share, 'getShareFolderDownloadStatus(token, jobId)'],
  [share, '<DownloadJobProgress job={downloadJob} accent={t.accent}'],
  [api, '/download-jobs/${encodeURIComponent(jobId)}/file?ticket='],
  [progress, 'data-testid="folder-download-progress"'],
  [progress, 'Preparing ZIP: ${percent}%'],
  [progress, 'Downloading: ${percent}%'],
  [progress, 'Download complete'],
];

for (const [source, snippet] of requirements) {
  if (!source.includes(snippet)) {
    throw new Error(`Release 1.6 check failed: missing ${snippet}`);
  }
}

const adminHandler = admin.slice(admin.indexOf('const handleDownloadAll'), admin.indexOf('const handleDownloadSingleFile'));
if (adminHandler.includes('.blob()') || adminHandler.includes('URL.createObjectURL')) {
  throw new Error('Release 1.6 check failed: admin folder ZIP still loads into browser memory');
}

console.log('Release 1.6 folder download progress checks passed');
