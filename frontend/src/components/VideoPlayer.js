import { useEffect, useRef, useState } from "react";
import videojs from "video.js";
import "video.js/dist/video-js.css";

const EXT_TYPES = {
  ".mp4": "video/mp4",
  ".mov": "video/mp4",
  ".webm": "video/webm",
  ".mkv": "video/x-matroska",
  ".avi": "video/x-msvideo",
  ".mts": "video/mp2t",
};

function getMimeType(filename) {
  if (!filename) return "video/mp4";
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return EXT_TYPES[ext] || "video/mp4";
}

export default function VideoPlayer({ src, resolveUrl, filename }) {
  const containerRef = useRef(null);
  const playerRef = useRef(null);
  const [error, setError] = useState(false);
  const [resolvedSrc, setResolvedSrc] = useState(null);
  const [loading, setLoading] = useState(false);

  // Resolve the playback URL (zero-DB-lookup direct stream)
  useEffect(() => {
    let cancelled = false;
    if (resolveUrl) {
      setLoading(true);
      resolveUrl()
        .then((url) => { if (!cancelled) setResolvedSrc(url); })
        .catch(() => { if (!cancelled) setResolvedSrc(src); }) // fallback to old URL
        .finally(() => { if (!cancelled) setLoading(false); });
    } else {
      setResolvedSrc(src);
    }
    return () => { cancelled = true; };
  }, [src, resolveUrl]);

  // Initialize video.js once we have the URL
  useEffect(() => {
    if (!containerRef.current || !resolvedSrc) return;
    setError(false);

    const videoEl = document.createElement("video-js");
    videoEl.classList.add("vjs-big-play-centered");
    containerRef.current.appendChild(videoEl);

    const mimeType = getMimeType(filename);

    const player = videojs(videoEl, {
      controls: true,
      autoplay: true,
      preload: "auto",
      responsive: true,
      fill: true,
      playbackRates: [0.5, 1, 1.25, 1.5, 2],
      html5: {
        vhs: { overrideNative: false },
        nativeVideoTracks: true,
        nativeAudioTracks: true,
      },
      controlBar: {
        volumePanel: { inline: true },
        pictureInPictureToggle: true,
      },
      sources: [{ src: resolvedSrc, type: mimeType }],
    });

    player.on("error", () => setError(true));
    playerRef.current = player;

    return () => {
      if (playerRef.current && !playerRef.current.isDisposed()) {
        playerRef.current.dispose();
        playerRef.current = null;
      }
    };
  }, [resolvedSrc, filename]);

  if (loading) {
    return (
      <div data-testid="video-player-loading" onClick={(e) => e.stopPropagation()}
        style={{ width: "90vw", maxWidth: "1200px", height: "70vh", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "black", borderRadius: "4px" }}>
        <div style={{ color: "white", fontFamily: "Manrope, sans-serif", fontSize: "14px" }}>Loading video...</div>
      </div>
    );
  }

  // Fallback to native HTML5 video if video.js fails
  if (error && resolvedSrc) {
    return (
      <div data-testid="video-player-fallback" onClick={(e) => e.stopPropagation()}>
        <video
          src={resolvedSrc}
          controls
          autoPlay
          playsInline
          preload="auto"
          style={{ maxWidth: "90vw", maxHeight: "85vh", backgroundColor: "black" }}
        />
      </div>
    );
  }

  return (
    <div
      data-testid="video-player-container"
      ref={containerRef}
      onClick={(e) => e.stopPropagation()}
      style={{ width: "90vw", maxWidth: "1200px", height: "70vh", maxHeight: "85vh" }}
    />
  );
}
