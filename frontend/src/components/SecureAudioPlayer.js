import { useEffect, useState } from "react";
import { Download, Loader2, Mic2, Play } from "lucide-react";

const formatDuration = (seconds) => {
  const whole = Math.max(0, Math.round(Number(seconds) || 0));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
};

export default function SecureAudioPlayer({ file, fetchAudio, onDownload, theme = {}, compact = false }) {
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  const loadAudio = async (event) => {
    event?.stopPropagation();
    if (audioUrl || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetchAudio();
      if (!response.ok) throw new Error("Audio download failed");
      const blob = await response.blob();
      setAudioUrl(URL.createObjectURL(blob));
    } catch {
      setError("Could not load this message");
    } finally {
      setLoading(false);
    }
  };

  const accent = theme.accent || '#D4AF37';
  const text = theme.text || 'var(--admin-text, #1C1917)';
  const muted = theme.textSub || 'var(--admin-muted, #78716C)';
  const surface = theme.bgCard || 'var(--admin-surface-raised, #F5F2EB)';

  return (
    <div
      className={`w-full h-full flex flex-col items-center justify-center text-center ${compact ? 'p-3' : 'p-5'}`}
      style={{ backgroundColor: surface, color: text }}
      onClick={(event) => event.stopPropagation()}
      data-testid={`audio-message-${file.id}`}
    >
      <div className="w-11 h-11 rounded-full flex items-center justify-center mb-2" style={{ backgroundColor: `${accent}22` }}>
        <Mic2 className="w-5 h-5" style={{ color: accent }} />
      </div>
      <p className="text-sm font-semibold leading-tight line-clamp-2" style={{ color: text }}>
        {file.guest_name || 'Wedding guest'}
      </p>
      <p className="text-[11px] mt-1 mb-3" style={{ color: muted }}>
        Personal message &middot; {formatDuration(file.duration_seconds)}
      </p>

      {!audioUrl ? (
        <button
          type="button"
          onClick={loadAudio}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-semibold text-white disabled:opacity-60"
          style={{ backgroundColor: accent }}
          aria-label={`Listen to the personal message from ${file.guest_name || 'wedding guest'}`}
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" fill="white" />}
          {loading ? 'Loading…' : 'Listen'}
        </button>
      ) : (
        <audio
          controls
          autoPlay
          preload="metadata"
          src={audioUrl}
          className="w-full h-9"
          onClick={(event) => event.stopPropagation()}
        />
      )}
      {onDownload && (
        <button type="button" onClick={(event) => { event.stopPropagation(); onDownload(file); }}
          className="inline-flex items-center gap-1 mt-2 text-[11px] font-semibold" style={{ color: accent }}
          aria-label={`Download the personal message from ${file.guest_name || 'wedding guest'}`}>
          <Download className="w-3 h-3" /> Download MP3
        </button>
      )}
      {error && <p className="text-[10px] text-red-600 mt-2">{error}</p>}
    </div>
  );
}

