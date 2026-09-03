const fs = require('fs');
const path = require('path');

const shareViewPath = path.join(__dirname, '..', 'src', 'pages', 'ShareView.js');
const source = fs.readFileSync(shareViewPath, 'utf8');

const requiredSnippets = [
  "window.scrollTo(0, 0)",
  "window.requestAnimationFrame(() => window.scrollTo(0, 0))",
  "const folderDownloadLabel = `Download All ${currentAlbumFiles.length} ${folderDownloadItemLabel}`",
  'data-testid="download-all-folder-btn"',
  'permissions.allowDownloads && currentAlbumFiles.length > 0',
  'permissions.allowDownloads && currentAlbumFiles.length > 0 && !selectMode',
  'aria-label={folderDownloadLabel}',
  '<span className="sm:hidden">{downloading ? "..." : `All (${currentAlbumFiles.length})`}</span>',
  'onClick={handleDownloadAlbum}',
];

for (const snippet of requiredSnippets) {
  if (!source.includes(snippet)) {
    throw new Error(`Release 1.3 check failed: missing ${snippet}`);
  }
}

if (source.includes('data-testid="download-all-images-btn"')) {
  throw new Error('Release 1.3 check failed: old photo-only bulk button is still present');
}

const folderButtonIndex = source.indexOf('data-testid="download-all-folder-btn"');
const emptyFolderIndex = source.indexOf('{currentAlbumFiles.length === 0 ?', folderButtonIndex);
if (folderButtonIndex < 0 || emptyFolderIndex < folderButtonIndex) {
  throw new Error('Release 1.3 check failed: folder button is not placed above the file grid');
}

console.log('Release 1.3 download visibility checks passed');
