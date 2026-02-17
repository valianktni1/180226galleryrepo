import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Heart, Download, X, ChevronLeft, ChevronRight, Camera, Image as ImageIcon, LogOut, Grid, LayoutGrid
} from "lucide-react";
import { getGalleryPhotos, toggleFavourite, downloadZip, mediaUrl } from "@/lib/api";

export default function ClientGallery() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [photos, setPhotos] = useState([]);
  const [galleryId, setGalleryId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lightboxIndex, setLightboxIndex] = useState(-1);
  const [showFavourites, setShowFavourites] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const loadPhotos = useCallback(async () => {
    try {
      const res = await getGalleryPhotos(slug);
      setPhotos(res.data.photos);
      setGalleryId(res.data.gallery_id);
    } catch {
      localStorage.removeItem("client_token");
      localStorage.removeItem("client_gallery_slug");
      navigate(`/gallery/${slug}`);
    } finally {
      setLoading(false);
    }
  }, [slug, navigate]);

  useEffect(() => {
    const token = localStorage.getItem("client_token");
    if (!token) { navigate(`/gallery/${slug}`); return; }
    loadPhotos();
  }, [slug, navigate, loadPhotos]);

  const handleFavourite = async (photoId) => {
    try {
      const res = await toggleFavourite(slug, photoId);
      setPhotos(prev => prev.map(p =>
        p.id === photoId ? { ...p, is_favourite: res.data.favourited } : p
      ));
    } catch {
      toast.error("Failed to update favourite");
    }
  };

  const handleDownloadAll = async () => {
    setDownloading(true);
    try {
      const ids = showFavourites ? photos.filter(p => p.is_favourite).map(p => p.id) : [];
      const res = await downloadZip(slug, ids);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = showFavourites ? "favourites.zip" : "gallery.zip";
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Download started");
    } catch {
      toast.error("Download failed");
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadSingle = async (photo) => {
    try {
      const token = localStorage.getItem("client_token");
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const res = await fetch(`${BACKEND_URL}/api/galleries/${slug}/download/${photo.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = photo.filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Download failed");
    }
  };

  const exitGallery = () => {
    localStorage.removeItem("client_token");
    localStorage.removeItem("client_gallery_slug");
    navigate(`/gallery/${slug}`);
  };

  const displayPhotos = showFavourites ? photos.filter(p => p.is_favourite) : photos;
  const favCount = photos.filter(p => p.is_favourite).length;

  // Lightbox navigation
  const currentPhoto = lightboxIndex >= 0 ? displayPhotos[lightboxIndex] : null;
  const goNext = () => setLightboxIndex(i => Math.min(i + 1, displayPhotos.length - 1));
  const goPrev = () => setLightboxIndex(i => Math.max(i - 1, 0));

  useEffect(() => {
    const handler = (e) => {
      if (lightboxIndex < 0) return;
      if (e.key === 'Escape') setLightboxIndex(-1);
      if (e.key === 'ArrowRight') goNext();
      if (e.key === 'ArrowLeft') goPrev();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Header */}
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Camera className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
            <span className="text-xs tracking-[0.2em] uppercase font-bold" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>
              Your Gallery
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              data-testid="toggle-favourites"
              variant={showFavourites ? "default" : "ghost"}
              onClick={() => setShowFavourites(f => !f)}
              className={`rounded-sm gap-2 text-xs tracking-wider ${showFavourites ? 'bg-[#1C1917] text-[#FDFCF8]' : 'text-[#57534E]'}`}
            >
              <Heart className="w-3.5 h-3.5" fill={showFavourites ? '#D4AF37' : 'none'} /> Favourites ({favCount})
            </Button>
            <Button
              data-testid="download-all-btn"
              variant="ghost"
              onClick={handleDownloadAll}
              disabled={downloading}
              className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider"
            >
              <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : (showFavourites ? "Download Favourites" : "Download All")}
            </Button>
            <Button
              data-testid="exit-gallery-btn"
              variant="ghost"
              onClick={exitGallery}
              className="text-[#57534E] rounded-sm"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-10">
        {displayPhotos.length === 0 ? (
          <div className="text-center py-24">
            <Heart className="w-12 h-12 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
            <p className="text-2xl mb-2" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>
              {showFavourites ? "No favourites yet" : "No photos in this gallery"}
            </p>
            <p className="text-sm" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
              {showFavourites ? "Heart the photos you love to see them here" : "Photos will appear here once uploaded"}
            </p>
          </div>
        ) : (
          <div className="masonry-grid">
            {displayPhotos.map((photo, i) => (
              <motion.div
                key={photo.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="masonry-item photo-card cursor-pointer"
                onClick={() => setLightboxIndex(i)}
                data-testid={`client-photo-${photo.id}`}
              >
                {photo.file_type === 'photo' && photo.preview_path ? (
                  <img
                    src={mediaUrl(galleryId, photo.preview_path)}
                    alt={photo.filename}
                    className="w-full block"
                    loading="lazy"
                  />
                ) : photo.file_type === 'video' ? (
                  <div className="aspect-video flex items-center justify-center" style={{ backgroundColor: '#F5F2EB' }}>
                    <ImageIcon className="w-8 h-8 text-[#A8A29E]" />
                  </div>
                ) : null}
                <div className="photo-overlay" />
                <div className="photo-actions flex items-center justify-between">
                  <button
                    data-testid={`fav-btn-${photo.id}`}
                    onClick={e => { e.stopPropagation(); handleFavourite(photo.id); }}
                    className="w-8 h-8 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
                  >
                    <Heart
                      className="w-4 h-4"
                      fill={photo.is_favourite ? '#D4AF37' : 'none'}
                      stroke={photo.is_favourite ? '#D4AF37' : '#1C1917'}
                    />
                  </button>
                  <button
                    data-testid={`download-btn-${photo.id}`}
                    onClick={e => { e.stopPropagation(); handleDownloadSingle(photo); }}
                    className="w-8 h-8 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
                  >
                    <Download className="w-4 h-4 text-[#1C1917]" />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </main>

      {/* Lightbox */}
      <AnimatePresence>
        {currentPhoto && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="lightbox-overlay"
            onClick={() => setLightboxIndex(-1)}
            data-testid="lightbox-overlay"
          >
            <button
              className="absolute top-6 right-6 text-white/70 hover:text-white z-10"
              onClick={() => setLightboxIndex(-1)}
              style={{ transition: 'color 0.2s ease' }}
            >
              <X className="w-6 h-6" />
            </button>

            {/* Lightbox actions */}
            <div className="absolute top-6 left-6 flex items-center gap-3 z-10">
              <button
                data-testid="lightbox-fav"
                onClick={e => { e.stopPropagation(); handleFavourite(currentPhoto.id); }}
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}
              >
                <Heart
                  className="w-5 h-5"
                  fill={currentPhoto.is_favourite ? '#D4AF37' : 'none'}
                  stroke={currentPhoto.is_favourite ? '#D4AF37' : 'white'}
                />
              </button>
              <button
                data-testid="lightbox-download"
                onClick={e => { e.stopPropagation(); handleDownloadSingle(currentPhoto); }}
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}
              >
                <Download className="w-5 h-5 text-white" />
              </button>
            </div>

            {/* Counter */}
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/60 text-sm z-10" style={{ fontFamily: 'Manrope, sans-serif' }}>
              {lightboxIndex + 1} / {displayPhotos.length}
            </div>

            {/* Navigation */}
            {lightboxIndex > 0 && (
              <button
                className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center text-white/60 hover:text-white z-10"
                style={{ backgroundColor: 'rgba(0,0,0,0.3)', transition: 'color 0.2s ease' }}
                onClick={e => { e.stopPropagation(); goPrev(); }}
              >
                <ChevronLeft className="w-6 h-6" />
              </button>
            )}
            {lightboxIndex < displayPhotos.length - 1 && (
              <button
                className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center text-white/60 hover:text-white z-10"
                style={{ backgroundColor: 'rgba(0,0,0,0.3)', transition: 'color 0.2s ease' }}
                onClick={e => { e.stopPropagation(); goNext(); }}
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            )}

            {/* Image */}
            <motion.img
              key={currentPhoto.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.3 }}
              src={galleryId ? mediaUrl(galleryId, currentPhoto.preview_path || currentPhoto.original_path) : ''}
              alt={currentPhoto.filename}
              className="max-w-[90vw] max-h-[85vh] object-contain"
              onClick={e => e.stopPropagation()}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
