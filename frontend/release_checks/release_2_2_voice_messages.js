const fs = require('fs');
const path = require('path');

const frontend = path.resolve(__dirname, '..', 'src');
const read = (relative) => fs.readFileSync(path.join(frontend, relative), 'utf8');
const guest = read('pages/GuestUploadView.js');
const recorder = read('components/VoiceMessageRecorder.js');
const player = read('components/SecureAudioPlayer.js');
const share = read('pages/ShareView.js');
const admin = read('pages/AdminGalleryDetail.js');
const api = read('lib/api.js');

const checks = [
  [guest.includes('Upload Photos') && guest.includes('Videos') && guest.includes('Record Your Personal Message'), 'guest choice screen'],
  [guest.includes('VoiceMessageRecorder') && guest.includes('gallery_dark_mode'), 'recorder and theme wiring'],
  [recorder.includes('const MAX_SECONDS = 240') && recorder.includes('const WARNING_SECONDS = 210'), 'four-minute timer'],
  [recorder.includes('MediaRecorder') && recorder.includes('audioBitsPerSecond: 192000'), 'browser recording settings'],
  [recorder.includes('createAudioRecorder') && recorder.includes('recorder.start();'), 'cross-mobile recorder fallback'],
  [recorder.includes('Listen before you send') && recorder.includes('Re-record'), 'review workflow'],
  [player.includes('Download MP3') && player.includes('<audio'), 'secure audio controls'],
  [share.includes("file_type === 'audio'") && admin.includes("file_type === 'audio'"), 'couple and admin audio cards'],
  [api.includes('/voice-message') && api.includes('/audio/'), 'voice API wiring'],
];

const failed = checks.filter(([passed]) => !passed).map(([, label]) => label);
if (failed.length) {
  console.error(`Release 2.2 frontend checks failed: ${failed.join(', ')}`);
  process.exit(1);
}
console.log('Release 2.2 frontend source checks passed');
