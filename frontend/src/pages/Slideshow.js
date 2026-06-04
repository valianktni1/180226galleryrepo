import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { previewUrl, slideshowMusicUrl } from "@/lib/api";
import { X, Play, Pause, Volume2, VolumeX, Music, Share2 } from "lucide-react";

// ─── MUSIC TRACKS ───
const TRACKS = [
  { id: 'romantic', file: 'romantic.mp3', name: 'Romantic', desc: 'Soft & tender' },
  { id: 'cinematic', file: 'cinematic.mp3', name: 'Cinematic', desc: 'Grand & sweeping' },
  { id: 'eternity', file: 'eternity.mp3', name: 'Eternity', desc: 'Dreamy & gentle' },
];

// ─── KEN BURNS ───
const kenBurnsPresets = [
  { toScale: 1.12, toX: -2,  toY: -1.5 },
  { toScale: 1.10, toX: 2,   toY: -1   },
  { toScale: 1.14, toX: -1,  toY: 1.5  },
  { toScale: 1.11, toX: 1.5, toY: 1    },
  { toScale: 1.13, toX: 0,   toY: -2   },
  { toScale: 1.10, toX: 0,   toY: 1.5  },
  { toScale: 1.15, toX: 0,   toY: 0    },
  { toScale: 1.08, toX: -2,  toY: 0    },
];

function randomKB() {
  return kenBurnsPresets[Math.floor(Math.random() * kenBurnsPresets.length)];
}

const SLIDE_DISPLAY_MS = 6000;
const CROSSFADE_MS = 2000;
const KB_DURATION_S = 9;
const INTRO_DURATION_MS = 4000;

// ─── MUSIC PICKER SCREEN ───
function MusicPicker({ coupleName, photoCount, onStart, onClose }) {
  const [previewingId, setPreviewingId] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const audioRef = useRef(null);

  const togglePreview = (track) => {
    if (previewingId === track.id) {
      // Stop preview
      if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
      setPreviewingId(null);
    } else {
      // Stop any current preview
      if (audioRef.current) { audioRef.current.pause(); }
      const audio = new Audio(slideshowMusicUrl(track.file));
      audio.volume = 0.4;
      audio.play().catch(() => {});
      // Play just 12 seconds as preview
      setTimeout(() => {
        if (audioRef.current === audio) {
          audio.pause();
          setPreviewingId(null);
        }
      }, 12000);
      audioRef.current = audio;
      setPreviewingId(track.id);
      setSelectedId(track.id);
    }
  };

  const handleStart = () => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    onStart(selectedId);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (audioRef.current) { audioRef.current.pause(); } };
  }, []);

  return (
    <div className="fixed inset-0 z-[9999] bg-black flex items-center justify-center" data-testid="music-picker">
      <button
        onClick={onClose}
        className="absolute top-6 right-6 w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer z-10"
        style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.12)' }}
        data-testid="music-picker-close"
      >
        <X className="w-4 h-4 text-white/70" />
      </button>

      <div className="text-center px-6 max-w-lg w-full">
        {/* Header */}
        <div className="flex items-center justify-center gap-4 mb-3">
          <div className="h-px w-12" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
          <Music className="w-5 h-5 text-[#D4AF37]" />
          <div className="h-px w-12" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
        </div>
        <p className="text-white/40 text-xs tracking-[0.3em] uppercase mb-3" style={{ fontFamily: 'Manrope, sans-serif' }}>
          Choose Your Soundtrack
        </p>
        <h2
          className="text-white text-3xl md:text-4xl font-light italic mb-2"
          style={{ fontFamily: 'Cormorant Garamond, serif' }}
        >
          {coupleName}
        </h2>
        <p className="text-white/30 text-xs mb-10" style={{ fontFamily: 'Manrope, sans-serif' }}>
          {photoCount} moments
        </p>

        {/* Track List */}
        <div className="space-y-3 mb-10">
          {TRACKS.map((track) => (
            <button
              key={track.id}
              onClick={() => togglePreview(track)}
              data-testid={`track-${track.id}`}
              className="w-full flex items-center gap-4 px-5 py-4 rounded-lg transition-all duration-300 cursor-pointer group"
              style={{
                backgroundColor: selectedId === track.id ? 'rgba(212,175,55,0.12)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${selectedId === track.id ? 'rgba(212,175,55,0.4)' : 'rgba(255,255,255,0.08)'}`,
              }}
            >
              {/* Play/Pause indicator */}
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300"
                style={{
                  backgroundColor: previewingId === track.id ? 'rgba(212,175,55,0.3)' : 'rgba(255,255,255,0.08)',
                  border: `1px solid ${previewingId === track.id ? '#D4AF37' : 'rgba(255,255,255,0.1)'}`,
                }}
              >
                {previewingId === track.id ? (
                  <Pause className="w-4 h-4 text-[#D4AF37]" />
                ) : (
                  <Play className="w-4 h-4 text-white/50 group-hover:text-white/80 ml-0.5" />
                )}
              </div>
              <div className="text-left flex-1">
                <p className="text-sm font-medium" style={{
                  fontFamily: 'Manrope, sans-serif',
                  color: selectedId === track.id ? '#D4AF37' : 'rgba(255,255,255,0.8)',
                }}>{track.name}</p>
                <p className="text-xs" style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'Manrope, sans-serif' }}>
                  {track.desc}
                </p>
              </div>
              {/* Selection check */}
              {selectedId === track.id && (
                <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ backgroundColor: '#D4AF37' }}>
                  <svg className="w-3 h-3 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
            </button>
          ))}
        </div>

        {/* Start buttons */}
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleStart}
            disabled={!selectedId}
            data-testid="start-slideshow-btn"
            className="px-8 py-3 rounded-full text-sm tracking-wider uppercase transition-all duration-300 cursor-pointer"
            style={{
              fontFamily: 'Manrope, sans-serif',
              fontWeight: 600,
              backgroundColor: selectedId ? '#D4AF37' : 'rgba(255,255,255,0.06)',
              color: selectedId ? '#1C1917' : 'rgba(255,255,255,0.25)',
              border: `1px solid ${selectedId ? '#D4AF37' : 'rgba(255,255,255,0.08)'}`,
              opacity: selectedId ? 1 : 0.5,
            }}
          >
            Start Slideshow
          </button>
          <button
            onClick={() => onStart(null)}
            data-testid="start-no-music-btn"
            className="text-xs tracking-wide cursor-pointer transition-colors duration-200 hover:text-white/50"
            style={{ color: 'rgba(255,255,255,0.25)', fontFamily: 'Manrope, sans-serif' }}
          >
            or continue without music
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── SLIDESHOW COMPONENT ───
export default function Slideshow({ photos, galleryId, coupleName, onClose, shareToken }) {
  const [phase, setPhase] = useState('picking'); // 'picking' | 'intro' | 'playing'
  const [chosenTrack, setChosenTrack] = useState(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [activeLayer, setActiveLayer] = useState('A');
  const [layerA, setLayerA] = useState({ index: 0, kb: randomKB(), animating: false });
  const [layerB, setLayerB] = useState({ index: 1 % Math.max(photos.length, 1), kb: randomKB(), animating: false });
  const [isPaused, setIsPaused] = useState(false);
  const [musicOn, setMusicOn] = useState(true);
  const [showControls, setShowControls] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);

  const audioRef = useRef(null);
  const timerRef = useRef(null);
  const controlsTimerRef = useRef(null);

  const photoUrls = useMemo(() =>
    photos.map(p => previewUrl(galleryId, p.subfolder || p._subfolder, p.filename)),
    [photos, galleryId]
  );

  // Preload images
  useEffect(() => {
    photoUrls.forEach(url => { const img = new Image(); img.src = url; });
  }, [photoUrls]);

  // ─── MUSIC PICK → INTRO → PLAYING ───
  const handleMusicPick = useCallback((trackId) => {
    setChosenTrack(trackId);
    setPhase('intro');

    // Start music during intro
    if (trackId) {
      const track = TRACKS.find(t => t.id === trackId);
      if (track) {
        const audio = new Audio(slideshowMusicUrl(track.file));
        audio.loop = true;
        audio.volume = 0;
        audio.play().catch(() => {});
        // Fade in over 3 seconds
        let vol = 0;
        const fadeIn = setInterval(() => {
          vol = Math.min(vol + 0.02, 0.5);
          audio.volume = vol;
          if (vol >= 0.5) clearInterval(fadeIn);
        }, 60);
        audioRef.current = audio;
      }
    }

    // Intro → Playing
    setTimeout(() => {
      setPhase('playing');
      // Kick off Ken Burns on first slide
      setTimeout(() => {
        setLayerA(prev => ({ ...prev, animating: true }));
      }, 100);
    }, INTRO_DURATION_MS);
  }, []);

  // ─── CLEANUP MUSIC ON UNMOUNT ───
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // ─── MUSIC VOLUME CONTROL ───
  useEffect(() => {
    if (!audioRef.current) return;
    const target = (musicOn && !isPaused) ? 0.5 : 0;
    const audio = audioRef.current;
    // Smooth volume transition
    const start = audio.volume;
    const diff = target - start;
    const steps = 15;
    let step = 0;
    const interval = setInterval(() => {
      step++;
      audio.volume = Math.max(0, Math.min(1, start + (diff * step / steps)));
      if (step >= steps) clearInterval(interval);
    }, 30);
  }, [musicOn, isPaused]);

  // ─── CLOSE HANDLER (fade out music) ───
  const handleClose = useCallback(() => {
    if (audioRef.current) {
      const audio = audioRef.current;
      let vol = audio.volume;
      const fadeOut = setInterval(() => {
        vol = Math.max(0, vol - 0.03);
        audio.volume = vol;
        if (vol <= 0) {
          clearInterval(fadeOut);
          audio.pause();
        }
      }, 30);
    }
    setTimeout(() => onClose(), 300);
  }, [onClose]);

  // ─── AUTO-HIDE CONTROLS ───
  const resetControlsTimer = useCallback(() => {
    setShowControls(true);
    if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current);
    controlsTimerRef.current = setTimeout(() => {
      if (!isPaused) setShowControls(false);
    }, 4000);
  }, [isPaused]);

  // ─── ADVANCE SLIDE ───
  const advanceSlide = useCallback(() => {
    if (photos.length <= 1) return;
    const nextIdx = (currentIndex + 1) % photos.length;
    const nextKB = randomKB();

    if (activeLayer === 'A') {
      setLayerB({ index: nextIdx, kb: nextKB, animating: false });
      setTimeout(() => {
        setActiveLayer('B');
        setTimeout(() => setLayerB(prev => ({ ...prev, animating: true })), 100);
      }, 80);
    } else {
      setLayerA({ index: nextIdx, kb: nextKB, animating: false });
      setTimeout(() => {
        setActiveLayer('A');
        setTimeout(() => setLayerA(prev => ({ ...prev, animating: true })), 100);
      }, 80);
    }
    setCurrentIndex(nextIdx);
  }, [currentIndex, photos.length, activeLayer]);

  // ─── AUTO-ADVANCE TIMER ───
  useEffect(() => {
    if (phase !== 'playing' || isPaused || photos.length <= 1) return;
    timerRef.current = setTimeout(advanceSlide, SLIDE_DISPLAY_MS);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [phase, isPaused, currentIndex, advanceSlide, photos.length]);

  // ─── KEYBOARD ───
  useEffect(() => {
    const handler = (e) => {
      if (phase === 'picking') {
        if (e.key === 'Escape') onClose();
        return;
      }
      if (e.key === 'Escape') handleClose();
      if (e.key === ' ') { e.preventDefault(); setIsPaused(p => !p); }
      if (e.key === 'm' || e.key === 'M') setMusicOn(m => !m);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [phase, onClose, handleClose]);

  // ─── LAYER STYLE ───
  const buildLayerImageStyle = (layer) => {
    const kb = layer.kb;
    const isAnimating = layer.animating && !isPaused;
    const scale = isAnimating ? kb.toScale : 1.0;
    const tx = isAnimating ? kb.toX : 0;
    const ty = isAnimating ? kb.toY : 0;
    return {
      backgroundImage: `url(${photoUrls[layer.index] || ''})`,
      backgroundSize: 'contain',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      transform: `scale(${scale}) translate(${tx}%, ${ty}%)`,
      transition: isAnimating ? `transform ${KB_DURATION_S}s cubic-bezier(0.25, 0.1, 0.25, 1.0)` : 'transform 0s',
      willChange: 'transform',
    };
  };

  if (photos.length === 0) return null;

  // ─── MUSIC PICKER PHASE ───
  if (phase === 'picking') {
    return <MusicPicker coupleName={coupleName} photoCount={photos.length} onStart={handleMusicPick} onClose={onClose} />;
  }

  const layerAOnTop = activeLayer === 'A';
  const showIntro = phase === 'intro';

  return (
    <div
      className="fixed inset-0 z-[9999] bg-black"
      style={{ cursor: showControls ? 'default' : 'none' }}
      onMouseMove={resetControlsTimer}
      onClick={resetControlsTimer}
      data-testid="slideshow-overlay"
    >
      {/* ─── INTRO ─── */}
      <div
        className="absolute inset-0 z-50 flex items-center justify-center bg-black"
        style={{
          opacity: showIntro ? 1 : 0,
          transition: 'opacity 1.2s ease',
          pointerEvents: showIntro ? 'auto' : 'none',
        }}
      >
        <div className="text-center px-8">
          <div className="flex items-center justify-center gap-4 mb-6">
            <div className="h-px w-16" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
            <span className="text-[#D4AF37] text-lg" style={{ lineHeight: 1 }}>&#10022;</span>
            <div className="h-px w-16" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
          </div>
          <p className="text-white/40 text-xs tracking-[0.35em] uppercase mb-5" style={{ fontFamily: 'Manrope, sans-serif' }}>
            Your Wedding Gallery
          </p>
          <h1 className="text-white text-5xl md:text-7xl font-light" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
            {coupleName}
          </h1>
          <div className="flex items-center justify-center gap-4 mt-6">
            <div className="h-px w-16" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
            <span className="text-[#D4AF37] text-lg" style={{ lineHeight: 1 }}>&#10022;</span>
            <div className="h-px w-16" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
          </div>
          <p className="text-white/30 text-xs tracking-wider mt-8" style={{ fontFamily: 'Manrope, sans-serif' }}>
            {photos.length} moments
          </p>
        </div>
      </div>

      {/* ─── IMAGE LAYERS ─── */}
      {phase === 'playing' && (
        <>
          <div className="absolute inset-0 overflow-hidden"
            style={{ opacity: layerAOnTop ? 1 : 0, transition: `opacity ${CROSSFADE_MS}ms ease-in-out`, zIndex: layerAOnTop ? 2 : 1 }}>
            <div className="absolute inset-0" style={buildLayerImageStyle(layerA)} />
          </div>
          <div className="absolute inset-0 overflow-hidden"
            style={{ opacity: layerAOnTop ? 0 : 1, transition: `opacity ${CROSSFADE_MS}ms ease-in-out`, zIndex: layerAOnTop ? 1 : 2 }}>
            <div className="absolute inset-0" style={buildLayerImageStyle(layerB)} />
          </div>

          {/* Overlays */}
          <div className="absolute inset-x-0 top-0 h-32 z-10 pointer-events-none" style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.3), transparent)' }} />
          <div className="absolute inset-x-0 bottom-0 h-40 z-10 pointer-events-none" style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.4), transparent)' }} />

          {/* Couple Name */}
          <div className="absolute bottom-7 left-1/2 -translate-x-1/2 z-20 text-center pointer-events-none"
            style={{ opacity: showControls ? 0.7 : 0.25, transition: 'opacity 1s ease' }}>
            <p className="text-white/70 text-2xl md:text-3xl font-light italic"
              style={{ fontFamily: 'Cormorant Garamond, serif', textShadow: '0 2px 20px rgba(0,0,0,0.7)' }}>
              {coupleName}
            </p>
          </div>

          {/* Progress */}
          <div className="absolute bottom-[72px] left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 pointer-events-none"
            style={{ opacity: showControls ? 1 : 0, transition: 'opacity 1s ease' }}>
            {photos.length <= 30 ? photos.map((_, i) => (
              <div key={i} className="rounded-full"
                style={{ width: i === currentIndex ? 20 : 5, height: 5,
                  backgroundColor: i === currentIndex ? '#D4AF37' : 'rgba(255,255,255,0.2)',
                  transition: 'all 0.6s ease' }} />
            )) : (
              <p className="text-white/45 text-xs tracking-wide" style={{ fontFamily: 'Manrope, sans-serif' }}>
                {currentIndex + 1} / {photos.length}
              </p>
            )}
          </div>

          {/* Controls */}
          <div className="absolute top-6 right-6 z-30 flex items-center gap-3"
            style={{ opacity: showControls ? 1 : 0, transition: 'opacity 1s ease' }}>
            {chosenTrack && (
              <button data-testid="slideshow-music-toggle"
                onClick={(e) => { e.stopPropagation(); setMusicOn(m => !m); }}
                className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer"
                style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.12)' }}
                title={musicOn ? "Mute (M)" : "Music (M)"}>
                {musicOn ? <Volume2 className="w-4 h-4 text-white/70" /> : <VolumeX className="w-4 h-4 text-white/35" />}
              </button>
            )}
            <button data-testid="slideshow-playpause"
              onClick={(e) => { e.stopPropagation(); setIsPaused(p => !p); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.12)' }}
              title={isPaused ? "Play (Space)" : "Pause (Space)"}>
              {isPaused ? <Play className="w-4 h-4 text-white/70 ml-0.5" /> : <Pause className="w-4 h-4 text-white/70" />}
            </button>
            {shareToken && (
              <button data-testid="slideshow-share"
                onClick={(e) => {
                  e.stopPropagation();
                  const url = `${window.location.origin}/s/${shareToken}/slideshow`;
                  navigator.clipboard.writeText(url).then(() => {
                    setLinkCopied(true);
                    setTimeout(() => setLinkCopied(false), 2500);
                  }).catch(() => {});
                }}
                className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer"
                style={{
                  backgroundColor: linkCopied ? 'rgba(212,175,55,0.25)' : 'rgba(255,255,255,0.1)',
                  border: `1px solid ${linkCopied ? 'rgba(212,175,55,0.5)' : 'rgba(255,255,255,0.12)'}`,
                  transition: 'all 0.3s ease',
                }}
                title="Copy slideshow link">
                <Share2 className="w-4 h-4" style={{ color: linkCopied ? '#D4AF37' : 'rgba(255,255,255,0.7)' }} />
              </button>
            )}
            <button data-testid="slideshow-close"
              onClick={(e) => { e.stopPropagation(); handleClose(); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.12)' }}
              title="Close (Esc)">
              <X className="w-4 h-4 text-white/70" />
            </button>
          </div>

          {/* Link copied toast */}
          {linkCopied && (
            <div className="absolute top-[72px] right-6 z-30 pointer-events-none"
              style={{ animation: 'fadeInOut 2.5s ease forwards' }}>
              <div className="px-4 py-2 rounded-full backdrop-blur-xl"
                style={{ backgroundColor: 'rgba(0,0,0,0.5)', border: '1px solid rgba(212,175,55,0.3)' }}>
                <p className="text-xs tracking-wide" style={{ color: '#D4AF37', fontFamily: 'Manrope, sans-serif' }}>
                  Slideshow link copied
                </p>
              </div>
            </div>
          )}

          {/* Paused */}
          {isPaused && (
            <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
              <div className="px-7 py-3 rounded-full backdrop-blur-xl"
                style={{ backgroundColor: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <p className="text-white/50 text-sm tracking-widest uppercase" style={{ fontFamily: 'Manrope, sans-serif' }}>Paused</p>
              </div>
            </div>
          )}
        </>
      )}

      {/* Branding */}
      <div className="absolute top-6 left-6 z-30 pointer-events-none"
        style={{ opacity: showControls && phase !== 'picking' ? 0.45 : 0, transition: 'opacity 1s ease' }}>
        <p className="text-white/45 text-xs italic" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Weddings By Mark</p>
      </div>

      <style>{`
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(-4px); }
          15% { opacity: 1; transform: translateY(0); }
          75% { opacity: 1; transform: translateY(0); }
          100% { opacity: 0; transform: translateY(-4px); }
        }
      `}</style>
    </div>
  );
}
