import { useState, useEffect, useRef } from "react";
import { X, Download, Share2 } from "lucide-react";

export default function InstallBanner({ theme }) {
  const [show, setShow] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const deferredPromptRef = useRef(null);

  useEffect(() => {
    // Don't show if already installed as PWA
    if (window.matchMedia('(display-mode: standalone)').matches) return;
    // Don't show if already dismissed
    if (localStorage.getItem('pwa_banner_dismissed')) return;

    // Detect iOS (no beforeinstallprompt on iOS)
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    setIsIOS(ios);

    if (ios) {
      // Only show on iOS Safari (not in-app browsers)
      const isSafari = /Safari/.test(navigator.userAgent) && !/CriOS|FxiOS|Chrome/.test(navigator.userAgent);
      if (isSafari) {
        setTimeout(() => setShow(true), 3000);
      }
      return;
    }

    // Android / Chrome — listen for the install prompt
    const handler = (e) => {
      e.preventDefault();
      deferredPromptRef.current = e;
      setTimeout(() => setShow(true), 2000);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = async () => {
    if (deferredPromptRef.current) {
      deferredPromptRef.current.prompt();
      const result = await deferredPromptRef.current.userChoice;
      if (result.outcome === 'accepted') {
        setShow(false);
        localStorage.setItem('pwa_banner_dismissed', 'installed');
      }
      deferredPromptRef.current = null;
    }
  };

  const handleDismiss = () => {
    setShow(false);
    localStorage.setItem('pwa_banner_dismissed', 'true');
  };

  if (!show) return null;

  const accent = theme?.accent || '#D4AF37';
  const font = theme?.bodyFont || 'Manrope, sans-serif';

  return (
    <div
      data-testid="pwa-install-banner"
      style={{
        position: 'fixed',
        bottom: '1rem',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9999,
        width: 'calc(100% - 2rem)',
        maxWidth: '420px',
        backgroundColor: 'rgba(28, 25, 23, 0.95)',
        backdropFilter: 'blur(16px)',
        borderRadius: '12px',
        padding: '16px 18px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
        fontFamily: font,
        animation: 'slideUpBanner 0.4s ease-out',
      }}
    >
      <style>{`
        @keyframes slideUpBanner {
          from { opacity: 0; transform: translateX(-50%) translateY(20px); }
          to { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `}</style>

      <button
        onClick={handleDismiss}
        style={{
          position: 'absolute', top: '8px', right: '10px',
          background: 'none', border: 'none', cursor: 'pointer', padding: '4px',
          color: 'rgba(255,255,255,0.4)',
        }}
        data-testid="pwa-dismiss-btn"
      >
        <X size={16} />
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <img
          src="/icon-192x192.png"
          alt="WBM"
          style={{ width: '48px', height: '48px', borderRadius: '10px', flexShrink: 0 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ color: 'white', fontSize: '14px', fontWeight: 600, margin: 0, lineHeight: 1.3 }}>
            Add to Home Screen
          </p>
          <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: '12px', margin: '3px 0 0', lineHeight: 1.4 }}>
            {isIOS
              ? <>Tap <Share2 size={12} style={{ display: 'inline', verticalAlign: '-2px', color: accent }} /> then &ldquo;Add to Home Screen&rdquo;</>
              : 'Access your gallery like an app'
            }
          </p>
        </div>
        {!isIOS && (
          <button
            onClick={handleInstall}
            data-testid="pwa-install-btn"
            style={{
              backgroundColor: accent,
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              padding: '8px 16px',
              fontSize: '12px',
              fontWeight: 700,
              fontFamily: font,
              cursor: 'pointer',
              letterSpacing: '0.5px',
              textTransform: 'uppercase',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            Install
          </button>
        )}
      </div>
    </div>
  );
}
