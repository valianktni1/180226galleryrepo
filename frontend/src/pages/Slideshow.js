import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { previewUrl } from "@/lib/api";
import { X, Play, Pause, Volume2, VolumeX } from "lucide-react";

// ─── AMBIENT MUSIC ENGINE (Bright Romantic Arpeggios) ───
class AmbientMusicEngine {
  constructor() {
    this.ctx = null;
    this.masterGain = null;
    this.playing = false;
    this.schedulerId = null;
    this.nextNoteTime = 0;
    this.chordIndex = 0;
    this.noteInChord = 0;
    this.progression = [
      [261.63, 329.63, 392.00, 493.88, 523.25, 659.25],
      [220.00, 329.63, 440.00, 493.88, 554.37, 659.25],
      [174.61, 261.63, 349.23, 440.00, 523.25, 698.46],
      [196.00, 293.66, 392.00, 493.88, 587.33, 783.99],
      [164.81, 246.94, 329.63, 415.30, 493.88, 659.25],
      [174.61, 220.00, 261.63, 349.23, 440.00, 523.25],
      [146.83, 220.00, 293.66, 349.23, 440.00, 587.33],
      [196.00, 246.94, 293.66, 392.00, 493.88, 587.33],
    ];
    this.tempo = 130;
  }

  init() {
    if (this.ctx) return;
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 0;

    const delay1 = this.ctx.createDelay(1.0);
    delay1.delayTime.value = 0.25;
    const fb1 = this.ctx.createGain();
    fb1.gain.value = 0.18;
    const delay2 = this.ctx.createDelay(1.0);
    delay2.delayTime.value = 0.4;
    const fb2 = this.ctx.createGain();
    fb2.gain.value = 0.12;
    const reverbMix = this.ctx.createGain();
    reverbMix.gain.value = 0.35;

    this.masterGain.connect(delay1);
    delay1.connect(fb1);
    fb1.connect(delay1);
    delay1.connect(reverbMix);
    this.masterGain.connect(delay2);
    delay2.connect(fb2);
    fb2.connect(delay2);
    delay2.connect(reverbMix);
    reverbMix.connect(this.ctx.destination);
    this.masterGain.connect(this.ctx.destination);
  }

  playNote(freq, startTime, duration, velocity = 0.045) {
    if (!this.ctx || !this.playing) return;
    const osc1 = this.ctx.createOscillator();
    const osc2 = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    const filter = this.ctx.createBiquadFilter();

    osc1.type = 'triangle';
    osc1.frequency.value = freq;
    osc2.type = 'sine';
    osc2.frequency.value = freq * 2;
    osc2.detune.value = 3;

    filter.type = 'lowpass';
    filter.frequency.value = 2500 + Math.random() * 1500;
    filter.Q.value = 0.7;

    const t = startTime;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(velocity, t + 0.015);
    gain.gain.exponentialRampToValueAtTime(velocity * 0.5, t + 0.12);
    gain.gain.setValueAtTime(velocity * 0.5, t + duration * 0.6);
    gain.gain.exponentialRampToValueAtTime(0.001, t + duration);

    const shimmerGain = this.ctx.createGain();
    shimmerGain.gain.value = 0.15;

    osc1.connect(filter);
    osc2.connect(shimmerGain);
    shimmerGain.connect(filter);
    filter.connect(gain);
    gain.connect(this.masterGain);

    osc1.start(t);
    osc1.stop(t + duration + 0.05);
    osc2.start(t);
    osc2.stop(t + duration + 0.05);
  }

  scheduleNotes() {
    if (!this.playing || !this.ctx) return;
    const beatDuration = 60.0 / this.tempo;
    while (this.nextNoteTime < this.ctx.currentTime + 0.2) {
      const chord = this.progression[this.chordIndex % this.progression.length];
      const noteIdx = this.noteInChord % chord.length;
      const freq = chord[noteIdx];
      const vel = noteIdx === 0 ? 0.05 : (noteIdx % 3 === 0 ? 0.04 : 0.032);
      const noteDur = beatDuration * (1.2 + Math.random() * 0.6);
      this.playNote(freq, this.nextNoteTime, noteDur, vel);
      if (Math.random() < 0.15) {
        this.playNote(freq * 2, this.nextNoteTime + beatDuration * 0.25, noteDur * 0.5, 0.015);
      }
      this.noteInChord++;
      if (this.noteInChord >= chord.length) {
        this.noteInChord = 0;
        this.chordIndex++;
      }
      this.nextNoteTime += beatDuration * 0.5;
    }
  }

  start() {
    this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    this.playing = true;
    this.chordIndex = 0;
    this.noteInChord = 0;
    this.nextNoteTime = this.ctx.currentTime + 0.1;
    this.masterGain.gain.setValueAtTime(0, this.ctx.currentTime);
    this.masterGain.gain.linearRampToValueAtTime(0.6, this.ctx.currentTime + 3);
    this.schedulerId = setInterval(() => this.scheduleNotes(), 100);
  }

  stop() {
    this.playing = false;
    if (this.schedulerId) { clearInterval(this.schedulerId); this.schedulerId = null; }
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 1.5);
    }
    setTimeout(() => {
      if (this.ctx) { this.ctx.close().catch(() => {}); this.ctx = null; this.masterGain = null; }
    }, 2000);
  }

  setVolume(vol) {
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.linearRampToValueAtTime(vol, this.ctx.currentTime + 0.3);
    }
  }
}

// ─── KEN BURNS ───
// All start at scale 1.0 (full image visible) and gently drift/zoom in
// The movement is subtle so you appreciate the photo first
const kenBurnsPresets = [
  { toScale: 1.12, toX: -2,  toY: -1.5 },  // gentle zoom toward top-left
  { toScale: 1.10, toX: 2,   toY: -1   },  // drift toward top-right
  { toScale: 1.14, toX: -1,  toY: 1.5  },  // zoom toward bottom-left
  { toScale: 1.11, toX: 1.5, toY: 1    },  // drift toward bottom-right
  { toScale: 1.13, toX: 0,   toY: -2   },  // slow zoom upward
  { toScale: 1.10, toX: 0,   toY: 1.5  },  // slow zoom downward
  { toScale: 1.15, toX: 0,   toY: 0    },  // pure center zoom
  { toScale: 1.08, toX: -2,  toY: 0    },  // gentle pan left
];

function randomKB() {
  return kenBurnsPresets[Math.floor(Math.random() * kenBurnsPresets.length)];
}

// ─── TIMING CONSTANTS ───
const SLIDE_DISPLAY_MS = 6000;    // 6 seconds each photo is displayed
const CROSSFADE_MS = 2000;        // 2 second smooth crossfade between images
const KB_DURATION_S = 9;          // Ken Burns runs over 9 seconds (covers display + crossfade)
const INTRO_DURATION_MS = 4000;   // 4 second intro card

// ─── SLIDESHOW COMPONENT ───
export default function Slideshow({ photos, galleryId, coupleName, onClose }) {
  const [activeLayer, setActiveLayer] = useState('A');
  const [layerA, setLayerA] = useState({ index: 0, kb: randomKB(), animating: false });
  const [layerB, setLayerB] = useState({ index: 1 % Math.max(photos.length, 1), kb: randomKB(), animating: false });
  const [isPaused, setIsPaused] = useState(false);
  const [musicOn, setMusicOn] = useState(true);
  const [showControls, setShowControls] = useState(true);
  const [introVisible, setIntroVisible] = useState(true);
  const [started, setStarted] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  const musicRef = useRef(null);
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

  // Auto-hide controls
  const resetControlsTimer = useCallback(() => {
    setShowControls(true);
    if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current);
    controlsTimerRef.current = setTimeout(() => {
      if (!isPaused) setShowControls(false);
    }, 4000);
  }, [isPaused]);

  // Intro -> Start
  useEffect(() => {
    const t = setTimeout(() => {
      setIntroVisible(false);
      setTimeout(() => {
        setStarted(true);
        // Kick off the Ken Burns on the first slide
        setTimeout(() => {
          setLayerA(prev => ({ ...prev, animating: true }));
        }, 100);
      }, 1000);
    }, INTRO_DURATION_MS);
    return () => clearTimeout(t);
  }, []);

  // Music
  useEffect(() => {
    if (!started) return;
    musicRef.current = new AmbientMusicEngine();
    if (musicOn) musicRef.current.start();
    return () => { if (musicRef.current) musicRef.current.stop(); };
  }, [started]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!musicRef.current) return;
    musicRef.current.setVolume(musicOn && !isPaused ? 0.6 : 0);
  }, [musicOn, isPaused]);

  // Advance slide
  const advanceSlide = useCallback(() => {
    if (photos.length <= 1) return;
    const nextIdx = (currentIndex + 1) % photos.length;
    const nextKB = randomKB();

    if (activeLayer === 'A') {
      // Load next image into Layer B at starting position (no animation yet)
      setLayerB({ index: nextIdx, kb: nextKB, animating: false });
      // Small delay then fade in Layer B and start its Ken Burns
      setTimeout(() => {
        setActiveLayer('B');
        setTimeout(() => {
          setLayerB(prev => ({ ...prev, animating: true }));
        }, 100);
      }, 80);
    } else {
      setLayerA({ index: nextIdx, kb: nextKB, animating: false });
      setTimeout(() => {
        setActiveLayer('A');
        setTimeout(() => {
          setLayerA(prev => ({ ...prev, animating: true }));
        }, 100);
      }, 80);
    }

    setCurrentIndex(nextIdx);
  }, [currentIndex, photos.length, activeLayer]);

  // Auto-advance timer
  useEffect(() => {
    if (!started || isPaused || photos.length <= 1) return;
    timerRef.current = setTimeout(advanceSlide, SLIDE_DISPLAY_MS);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [started, isPaused, currentIndex, advanceSlide, photos.length]);

  // Keyboard
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === ' ') { e.preventDefault(); setIsPaused(p => !p); }
      if (e.key === 'm' || e.key === 'M') setMusicOn(m => !m);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  // Build the style for an image layer
  const buildLayerImageStyle = (layer) => {
    const kb = layer.kb;
    const isAnimating = layer.animating && !isPaused;
    // Start: scale 1.0, centered (full image visible via contain)
    // End: gently zoomed in with subtle drift
    const scale = isAnimating ? kb.toScale : 1.0;
    const tx = isAnimating ? kb.toX : 0;
    const ty = isAnimating ? kb.toY : 0;

    return {
      backgroundImage: `url(${photoUrls[layer.index] || ''})`,
      backgroundSize: 'contain',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      transform: `scale(${scale}) translate(${tx}%, ${ty}%)`,
      transition: isAnimating
        ? `transform ${KB_DURATION_S}s cubic-bezier(0.25, 0.1, 0.25, 1.0)`
        : 'transform 0s',
      willChange: 'transform',
    };
  };

  if (photos.length === 0) return null;

  const layerAOnTop = activeLayer === 'A';

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
          opacity: introVisible ? 1 : 0,
          transition: 'opacity 1.2s ease',
          pointerEvents: introVisible ? 'auto' : 'none',
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
          <h1
            className="text-white text-5xl md:text-7xl font-light"
            style={{ fontFamily: 'Cormorant Garamond, serif' }}
          >
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
      {started && (
        <>
          {/* Layer A */}
          <div
            className="absolute inset-0 overflow-hidden"
            style={{
              opacity: layerAOnTop ? 1 : 0,
              transition: `opacity ${CROSSFADE_MS}ms ease-in-out`,
              zIndex: layerAOnTop ? 2 : 1,
            }}
          >
            <div className="absolute inset-0" style={buildLayerImageStyle(layerA)} />
          </div>

          {/* Layer B */}
          <div
            className="absolute inset-0 overflow-hidden"
            style={{
              opacity: layerAOnTop ? 0 : 1,
              transition: `opacity ${CROSSFADE_MS}ms ease-in-out`,
              zIndex: layerAOnTop ? 1 : 2,
            }}
          >
            <div className="absolute inset-0" style={buildLayerImageStyle(layerB)} />
          </div>

          {/* ─── OVERLAYS ─── */}
          <div className="absolute inset-x-0 top-0 h-32 z-10 pointer-events-none" style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.3), transparent)' }} />
          <div className="absolute inset-x-0 bottom-0 h-40 z-10 pointer-events-none" style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.4), transparent)' }} />

          {/* ─── COUPLE NAME ─── */}
          <div
            className="absolute bottom-7 left-1/2 -translate-x-1/2 z-20 text-center pointer-events-none"
            style={{ opacity: showControls ? 0.7 : 0.25, transition: 'opacity 1s ease' }}
          >
            <p
              className="text-white/70 text-2xl md:text-3xl font-light italic"
              style={{ fontFamily: 'Cormorant Garamond, serif', textShadow: '0 2px 20px rgba(0,0,0,0.7)' }}
            >
              {coupleName}
            </p>
          </div>

          {/* ─── PROGRESS ─── */}
          <div
            className="absolute bottom-[72px] left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 pointer-events-none"
            style={{ opacity: showControls ? 1 : 0, transition: 'opacity 1s ease' }}
          >
            {photos.length <= 30 ? photos.map((_, i) => (
              <div
                key={i}
                className="rounded-full"
                style={{
                  width: i === currentIndex ? 20 : 5,
                  height: 5,
                  backgroundColor: i === currentIndex ? '#D4AF37' : 'rgba(255,255,255,0.2)',
                  transition: 'all 0.6s ease',
                }}
              />
            )) : (
              <p className="text-white/45 text-xs tracking-wide" style={{ fontFamily: 'Manrope, sans-serif' }}>
                {currentIndex + 1} / {photos.length}
              </p>
            )}
          </div>

          {/* ─── CONTROLS ─── */}
          <div
            className="absolute top-6 right-6 z-30 flex items-center gap-3"
            style={{ opacity: showControls ? 1 : 0, transition: 'opacity 1s ease' }}
          >
            <button
              data-testid="slideshow-music-toggle"
              onClick={(e) => { e.stopPropagation(); setMusicOn(m => !m); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.12)' }}
              title={musicOn ? "Mute (M)" : "Music (M)"}
            >
              {musicOn ? <Volume2 className="w-4 h-4 text-white/70" /> : <VolumeX className="w-4 h-4 text-white/35" />}
            </button>
            <button
              data-testid="slideshow-playpause"
              onClick={(e) => { e.stopPropagation(); setIsPaused(p => !p); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.12)' }}
              title={isPaused ? "Play (Space)" : "Pause (Space)"}
            >
              {isPaused ? <Play className="w-4 h-4 text-white/70 ml-0.5" /> : <Pause className="w-4 h-4 text-white/70" />}
            </button>
            <button
              data-testid="slideshow-close"
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md cursor-pointer"
              style={{ backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.12)' }}
              title="Close (Esc)"
            >
              <X className="w-4 h-4 text-white/70" />
            </button>
          </div>

          {/* ─── PAUSED ─── */}
          {isPaused && (
            <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
              <div
                className="px-7 py-3 rounded-full backdrop-blur-xl"
                style={{ backgroundColor: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.08)' }}
              >
                <p className="text-white/50 text-sm tracking-widest uppercase" style={{ fontFamily: 'Manrope, sans-serif' }}>
                  Paused
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {/* ─── BRANDING ─── */}
      <div
        className="absolute top-6 left-6 z-30 pointer-events-none"
        style={{ opacity: showControls ? 0.45 : 0, transition: 'opacity 1s ease' }}
      >
        <p className="text-white/45 text-xs italic" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
          Weddings By Mark
        </p>
      </div>
    </div>
  );
}
