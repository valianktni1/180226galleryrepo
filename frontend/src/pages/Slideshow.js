import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { previewUrl } from "@/lib/api";
import { X, Play, Pause, Volume2, VolumeX } from "lucide-react";

// ─── AMBIENT MUSIC ENGINE ───
class AmbientMusicEngine {
  constructor() {
    this.ctx = null;
    this.masterGain = null;
    this.reverbGain = null;
    this.playing = false;
    this.intervalId = null;
    this.chordIndex = 0;
    // Romantic piano chord progression (frequencies in Hz)
    // Cmaj7 → Am7 → Fmaj7 → Gsus4 → Em7 → Am → Dm7 → G7
    this.progression = [
      [130.81, 164.81, 196.00, 246.94, 329.63],  // Cmaj7
      [110.00, 164.81, 196.00, 261.63, 329.63],  // Am7
      [130.81, 174.61, 220.00, 261.63, 349.23],  // Fmaj7
      [98.00, 146.83, 196.00, 261.63, 392.00],   // Gsus4
      [123.47, 164.81, 196.00, 246.94, 329.63],  // Em7
      [110.00, 130.81, 164.81, 220.00, 329.63],  // Am
      [116.54, 146.83, 174.61, 261.63, 349.23],  // Dm7
      [98.00, 123.47, 146.83, 196.00, 293.66],   // G7
    ];
  }

  init() {
    if (this.ctx) return;
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();

    // Master volume
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 0;

    // Simple delay-based reverb
    const delay1 = this.ctx.createDelay(1.0);
    delay1.delayTime.value = 0.3;
    const delay2 = this.ctx.createDelay(1.0);
    delay2.delayTime.value = 0.5;
    const feedback1 = this.ctx.createGain();
    feedback1.gain.value = 0.2;
    const feedback2 = this.ctx.createGain();
    feedback2.gain.value = 0.15;
    this.reverbGain = this.ctx.createGain();
    this.reverbGain.gain.value = 0.4;

    // Reverb chain
    this.masterGain.connect(delay1);
    delay1.connect(feedback1);
    feedback1.connect(delay1);
    delay1.connect(this.reverbGain);

    this.masterGain.connect(delay2);
    delay2.connect(feedback2);
    feedback2.connect(delay2);
    delay2.connect(this.reverbGain);

    this.reverbGain.connect(this.ctx.destination);
    this.masterGain.connect(this.ctx.destination);
  }

  playNote(freq, startTime, duration, velocity = 0.06) {
    if (!this.ctx) return;
    // Two slightly detuned oscillators for richness
    [0, 1.5].forEach(detune => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const filter = this.ctx.createBiquadFilter();

      osc.type = 'sine';
      osc.frequency.value = freq;
      osc.detune.value = detune;

      filter.type = 'lowpass';
      filter.frequency.value = 800 + Math.random() * 400;
      filter.Q.value = 0.5;

      // ADSR envelope - soft piano-like
      gain.gain.setValueAtTime(0, startTime);
      gain.gain.linearRampToValueAtTime(velocity, startTime + 0.08);
      gain.gain.exponentialRampToValueAtTime(velocity * 0.6, startTime + 0.4);
      gain.gain.setValueAtTime(velocity * 0.6, startTime + duration - 1.2);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

      osc.connect(filter);
      filter.connect(gain);
      gain.connect(this.masterGain);

      osc.start(startTime);
      osc.stop(startTime + duration + 0.1);
    });
  }

  playChord(chord, startTime, duration) {
    // Arpeggiate slightly for natural feel
    chord.forEach((freq, i) => {
      const noteDelay = i * (0.06 + Math.random() * 0.08);
      const vel = i < 2 ? 0.04 : 0.055; // bass notes quieter
      this.playNote(freq, startTime + noteDelay, duration - noteDelay, vel);
    });
  }

  scheduleChords() {
    if (!this.playing || !this.ctx) return;
    const now = this.ctx.currentTime;
    // Schedule next 2 chords ahead
    for (let i = 0; i < 2; i++) {
      const chord = this.progression[this.chordIndex % this.progression.length];
      const chordDuration = 4.5 + Math.random() * 1.5; // 4.5-6s per chord
      this.playChord(chord, now + i * chordDuration, chordDuration);
      this.chordIndex++;
    }
  }

  start() {
    this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    this.playing = true;
    this.chordIndex = 0;
    // Fade in
    this.masterGain.gain.setValueAtTime(0, this.ctx.currentTime);
    this.masterGain.gain.linearRampToValueAtTime(0.7, this.ctx.currentTime + 3);
    this.scheduleChords();
    this.intervalId = setInterval(() => this.scheduleChords(), 8000);
  }

  stop() {
    this.playing = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 1.5);
    }
    setTimeout(() => {
      if (this.ctx) {
        this.ctx.close();
        this.ctx = null;
        this.masterGain = null;
        this.reverbGain = null;
      }
    }, 2000);
  }

  setVolume(vol) {
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.linearRampToValueAtTime(vol, this.ctx.currentTime + 0.3);
    }
  }
}

// ─── KEN BURNS PRESETS ───
const kenBurnsVariants = [
  { from: { scale: 1.0, x: 0, y: 0 },    to: { scale: 1.25, x: -3, y: -2 } },
  { from: { scale: 1.2, x: -3, y: -2 },   to: { scale: 1.0, x: 0, y: 0 } },
  { from: { scale: 1.0, x: 0, y: 0 },    to: { scale: 1.2, x: 3, y: -2 } },
  { from: { scale: 1.15, x: 2, y: 2 },    to: { scale: 1.0, x: -1, y: 0 } },
  { from: { scale: 1.0, x: -2, y: 1 },    to: { scale: 1.3, x: 2, y: -1 } },
  { from: { scale: 1.25, x: 0, y: -3 },   to: { scale: 1.05, x: 0, y: 1 } },
  { from: { scale: 1.0, x: 3, y: 0 },    to: { scale: 1.2, x: -2, y: -2 } },
  { from: { scale: 1.1, x: -1, y: -1 },   to: { scale: 1.0, x: 2, y: 2 } },
];

// ─── TRANSITION TYPES ───
const TRANSITIONS = ['crossfade', 'softSlide'];

function getRandomDuration() {
  return 2000 + Math.random() * 2000; // 2-4 seconds
}

function getRandomKenBurns() {
  return kenBurnsVariants[Math.floor(Math.random() * kenBurnsVariants.length)];
}

function getRandomTransition() {
  return TRANSITIONS[Math.floor(Math.random() * TRANSITIONS.length)];
}

// ─── SLIDESHOW COMPONENT ───
export default function Slideshow({ photos, galleryId, coupleName, onClose }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [nextIndex, setNextIndex] = useState(1);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [musicOn, setMusicOn] = useState(true);
  const [showControls, setShowControls] = useState(true);
  const [currentKB, setCurrentKB] = useState(getRandomKenBurns);
  const [nextKB, setNextKB] = useState(getRandomKenBurns);
  const [transition, setTransition] = useState(getRandomTransition);
  const [introVisible, setIntroVisible] = useState(true);
  const [started, setStarted] = useState(false);

  const musicRef = useRef(null);
  const timerRef = useRef(null);
  const controlsTimerRef = useRef(null);
  const containerRef = useRef(null);

  const photoUrls = useMemo(() =>
    photos.map(p => previewUrl(galleryId, p.subfolder || p._subfolder, p.filename)),
    [photos, galleryId]
  );

  // Preload images
  useEffect(() => {
    photoUrls.forEach(url => {
      const img = new Image();
      img.src = url;
    });
  }, [photoUrls]);

  // Auto-hide controls
  const resetControlsTimer = useCallback(() => {
    setShowControls(true);
    if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current);
    controlsTimerRef.current = setTimeout(() => {
      if (!isPaused) setShowControls(false);
    }, 3000);
  }, [isPaused]);

  // Start the slideshow after intro
  useEffect(() => {
    const introTimer = setTimeout(() => {
      setIntroVisible(false);
      setTimeout(() => setStarted(true), 800);
    }, 3500);
    return () => clearTimeout(introTimer);
  }, []);

  // Music
  useEffect(() => {
    if (!started) return;
    musicRef.current = new AmbientMusicEngine();
    if (musicOn) musicRef.current.start();
    return () => {
      if (musicRef.current) musicRef.current.stop();
    };
  }, [started]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!musicRef.current) return;
    if (musicOn && !isPaused) {
      musicRef.current.setVolume(0.7);
    } else if (!musicOn || isPaused) {
      musicRef.current.setVolume(0);
    }
  }, [musicOn, isPaused]);

  // Advance slides
  const advanceSlide = useCallback(() => {
    if (photos.length <= 1) return;
    const next = (currentIndex + 1) % photos.length;
    setNextIndex(next);
    setNextKB(getRandomKenBurns());
    setTransition(getRandomTransition());
    setIsTransitioning(true);

    setTimeout(() => {
      setCurrentIndex(next);
      setCurrentKB(getRandomKenBurns());
      setIsTransitioning(false);
    }, 700); // 0.7s transition
  }, [currentIndex, photos.length]);

  useEffect(() => {
    if (!started || isPaused || photos.length <= 1) return;
    const duration = getRandomDuration();
    timerRef.current = setTimeout(advanceSlide, duration + 700);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [started, isPaused, currentIndex, advanceSlide, photos.length]);

  // Keyboard controls
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === ' ') { e.preventDefault(); setIsPaused(p => !p); }
      if (e.key === 'm') setMusicOn(m => !m);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const kbStyle = (kb, progress = 1) => ({
    transform: `scale(${kb.from.scale + (kb.to.scale - kb.from.scale) * progress}) translate(${kb.from.x + (kb.to.x - kb.from.x) * progress}%, ${kb.from.y + (kb.to.y - kb.from.y) * progress}%)`,
  });

  if (photos.length === 0) return null;

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-[9999] bg-black cursor-none"
      onMouseMove={resetControlsTimer}
      onClick={resetControlsTimer}
      data-testid="slideshow-overlay"
    >
      {/* ─── INTRO CARD ─── */}
      <div
        className="absolute inset-0 z-50 flex items-center justify-center"
        style={{
          opacity: introVisible ? 1 : 0,
          transition: 'opacity 0.8s ease',
          pointerEvents: introVisible ? 'auto' : 'none',
        }}
      >
        <div className="text-center">
          <div className="flex items-center justify-center gap-4 mb-6">
            <div className="h-px w-16" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
            <span className="text-[#D4AF37] text-lg">&#10022;</span>
            <div className="h-px w-16" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
          </div>
          <p className="text-white/40 text-xs tracking-[0.35em] uppercase mb-4" style={{ fontFamily: 'Manrope, sans-serif' }}>
            Your Wedding Gallery
          </p>
          <h1
            className="text-white text-5xl md:text-7xl font-light mb-4"
            style={{
              fontFamily: 'Cormorant Garamond, serif',
              opacity: introVisible ? 1 : 0,
              transform: introVisible ? 'translateY(0)' : 'translateY(20px)',
              transition: 'all 1.2s ease 0.5s',
            }}
          >
            {coupleName}
          </h1>
          <div className="flex items-center justify-center gap-4 mt-6">
            <div className="h-px w-16" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
            <span className="text-[#D4AF37] text-lg">&#10022;</span>
            <div className="h-px w-16" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
          </div>
          <p className="text-white/30 text-xs tracking-wider mt-8" style={{ fontFamily: 'Manrope, sans-serif' }}>
            {photos.length} moments
          </p>
        </div>
      </div>

      {/* ─── CURRENT SLIDE ─── */}
      {started && (
        <>
          <div
            className="absolute inset-0 overflow-hidden"
            style={{
              opacity: isTransitioning ? (transition === 'crossfade' ? 0 : 1) : 1,
              transform: isTransitioning && transition === 'softSlide' ? 'translateX(-3%)' : 'translateX(0)',
              transition: `opacity 0.7s ease, transform 0.7s ease`,
            }}
          >
            <div
              className="absolute inset-0 bg-center bg-cover"
              style={{
                backgroundImage: `url(${photoUrls[currentIndex]})`,
                animation: isPaused ? 'none' : `kenburns ${4 + Math.random() * 2}s ease-in-out infinite alternate`,
                ...kbStyle(currentKB, 0.5),
                transition: 'transform 4s ease-in-out',
              }}
            />
          </div>

          {/* ─── NEXT SLIDE (visible during transition) ─── */}
          <div
            className="absolute inset-0 overflow-hidden"
            style={{
              opacity: isTransitioning ? 1 : 0,
              transform: isTransitioning
                ? 'translateX(0)'
                : transition === 'softSlide' ? 'translateX(3%)' : 'translateX(0)',
              transition: `opacity 0.7s ease, transform 0.7s ease`,
            }}
          >
            <div
              className="absolute inset-0 bg-center bg-cover"
              style={{
                backgroundImage: `url(${photoUrls[nextIndex]})`,
                ...kbStyle(nextKB, 0),
              }}
            />
          </div>

          {/* ─── CINEMATIC OVERLAYS ─── */}
          {/* Top gradient */}
          <div className="absolute inset-x-0 top-0 h-32 z-10" style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.4), transparent)' }} />
          {/* Bottom gradient */}
          <div className="absolute inset-x-0 bottom-0 h-40 z-10" style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.5), transparent)' }} />
          {/* Subtle vignette */}
          <div className="absolute inset-0 z-10" style={{ boxShadow: 'inset 0 0 200px rgba(0,0,0,0.3)' }} />

          {/* ─── COUPLE NAME WATERMARK ─── */}
          <div
            className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20 text-center"
            style={{
              opacity: showControls ? 1 : 0.4,
              transition: 'opacity 0.5s ease',
            }}
          >
            <p
              className="text-white/70 text-2xl md:text-3xl font-light italic"
              style={{ fontFamily: 'Cormorant Garamond, serif', textShadow: '0 2px 12px rgba(0,0,0,0.5)' }}
            >
              {coupleName}
            </p>
          </div>

          {/* ─── PROGRESS DOTS ─── */}
          <div
            className="absolute bottom-24 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1"
            style={{
              opacity: showControls ? 1 : 0,
              transition: 'opacity 0.5s ease',
            }}
          >
            {photos.length <= 30 && photos.map((_, i) => (
              <div
                key={i}
                className="rounded-full transition-all duration-300"
                style={{
                  width: i === currentIndex ? 16 : 4,
                  height: 4,
                  backgroundColor: i === currentIndex ? '#D4AF37' : 'rgba(255,255,255,0.3)',
                }}
              />
            ))}
            {photos.length > 30 && (
              <p className="text-white/50 text-xs" style={{ fontFamily: 'Manrope, sans-serif' }}>
                {currentIndex + 1} / {photos.length}
              </p>
            )}
          </div>

          {/* ─── CONTROLS ─── */}
          <div
            className="absolute top-6 right-6 z-30 flex items-center gap-3"
            style={{
              opacity: showControls ? 1 : 0,
              transition: 'opacity 0.5s ease',
              cursor: 'default',
            }}
          >
            <button
              data-testid="slideshow-music-toggle"
              onClick={(e) => { e.stopPropagation(); setMusicOn(m => !m); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)', cursor: 'pointer' }}
              title={musicOn ? "Mute music (M)" : "Play music (M)"}
            >
              {musicOn ? <Volume2 className="w-4 h-4 text-white/80" /> : <VolumeX className="w-4 h-4 text-white/40" />}
            </button>
            <button
              data-testid="slideshow-playpause"
              onClick={(e) => { e.stopPropagation(); setIsPaused(p => !p); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)', cursor: 'pointer' }}
              title={isPaused ? "Play (Space)" : "Pause (Space)"}
            >
              {isPaused ? <Play className="w-4 h-4 text-white/80 ml-0.5" /> : <Pause className="w-4 h-4 text-white/80" />}
            </button>
            <button
              data-testid="slideshow-close"
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)', cursor: 'pointer' }}
              title="Close (Esc)"
            >
              <X className="w-4 h-4 text-white/80" />
            </button>
          </div>

          {/* ─── PAUSED INDICATOR ─── */}
          {isPaused && (
            <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
              <div className="px-6 py-3 rounded-full backdrop-blur-xl" style={{ backgroundColor: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)' }}>
                <p className="text-white/60 text-sm tracking-widest uppercase" style={{ fontFamily: 'Manrope, sans-serif' }}>Paused</p>
              </div>
            </div>
          )}
        </>
      )}

      {/* ─── BRANDING ─── */}
      <div
        className="absolute top-6 left-6 z-30"
        style={{
          opacity: showControls ? 0.6 : 0,
          transition: 'opacity 0.5s ease',
        }}
      >
        <p className="text-white/50 text-xs italic" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
          Weddings By Mark
        </p>
      </div>

      {/* Ken Burns CSS animation */}
      <style>{`
        @keyframes kenburns {
          0% { transform: scale(1) translate(0, 0); }
          100% { transform: scale(1.15) translate(-1%, -1%); }
        }
      `}</style>
    </div>
  );
}
