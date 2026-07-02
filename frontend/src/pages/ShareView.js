import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle
} from "@/components/ui/alert-dialog";
import {
  Heart, Download, X, ChevronLeft, ChevronRight, Camera, FolderOpen, Film,
  ArrowLeft, Upload, Image as ImageIcon, Trash2, Check, CheckCircle, Printer, FileText, Play, PlayCircle, Moon, Sun
} from "lucide-react";
import {
  getShareFiles, toggleShareFavourite, submitFavouritesToAlbum, downloadShareFile, getShareDownloadUrl, getShareFavouritesDownloadUrl, guestUpload, guestDeleteFiles, previewUrl, thumbUrl, trackGalleryView, trackDownload, sendHeartbeat, getErrorMessage, videoStreamUrl, getVideoPlaybackUrl
} from "@/lib/api";
import GuestUploadView from "@/pages/GuestUploadView";
import Slideshow from "@/pages/Slideshow";
import VideoPlayer from "@/components/VideoPlayer";

export default function ShareView() {
  const { token } = useParams();

  // Check if this is Guest Upload Mode
  const isGuestUploadMode = localStorage.getItem(`guest_upload_mode_${token}`) === 'true';
  const storedGalleryName = localStorage.getItem(`gallery_name_${token}`);

  // If Guest Upload Mode, render the simplified view
  if (isGuestUploadMode) {
    return <GuestUploadView galleryName={storedGalleryName} />;
  }

  // Continue with normal ShareView
  return <ShareViewFull />;
}

function ShareViewFull() {
  const { token } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const guestInputRef = useRef(null);

  const [galleryName, setGalleryName] = useState("");
  const [galleryId, setGalleryId] = useState(null);
  const [subfolders, setSubfolders] = useState([]);
  const [covers, setCovers] = useState({});
  const [permissions, setPermissions] = useState({
    allowUploads: false,
    allowDownloads: true,
    allowDelete: false,
    accessLevel: "download"
  });
  const [loading, setLoading] = useState(true);
  const [activeAlbum, setActiveAlbum] = useState(null); // null = landing, string = subfolder name
  const [lightboxIndex, setLightboxIndex] = useState(-1);
  const [showFavourites, setShowFavourites] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [submittingFavourites, setSubmittingFavourites] = useState(false);
  const [showThankYou, setShowThankYou] = useState(false);
  const [submittedCount, setSubmittedCount] = useState(0);
  const [showSlideshow, setShowSlideshow] = useState(false);

  // Dark mode with localStorage persistence
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('gallery_dark_mode') === 'true');
  const toggleDarkMode = () => {
    setDarkMode(prev => {
      localStorage.setItem('gallery_dark_mode', !prev);
      return !prev;
    });
  };
  // Theme colours
  const t = darkMode ? {
    bg: '#1A1A1A', bgAlt: '#252525', bgCard: '#2A2A2A', bgInstructions: '#222222',
    text: '#E8E4DF', textSub: '#A8A29E', textMuted: '#78716C', headingColor: '#F5F2EB',
    border: '#333333', borderGold: '#D4AF37', cardShadow: '0 2px 12px rgba(0,0,0,0.3)',
    emptyBg: '#252525',
  } : {
    bg: '#FDFCF8', bgAlt: '#F5F2EB', bgCard: 'white', bgInstructions: 'white',
    text: '#57534E', textSub: '#A8A29E', textMuted: '#78716C', headingColor: '#1C1917',
    border: '#F5F2EB', borderGold: '#D4AF37', cardShadow: '0 2px 12px rgba(0,0,0,0.06)',
    emptyBg: '#F5F2EB',
  };

  // ─── Live Heartbeat (silent background ping every 30s) ───
  const sessionIdRef = useRef(Math.random().toString(36).slice(2) + Date.now().toString(36));
  const currentActionRef = useRef("browsing");
  const currentDetailRef = useRef(null);

  useEffect(() => {
    if (!token) return;
    const beat = () => {
      sendHeartbeat(token, {
        session_id: sessionIdRef.current,
        action: currentActionRef.current,
        subfolder: activeAlbum || null,
        detail: currentDetailRef.current,
      });
    };
    beat();
    const interval = setInterval(beat, 30000);
    return () => clearInterval(interval);
  }, [token, activeAlbum]);

  const handleSubmitFavourites = async () => {
    if (favCount === 0) return;
    setSubmittingFavourites(true);
    try {
      const res = await submitFavouritesToAlbum(token);
      setSubmittedCount(res.data.copied);
      setShowThankYou(true);
      // Refresh files to show updated Album Favourites
      loadFiles();
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to submit favourites'));
    } finally {
      setSubmittingFavourites(false);
    }
  };

  const loadFiles = useCallback(async () => {
    try {
      const res = await getShareFiles(token);
      setGalleryName(res.data.gallery_name);
      setGalleryId(res.data.gallery_id);
      setSubfolders(res.data.subfolders);
      setCovers(res.data.covers || {});
      setPermissions({
        allowUploads: res.data.allow_uploads,
        allowDownloads: res.data.allow_downloads,
        allowDelete: res.data.allow_delete,
        accessLevel: res.data.access_level || "download",
        allowAllFileTypes: res.data.allow_all_file_types || false
      });
    } catch (err) {
      console.error("Failed to load share files:", err);
      localStorage.removeItem("share_token");
      localStorage.removeItem("share_url_token");
      navigate(`/s/${token}`);
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  useEffect(() => {
    if (!localStorage.getItem("share_token")) { navigate(`/s/${token}`); return; }
    loadFiles();
    // Track gallery view
    trackGalleryView(token);
  }, [token, navigate, loadFiles]);

  const handleFavourite = async (fileId) => {
    try {
      const res = await toggleShareFavourite(token, fileId);
      setSubfolders(prev => prev.map(sf => ({
        ...sf,
        files: sf.files.map(f => f.id === fileId ? { ...f, is_favourite: res.data.favourited } : f)
      })));
    } catch { toast.error("Failed to update favourite"); }
  };

  const [downloadProgress, setDownloadProgress] = useState(null); // {fileId, percent, filename}

  const handleDownloadSingle = async (file) => {
    if (!permissions.allowDownloads) {
      toast.error("Downloads are not allowed on this share");
      return;
    }
    try {
      setDownloadProgress({ fileId: file.id, percent: 0, filename: file.filename });
      const res = await downloadShareFile(token, file.id);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Download failed");
      }
      const contentLength = res.headers.get('content-length');
      const total = contentLength ? parseInt(contentLength, 10) : 0;
      const reader = res.body.getReader();
      const chunks = [];
      let received = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        if (total > 0) {
          setDownloadProgress({ fileId: file.id, percent: Math.round((received / total) * 100), filename: file.filename });
        }
      }
      const blob = new Blob(chunks);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = file.filename; a.click();
      window.URL.revokeObjectURL(url);
      trackDownload(token);
      setDownloadProgress(null);
    } catch (err) { 
      toast.error(err.message || "Download failed"); 
      setDownloadProgress(null);
    }
  };

  const handleDownloadAlbum = () => {
    if (!permissions.allowDownloads) {
      toast.error("Downloads are not allowed on this share");
      return;
    }
    
    // For favourites, use direct URL
    if (showFavourites) {
      if (favCount === 0) {
        toast.error("No favourites selected");
        return;
      }
      const url = getShareFavouritesDownloadUrl(token);
      window.open(url, '_blank');
      toast.success("Download started");
      trackDownload(token);
      return;
    }
    
    // For album download, use direct URL
    if (activeAlbum) {
      const url = getShareDownloadUrl(token, activeAlbum);
      window.open(url, '_blank');
      toast.success("Download started");
      trackDownload(token);
    }
  };

  const toggleSelect = (fileId) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId); else next.add(fileId);
      return next;
    });
  };

  const handleBulkDelete = async () => {
    if (!permissions.allowDelete) {
      toast.error("Deleting is not allowed on this share");
      return;
    }
    try {
      const res = await guestDeleteFiles(token, Array.from(selectedFiles));
      toast.success(`${res.data.deleted} files deleted`);
      setSelectedFiles(new Set());
      setSelectMode(false);
      setShowDeleteDialog(false);
      loadFiles();
    } catch (err) {
      toast.error(getErrorMessage(err, "Delete failed"));
    }
  };

  const handleGuestUpload = async (fileList) => {
    if (!fileList?.length) return;
    setUploading(true);
    setUploadProgress(0);
    try {
      const files = Array.from(fileList);
      if (permissions.allowAllFileTypes) {
        // Photographer mode: upload one at a time
        for (let i = 0; i < files.length; i++) {
          setUploadProgress(Math.round(((i) / files.length) * 100));
          await guestUpload(token, [files[i]], (e) => {
            const fileProgress = Math.round((e.loaded * 100) / e.total);
            setUploadProgress(Math.round(((i + fileProgress / 100) / files.length) * 100));
          });
        }
        setUploadProgress(100);
        toast.success(`${files.length} file(s) uploaded successfully!`);
      } else {
        // Guest mode: upload all at once
        await guestUpload(token, files, (e) => {
          setUploadProgress(Math.round((e.loaded * 100) / e.total));
        });
        toast.success("Photos uploaded! Thank you!");
      }
      loadFiles();
    } catch (err) {
      toast.error(getErrorMessage(err, "Upload failed"));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const allFiles = subfolders.flatMap(sf => sf.files.map(f => ({ ...f, _subfolder: sf.name })));
  const currentAlbumFilesRaw = activeAlbum ? (subfolders.find(sf => sf.name === activeAlbum)?.files || []) : [];
  // Hide "other" file types from regular shares (only show in photographer shares)
  const fileFilter = (f) => permissions.allowAllFileTypes || f.file_type === 'photo' || f.file_type === 'video';
  const currentAlbumFiles = currentAlbumFilesRaw.filter(fileFilter);
  const displayFiles = showFavourites ? allFiles.filter(f => f.is_favourite && fileFilter(f)) : currentAlbumFiles;

  // Track current action for heartbeat (must be after displayFiles is defined)
  useEffect(() => {
    if (lightboxIndex >= 0) {
      const photo = displayFiles[lightboxIndex];
      if (photo?.file_type === 'video') {
        currentActionRef.current = "watching_video";
      } else {
        currentActionRef.current = "viewing_photo";
      }
      currentDetailRef.current = photo?.filename || null;
    } else {
      currentActionRef.current = "browsing";
      currentDetailRef.current = null;
    }
  }, [lightboxIndex, displayFiles]);

  const favCount = allFiles.filter(f => f.is_favourite).length;

  // Show all subfolders from the gallery (not just ones with files)
  const visibleAlbums = subfolders;

  // Lightbox
  const currentPhoto = lightboxIndex >= 0 ? displayFiles[lightboxIndex] : null;
  const goNext = () => setLightboxIndex(i => Math.min(i + 1, displayFiles.length - 1));
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

  // Smart preloading: cache next 3 photos when navigating lightbox
  useEffect(() => {
    if (lightboxIndex < 0) return;
    for (let i = 1; i <= 3; i++) {
      const idx = lightboxIndex + i;
      if (idx < displayFiles.length) {
        const f = displayFiles[idx];
        if (f.file_type === 'photo' && f.has_preview && galleryId) {
          const img = new Image();
          img.src = previewUrl(galleryId, f.subfolder || f._subfolder, f.filename);
        }
      }
    }
  }, [lightboxIndex, displayFiles, galleryId]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: t.bg }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  // If no gallery name, something went wrong - show error
  if (!galleryName) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: t.bg }}>
        <div className="text-center">
          <p className="text-lg mb-4" style={{ color: t.text }}>Unable to load gallery</p>
          <button 
            onClick={() => { 
              localStorage.removeItem("share_token"); 
              localStorage.removeItem("share_url_token"); 
              navigate(`/s/${token}`); 
            }}
            className="text-[#D4AF37] underline"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  // Extract couple name from gallery folder name (e.g. "Gina & Mark 30.11.22" → "Gina & Mark")
  const coupleName = galleryName.replace(/\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$/, '').trim() || galleryName;

  // ─── Compute hero image from Wedding Images cover ───
  const heroImageUrl = (() => {
    const weddingSf = subfolders.find(sf => sf.name.toLowerCase().includes('wedding') && sf.name.toLowerCase().includes('image'));
    if (!weddingSf || weddingSf.files.length === 0) return null;
    const coverId = covers[weddingSf.name];
    const coverFile = coverId ? weddingSf.files.find(f => f.id === coverId) : null;
    const heroFile = coverFile || weddingSf.files[0];
    if (!heroFile || !heroFile.has_preview) return null;
    return previewUrl(galleryId, weddingSf.name, heroFile.filename);
  })();

  // ─── LANDING PAGE (Album cards view) ───
  if (!activeAlbum && !showFavourites) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: t.bg, '--card-empty-bg': t.emptyBg }}>
        {/* Header — floats over hero when hero image exists */}
        <header className={heroImageUrl ? 'absolute top-0 left-0 right-0 z-20' : 'border-b'} style={heroImageUrl ? {} : { borderColor: darkMode ? '#333' : 'rgba(212,175,55,0.15)' }}>
          <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="Weddings By Mark" className="h-8" style={{ filter: (heroImageUrl || darkMode) ? 'brightness(0) invert(1)' : 'invert(1)' }} />
            </div>
            <div className="flex items-center gap-3">
              {/* Dark mode toggle */}
              <button data-testid="dark-mode-toggle" onClick={toggleDarkMode}
                className="w-8 h-8 rounded-full flex items-center justify-center cursor-pointer"
                style={{ backgroundColor: heroImageUrl ? 'rgba(255,255,255,0.15)' : (darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)'), transition: 'background-color 0.3s ease' }}
                title={darkMode ? 'Light mode' : 'Dark mode'}>
                {darkMode ? <Sun className="w-3.5 h-3.5" style={{ color: heroImageUrl ? 'white' : '#D4AF37' }} /> : <Moon className="w-3.5 h-3.5" style={{ color: heroImageUrl ? 'white' : '#78716C' }} />}
              </button>
              <Button data-testid="order-prints-btn" onClick={() => navigate(`/s/${token}/prints`)}
                className={`rounded-sm gap-2 text-xs tracking-wider uppercase font-bold px-4 py-2 shadow-md ${heroImageUrl ? 'bg-white/20 backdrop-blur-md hover:bg-white/30 text-white border border-white/20' : 'bg-[#D4AF37] hover:bg-[#B8962E] text-white'}`}>
                <Printer className="w-4 h-4" /> Order Prints
              </Button>
              {favCount > 0 && (
                <Button data-testid="show-favourites-landing" variant="ghost" onClick={() => setShowFavourites(true)}
                  className={`rounded-sm gap-2 text-xs tracking-wider ${heroImageUrl ? 'text-white/90 hover:text-white' : ''}`}
                  style={heroImageUrl ? {} : { color: t.text }}>
                  <Heart className="w-3.5 h-3.5" fill="#D4AF37" stroke="#D4AF37" /> Favourites ({favCount})
                </Button>
              )}
            </div>
          </div>
        </header>

        {/* Welcome Hero */}
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1 }}
          className="relative text-center overflow-hidden"
          style={heroImageUrl ? { minHeight: '70vh', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' } : { padding: '4rem 1.5rem 4rem', backgroundColor: t.bgAlt }}
        >
          {/* Hero background image */}
          {heroImageUrl && (
            <>
              <div className="absolute inset-0 z-0"
                style={{
                  backgroundImage: `url(${heroImageUrl})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center 25%',
                  filter: 'blur(2px) brightness(0.55)',
                  transform: 'scale(1.05)',
                }} />
              <div className="absolute inset-0 z-[1]" style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.15) 40%, rgba(0,0,0,0.4) 100%)' }} />
            </>
          )}

          <div className={`relative ${heroImageUrl ? 'z-10 px-6 py-20 md:py-28' : ''}`}>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-sm tracking-[0.3em] uppercase mb-2"
              style={{ color: heroImageUrl ? 'rgba(255,255,255,0.7)' : t.textSub, fontFamily: 'Manrope, sans-serif' }}
            >
              Welcome
            </motion.p>
            {heroImageUrl && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
                className="flex items-center justify-center gap-4 mb-4">
                <div className="h-px w-12 md:w-20" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
                <span className="text-[#D4AF37] text-sm" style={{ lineHeight: 1 }}>&#10022;</span>
                <div className="h-px w-12 md:w-20" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
              </motion.div>
            )}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="text-5xl md:text-7xl lg:text-8xl font-light italic mb-3"
              style={{ fontFamily: 'Cormorant Garamond, serif', color: heroImageUrl ? 'white' : t.headingColor, textShadow: heroImageUrl ? '0 2px 30px rgba(0,0,0,0.4)' : 'none' }}
              data-testid="couple-name-heading"
            >
              {coupleName}
            </motion.h1>
            {heroImageUrl && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
                className="flex items-center justify-center gap-4 mb-4">
                <div className="h-px w-12 md:w-20" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
                <span className="text-[#D4AF37] text-sm" style={{ lineHeight: 1 }}>&#10022;</span>
                <div className="h-px w-12 md:w-20" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
              </motion.div>
            )}
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="text-base md:text-lg"
              style={{ color: heroImageUrl ? 'rgba(255,255,255,0.8)' : t.text, fontFamily: 'Manrope, sans-serif' }}
            >
              Your special memories, beautifully captured
            </motion.p>
          </div>
        </motion.section>

        {/* Album Instructions */}
        <section className="max-w-screen-xl mx-auto px-6 pt-10 md:pt-14">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9 }}
            className="mx-auto max-w-3xl text-center px-8 py-10"
          >
            <h3 className="text-2xl font-medium mb-2" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>
              Your Wedding Album
            </h3>
            <p className="text-sm mb-10" style={{ fontFamily: 'Manrope, sans-serif', color: t.textMuted || '#A8A29E' }}>
              If your package includes an album, follow these three simple steps
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-10">
              {[
                { step: "1", icon: <Heart className="w-6 h-6" fill="#D4AF37" stroke="#D4AF37" />, title: "Heart Your Favourites", desc: "Open your Wedding Images folder and tap the heart on your 40 favourite photos" },
                { step: "2", icon: <ImageIcon className="w-6 h-6" style={{ color: '#D4AF37' }} />, title: "Choose Your Cover", desc: "Pick one special image for the front cover of your album" },
                { step: "3", icon: <CheckCircle className="w-6 h-6" style={{ color: '#D4AF37' }} />, title: "Submit Your Album", desc: "Tap the gold heart at the top, then press Submit for Album" },
              ].map(({ step, icon, title, desc }) => (
                <div key={step} className="flex flex-col items-center text-center p-6 rounded-sm border" style={{ borderColor: t.border || 'rgba(212,175,55,0.2)', backgroundColor: t.bgInstructions || 'rgba(212,175,55,0.03)' }}>
                  <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4" style={{ backgroundColor: 'rgba(212,175,55,0.1)' }}>
                    {icon}
                  </div>
                  <h4 className="text-base font-medium mb-2" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>{title}</h4>
                  <p className="text-xs leading-relaxed" style={{ fontFamily: 'Manrope, sans-serif', color: t.text }}>{desc}</p>
                </div>
              ))}
            </div>

            <p className="text-xs" style={{ fontFamily: 'Manrope, sans-serif', color: t.textMuted || '#A8A29E' }}>
              Your selections will appear in your <strong style={{ color: t.headingColor }}>Album Favourites</strong> folder. Please email <a href="mailto:mark@perfectweddingsbymark.uk" className="underline" style={{ color: '#D4AF37' }}>mark@perfectweddingsbymark.uk</a> once submitted, including your chosen cover image number.
            </p>
          </motion.div>
        </section>

        {/* Albums Section */}
        <section className="max-w-screen-xl mx-auto px-6 py-12 md:py-16">
          <div className="flex items-center justify-center gap-4 mb-10">
            <div className="h-px flex-1 max-w-[80px]" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }} />
            <h2 className="text-xl font-light tracking-wide" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>Your Albums</h2>
            <div className="h-px flex-1 max-w-[80px]" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 mb-12">
            {visibleAlbums.map((sf, i) => (
              <motion.button
                key={sf.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.08 }}
                onClick={() => { setActiveAlbum(sf.name); setShowFavourites(false); }}
                className="group text-left rounded-lg overflow-hidden"
                style={{ boxShadow: t.cardShadow, transition: 'box-shadow 0.4s ease, transform 0.4s ease', backgroundColor: t.bgCard }}
                onMouseOver={e => { e.currentTarget.style.boxShadow = darkMode ? '0 8px 30px rgba(0,0,0,0.4)' : '0 8px 30px rgba(0,0,0,0.12)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                onMouseOut={e => { e.currentTarget.style.boxShadow = t.cardShadow; e.currentTarget.style.transform = 'translateY(0)'; }}
                data-testid={`album-card-${sf.name.replace(/\s/g, '-')}`}
              >
                {/* Album cover image */}
                {(() => {
                  const coverId = covers[sf.name];
                  const coverFile = coverId ? sf.files.find(f => f.id === coverId) : null;
                  const displayFile = coverFile || (sf.files.length > 0 ? sf.files[0] : null);
                  
                  if (displayFile && displayFile.has_thumb) {
                    return (
                      <div className="w-full aspect-[4/3] overflow-hidden relative" style={{ backgroundColor: t.emptyBg }}>
                        <img
                          src={thumbUrl(galleryId, sf.name, displayFile.filename)}
                          alt={sf.name}
                          className="w-full h-full object-cover"
                          style={{ objectPosition: 'center 25%', transition: 'transform 0.6s ease' }}
                          onMouseOver={e => e.target.style.transform = 'scale(1.06)'}
                          onMouseOut={e => e.target.style.transform = 'scale(1)'}
                        />
                        <div className="absolute inset-x-0 bottom-0 h-20" style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.5), transparent)' }} />
                        <div className="absolute bottom-3 left-4 right-4">
                          <p className="font-medium text-sm text-white" style={{ fontFamily: 'Manrope, sans-serif', textShadow: '0 1px 4px rgba(0,0,0,0.4)' }}>{sf.name}</p>
                          <p className="text-xs text-white/70" style={{ fontFamily: 'Manrope, sans-serif' }}>{sf.files.length} {sf.files.length === 1 ? 'file' : 'files'}</p>
                        </div>
                      </div>
                    );
                  }
                  return (
                    <div className="w-full aspect-[4/3] flex flex-col items-center justify-center" style={{ backgroundColor: t.emptyBg }}>
                      <FolderOpen className="w-10 h-10 mb-3" strokeWidth={1.5} style={{ color: t.textMuted }} />
                      <p className="font-medium text-sm mb-0.5" style={{ fontFamily: 'Manrope, sans-serif', color: t.headingColor }}>{sf.name}</p>
                      <p className="text-xs" style={{ color: t.textSub, fontFamily: 'Manrope, sans-serif' }}>{sf.files.length} {sf.files.length === 1 ? 'file' : 'files'}</p>
                    </div>
                  );
                })()}
              </motion.button>
            ))}
          </div>

          {/* Guest Upload Section */}
          {permissions.allowUploads && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
            >
              <div className="flex items-center gap-2 mb-4">
                <Upload className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
                <h2 className="text-xl font-semibold" style={{ fontFamily: 'Manrope, sans-serif', color: t.headingColor }}>
                  {permissions.allowAllFileTypes ? "Upload Files" : "Upload Photos & Videos"}
                </h2>
              </div>
              <p className="text-sm mb-4" style={{ color: t.text, fontFamily: 'Manrope, sans-serif' }}>
                {permissions.allowAllFileTypes 
                  ? "Upload RAW files, photos, videos and any other files"
                  : "Share your photos and videos from the event"
                }
              </p>
              <div
                className="upload-zone p-8 flex flex-col items-center justify-center text-center cursor-pointer"
                style={{ minHeight: '140px', backgroundColor: 'rgba(212,175,55,0.04)' }}
                onClick={() => guestInputRef.current?.click()}
                data-testid="guest-upload-zone"
              >
                <input ref={guestInputRef} type="file" multiple accept={permissions.allowAllFileTypes ? undefined : "image/*,video/*"} className="hidden"
                  onChange={e => handleGuestUpload(e.target.files)} data-testid="guest-file-input" />
                {uploading ? (
                  <div className="w-full max-w-xs">
                    <p className="text-sm mb-2" style={{ color: t.text, fontFamily: 'Manrope, sans-serif' }}>Uploading... {uploadProgress}%</p>
                    <Progress value={uploadProgress} className="h-1.5" />
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 mb-3 text-[#D4AF37]" strokeWidth={1.5} />
                    <p className="text-sm font-medium mb-1" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      Click to choose files or drag & drop
                    </p>
                    <p className="text-xs" style={{ color: t.textSub, fontFamily: 'Manrope, sans-serif' }}>
                    </p>
                  </>
                )}
              </div>
            </motion.div>
          )}
        </section>

        {/* Elegant Footer */}
        <footer className="mt-16 mb-8">
          <div className="max-w-screen-xl mx-auto px-6">
            <div className="border-t pt-8 text-center" style={{ borderColor: 'rgba(212,175,55,0.3)' }}>
              <div className="flex items-center justify-center gap-3 mb-3">
                <div className="h-px w-12" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }}></div>
                <span className="text-[#D4AF37] text-lg">✦</span>
                <div className="h-px w-12" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }}></div>
              </div>
              <p className="text-sm tracking-wide" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.text }}>
                Site Designed & Maintained by
              </p>
              <p className="text-xl font-medium italic mt-1" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>
                Weddings By Mark
              </p>
            </div>
          </div>
        </footer>
      </div>
    );
  }

  // ─── FAVOURITES VIEW ───
  if (showFavourites) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: t.bg, '--card-empty-bg': t.emptyBg }}>
        <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: darkMode ? 'rgba(26,26,26,0.85)' : 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: darkMode ? '#333' : 'rgba(212,175,55,0.15)' }}>
          <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button data-testid="back-from-favourites" onClick={() => setShowFavourites(false)}
                style={{ color: t.text, transition: 'color 0.2s ease' }}>
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>Your Favourites</h1>
              <span className="text-xs" style={{ color: t.textSub }}>({favCount})</span>
            </div>
            <div className="flex items-center gap-2">
              {favCount > 0 && (
                <Button data-testid="submit-favourites-btn" variant="default" onClick={handleSubmitFavourites} disabled={submittingFavourites}
                  className="rounded-sm gap-2 text-xs tracking-wider" style={{ backgroundColor: '#D4AF37', color: 'white' }}>
                  <Heart className="w-3.5 h-3.5" /> {submittingFavourites ? "Submitting..." : "Submit for Album"}
                </Button>
              )}
              {permissions.allowDownloads && (
                <Button data-testid="download-favourites-btn" variant="ghost" onClick={handleDownloadAlbum} disabled={downloading}
                  className="rounded-sm gap-2 text-xs tracking-wider" style={{ color: t.text }}>
                  <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : "Download All"}
                </Button>
              )}
            </div>
          </div>
        </header>
        <main className="max-w-screen-xl mx-auto px-6 py-8">
          <div className="mb-6 p-4 rounded-lg" style={{ backgroundColor: t.bgAlt }}>
            <p className="text-sm" style={{ color: t.text, fontFamily: 'Manrope, sans-serif' }}>
              <Heart className="w-4 h-4 inline mr-2" fill="#D4AF37" stroke="#D4AF37" />
              Heart your favourite photos, then click <strong>"Submit for Album"</strong> to send them for your wedding album.
            </p>
          </div>
          {displayFiles.length === 0 ? (
            <div className="text-center py-20">
              <Heart className="w-12 h-12 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
              <p className="text-xl" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.text }}>No favourites yet</p>
              <p className="text-sm mt-2" style={{ color: t.textSub }}>Heart the photos you love to see them here</p>
            </div>
          ) : (
            <div className="masonry-grid">
              {displayFiles.map((file, i) => (
                <FileCard key={file.id} file={file} index={i} galleryId={galleryId}
                  onFav={handleFavourite} onDownload={handleDownloadSingle}
                  onClick={() => setLightboxIndex(i)} permissions={permissions} theme={t}
                  downloadProgress={downloadProgress} />
              ))}
            </div>
          )}
        </main>
        <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
          setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
          galleryId={galleryId} onFav={handleFavourite} onDownload={handleDownloadSingle} permissions={permissions} shareToken={token}
          downloadProgress={downloadProgress} />
        <ThankYouModal show={showThankYou} onClose={() => setShowThankYou(false)} count={submittedCount} galleryName={galleryName} theme={t} />
      </div>
    );
  }

  // ─── ALBUM DETAIL VIEW ───
  return (
    <div className="min-h-screen" style={{ backgroundColor: t.bg, '--card-empty-bg': t.emptyBg }}>
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: darkMode ? 'rgba(26,26,26,0.85)' : 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: darkMode ? '#333' : 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button data-testid="back-to-albums" onClick={() => { setActiveAlbum(null); setLightboxIndex(-1); setSelectMode(false); setSelectedFiles(new Set()); }}
              style={{ color: t.text, transition: 'color 0.2s ease' }}>
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>{activeAlbum}</h1>
              <p className="text-xs" style={{ color: t.textSub, fontFamily: 'Manrope, sans-serif' }}>{coupleName} &middot; {currentAlbumFiles.length} files</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {permissions.allowDelete && (
              <Button data-testid="select-mode-btn" variant={selectMode ? "default" : "ghost"} 
                onClick={() => { setSelectMode(m => !m); setSelectedFiles(new Set()); }}
                className={`rounded-sm text-xs tracking-wider gap-1.5 ${selectMode ? (darkMode ? 'bg-white/10 text-white' : 'bg-[#1C1917] text-[#FDFCF8]') : ''}`}
                style={selectMode ? { fontFamily: 'Manrope, sans-serif' } : { fontFamily: 'Manrope, sans-serif', color: t.text }}>
                <Check className="w-3.5 h-3.5" /> {selectMode ? "Cancel" : "Select"}
              </Button>
            )}
            {selectMode && selectedFiles.size > 0 && (
              <Button data-testid="bulk-delete-btn" onClick={() => setShowDeleteDialog(true)} variant="ghost" className="text-[#9F1239] text-xs gap-1">
                <Trash2 className="w-3.5 h-3.5" /> Delete ({selectedFiles.size})
              </Button>
            )}
            {favCount > 0 && !selectMode && (
              <Button data-testid="show-favourites-album" variant="ghost" onClick={() => setShowFavourites(true)}
                className="rounded-sm gap-2 text-xs tracking-wider" style={{ color: t.text }}>
                <Heart className="w-3.5 h-3.5" fill="#D4AF37" stroke="#D4AF37" /> ({favCount})
              </Button>
            )}
            {activeAlbum && activeAlbum.toLowerCase().includes('wedding') && !selectMode && currentAlbumFiles.filter(f => f.file_type === 'photo').length > 0 && (
              <Button data-testid="slideshow-btn" variant="ghost" onClick={() => setShowSlideshow(true)}
                className="rounded-sm gap-2 text-xs tracking-wider"
                style={{ color: '#D4AF37', fontFamily: 'Manrope, sans-serif' }}>
                <PlayCircle className="w-3.5 h-3.5" /> Slideshow
              </Button>
            )}
            {permissions.allowDownloads && !selectMode && (
              <Button data-testid="download-album-btn" variant="ghost" onClick={handleDownloadAlbum} disabled={downloading}
                className="rounded-sm gap-2 text-xs tracking-wider" style={{ color: t.text }}>
                <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : "Download All"}
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-8">
        {activeAlbum && activeAlbum.toLowerCase() === 'video' && (
          <div className="mb-8 p-5 rounded-sm border" style={{ 
            backgroundColor: darkMode ? 'rgba(212,175,55,0.08)' : 'rgba(212,175,55,0.06)', 
            borderColor: 'rgba(212,175,55,0.25)' 
          }}>
            <p className="text-sm leading-relaxed" style={{ fontFamily: 'Manrope, sans-serif', color: t.text }}>
              <Film className="w-4 h-4 inline mr-2 -mt-0.5" style={{ color: '#D4AF37' }} />
              Your videos are ready for online viewing, optimised for smooth streaming on all your devices. 
              You can also download the full high-quality original — perfect for watching on your big screen at home.
            </p>
          </div>
        )}
        {activeAlbum && activeAlbum.toLowerCase() !== 'video' && (
          <div className="mb-8 p-5 rounded-sm border" style={{ 
            backgroundColor: darkMode ? 'rgba(212,175,55,0.08)' : 'rgba(212,175,55,0.06)', 
            borderColor: 'rgba(212,175,55,0.25)' 
          }}>
            <p className="text-sm leading-relaxed" style={{ fontFamily: 'Manrope, sans-serif', color: t.text }}>
              <ImageIcon className="w-4 h-4 inline mr-2 -mt-0.5" style={{ color: '#D4AF37' }} />
              The small logo you see on your images is only visible here in your online gallery. 
              When you download your photos, they are completely watermark-free and in full quality.
            </p>
            {permissions.allowDownloads && currentAlbumFiles.filter(f => f.file_type === 'photo').length > 0 && (
              <button
                data-testid="download-all-images-btn"
                onClick={handleDownloadAlbum}
                disabled={downloading}
                className="mt-4 w-full flex items-center justify-center gap-3 py-3.5 rounded-sm text-sm font-bold tracking-[0.15em] uppercase transition-all duration-200"
                style={{
                  backgroundColor: '#D4AF37',
                  color: '#1C1917',
                  fontFamily: 'Manrope, sans-serif',
                  opacity: downloading ? 0.7 : 1,
                }}
                onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#C4A030'; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#D4AF37'; }}
              >
                <Download className="w-5 h-5" />
                {downloading ? "Preparing Download..." : "Download All Images"}
              </button>
            )}
          </div>
        )}
        {currentAlbumFiles.length === 0 ? (
          <div className="text-center py-20">
            <FolderOpen className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" strokeWidth={1} />
            <p className="text-xl" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.text }}>No files in {activeAlbum}</p>
          </div>
        ) : (
          <div className="masonry-grid">
            {currentAlbumFiles.map((file, i) => (
              <FileCard key={file.id} file={file} index={i} galleryId={galleryId}
                onFav={handleFavourite} onDownload={handleDownloadSingle}
                onClick={selectMode ? () => toggleSelect(file.id) : () => setLightboxIndex(i)} 
                permissions={permissions}
                selectMode={selectMode}
                isSelected={selectedFiles.has(file.id)} theme={t}
                downloadProgress={downloadProgress} />
            ))}
          </div>
        )}
      </main>

      {/* Elegant Footer */}
      <footer className="mt-16 mb-8">
        <div className="max-w-screen-xl mx-auto px-6">
          <div className="border-t pt-8 text-center" style={{ borderColor: 'rgba(212,175,55,0.3)' }}>
            <div className="flex items-center justify-center gap-3 mb-3">
              <div className="h-px w-12" style={{ background: 'linear-gradient(to right, transparent, #D4AF37)' }}></div>
              <span className="text-[#D4AF37] text-lg">✦</span>
              <div className="h-px w-12" style={{ background: 'linear-gradient(to left, transparent, #D4AF37)' }}></div>
            </div>
            <p className="text-sm tracking-wide" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.text }}>
              Site Designed & Maintained by
            </p>
            <p className="text-xl font-medium italic mt-1" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>
              Weddings By Mark
            </p>
          </div>
        </div>
      </footer>

      <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
        setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
        galleryId={galleryId} onFav={handleFavourite} onDownload={handleDownloadSingle} permissions={permissions} shareToken={token}
        downloadProgress={downloadProgress} />
      
      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="border-none shadow-2xl rounded-none" style={{ backgroundColor: t.bgCard, color: t.text }}>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif', color: t.headingColor }}>
              Delete {selectedFiles.size} file(s)?
            </AlertDialogTitle>
            <AlertDialogDescription style={{ color: t.text, fontFamily: 'Manrope, sans-serif' }}>
              This will permanently delete the selected files. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm" style={{ fontFamily: 'Manrope, sans-serif' }}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-files"
              onClick={handleBulkDelete}
              className="bg-[#9F1239] text-white hover:bg-[#9F1239]/90 rounded-sm text-xs tracking-wider uppercase font-bold"
              style={{ fontFamily: 'Manrope, sans-serif' }}
            >
              Delete Files
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Slideshow */}
      {showSlideshow && (
        <Slideshow
          photos={currentAlbumFiles.filter(f => f.file_type === 'photo' && (f.has_preview || f.has_thumb))}
          galleryId={galleryId}
          coupleName={coupleName}
          onClose={() => setShowSlideshow(false)}
          shareToken={token}
        />
      )}
    </div>
  );
}

// ─── Reusable Components ───
function FileCard({ file, index, galleryId, onFav, onDownload, onClick, permissions = {}, selectMode = false, isSelected = false, theme = {}, downloadProgress = null }) {
  const emptyColor = theme.textSub || '#A8A29E';
  const mutedColor = theme.textMuted || '#C4C0B8';
  const isDownloading = downloadProgress && downloadProgress.fileId === file.id;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.02 }}
      className={`masonry-item photo-card cursor-pointer ${isSelected ? 'ring-2 ring-[#D4AF37]' : ''}`}
      onClick={onClick}
      data-testid={`share-file-${file.id}`}
    >
      {file.file_type === 'photo' ? (
        file.has_preview ? (
          <div className="relative">
            <img
              src={previewUrl(galleryId, file.subfolder || file._subfolder, file.filename)}
              alt={file.filename} className="w-full block" loading="lazy" />
            <img src="/watermark-logo.png" alt="" className="absolute pointer-events-none" 
              style={{ bottom: '10px', right: '10px', width: '80px', opacity: 0.72 }} />
          </div>
        ) : (
          <div className="aspect-square flex flex-col items-center justify-center file-card-empty">
            <ImageIcon className="w-8 h-8 mb-1" style={{ color: emptyColor }} />
            <span className="text-xs truncate max-w-[80%]" style={{ color: emptyColor }}>{file.filename}</span>
          </div>
        )
      ) : file.file_type === 'video' ? (
        file.has_thumb ? (
          <div className="relative">
            <img src={thumbUrl(galleryId, file.subfolder || file._subfolder, file.filename)} alt={file.filename} className="w-full block" loading="lazy" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
                <Play className="w-5 h-5 text-white ml-0.5" fill="white" />
              </div>
            </div>
            <span className="absolute bottom-1 left-1 text-[10px] px-1.5 py-0.5 rounded" style={{ backgroundColor: 'rgba(0,0,0,0.6)', color: 'white' }}>{file.filename}</span>
          </div>
        ) : (
          <div className="aspect-video flex flex-col items-center justify-center file-card-empty">
            <Film className="w-8 h-8 mb-1" style={{ color: emptyColor }} />
            <span className="text-xs truncate max-w-[80%]" style={{ color: emptyColor }}>{file.filename}</span>
          </div>
        )
      ) : (
        <div className="aspect-square flex flex-col items-center justify-center file-card-empty">
          <FileText className="w-8 h-8 mb-1" style={{ color: emptyColor }} />
          <span className="text-xs truncate max-w-[80%]" style={{ color: emptyColor }}>{file.filename}</span>
          <span className="text-[10px] mt-0.5" style={{ color: mutedColor }}>{(file.file_size / (1024*1024)).toFixed(1)} MB</span>
        </div>
      )}
      {/* Selection checkbox - visible in select mode */}
      {selectMode && (
        <div className="absolute top-2 left-2 w-6 h-6 rounded-sm border flex items-center justify-center"
          style={{ backgroundColor: isSelected ? '#D4AF37' : 'rgba(255,255,255,0.9)', borderColor: isSelected ? '#D4AF37' : '#D4D4D8' }}>
          {isSelected && <Check className="w-3.5 h-3.5 text-white" />}
        </div>
      )}
      {/* Always visible heart button (bottom-left) - permanent overlay */}
      {!selectMode && (
        <button 
          data-testid={`fav-btn-${file.id}`} 
          onClick={e => { e.stopPropagation(); onFav(file.id); }}
          className="absolute bottom-2 left-2 w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-transform active:scale-95 z-10"
          style={{ backgroundColor: file.is_favourite ? '#D4AF37' : 'rgba(255,255,255,0.95)' }}
        >
          <Heart className="w-5 h-5" fill={file.is_favourite ? 'white' : 'none'} stroke={file.is_favourite ? 'white' : '#1C1917'} />
        </button>
      )}
      {/* Hover overlay for download button */}
      {!selectMode && permissions.allowDownloads && (
        <>
          <div className="photo-overlay" />
          <div className="photo-actions flex items-center justify-end">
            <button data-testid={`download-btn-${file.id}`} onClick={e => { e.stopPropagation(); onDownload(file); }}
              className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}>
              <Download className="w-4 h-4 text-[#1C1917]" />
            </button>
          </div>
        </>
      )}
      {/* Download progress overlay */}
      {isDownloading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-20 rounded-sm"
          style={{ backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(2px)' }}>
          <Download className="w-6 h-6 text-white mb-2 animate-bounce" />
          <div className="w-3/4 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'rgba(255,255,255,0.2)' }}>
            <div className="h-full rounded-full transition-all duration-300" 
              style={{ width: `${downloadProgress.percent}%`, backgroundColor: '#D4AF37' }} />
          </div>
          <span className="text-white text-xs mt-2" style={{ fontFamily: 'Manrope, sans-serif' }}>
            {downloadProgress.percent}%
          </span>
        </div>
      )}
    </motion.div>
  );
}

function Lightbox({ currentPhoto, lightboxIndex, total, setLightboxIndex, goNext, goPrev, galleryId, onFav, onDownload, permissions = {}, shareToken, downloadProgress }) {
  const isVideo = currentPhoto && currentPhoto.file_type === 'video';
  const isDownloading = downloadProgress && currentPhoto && downloadProgress.fileId === currentPhoto.id;
  return (
    <AnimatePresence>
      {currentPhoto && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="lightbox-overlay" onClick={() => setLightboxIndex(-1)} data-testid="lightbox-overlay">
          <button className="absolute top-6 right-6 text-white/70 hover:text-white z-10" onClick={() => setLightboxIndex(-1)}>
            <X className="w-6 h-6" />
          </button>
          <div className="absolute top-6 left-6 flex items-center gap-3 z-10">
            <button data-testid="lightbox-fav" onClick={e => { e.stopPropagation(); onFav(currentPhoto.id); }}
              className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
              <Heart className="w-5 h-5" fill={currentPhoto.is_favourite ? '#D4AF37' : 'none'} stroke={currentPhoto.is_favourite ? '#D4AF37' : 'white'} />
            </button>
            {permissions.allowDownloads && (
              <button data-testid="lightbox-download" onClick={e => { e.stopPropagation(); if (!isDownloading) onDownload(currentPhoto); }}
                className="h-10 rounded-full flex items-center justify-center gap-2 px-3" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)', minWidth: '40px' }}>
                {isDownloading ? (
                  <>
                    <Download className="w-5 h-5 text-white animate-bounce" />
                    <span className="text-white text-xs font-medium" style={{ fontFamily: 'Manrope, sans-serif' }}>{downloadProgress.percent}%</span>
                  </>
                ) : (
                  <Download className="w-5 h-5 text-white" />
                )}
              </button>
            )}
          </div>
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/60 text-sm z-10" style={{ fontFamily: 'Manrope, sans-serif' }}>
            {lightboxIndex + 1} / {total}
          </div>
          {lightboxIndex > 0 && (
            <button className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center text-white/60 hover:text-white z-10"
              style={{ backgroundColor: 'rgba(0,0,0,0.3)' }} onClick={e => { e.stopPropagation(); goPrev(); }}>
              <ChevronLeft className="w-6 h-6" />
            </button>
          )}
          {lightboxIndex < total - 1 && (
            <button className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center text-white/60 hover:text-white z-10"
              style={{ backgroundColor: 'rgba(0,0,0,0.3)' }} onClick={e => { e.stopPropagation(); goNext(); }}>
              <ChevronRight className="w-6 h-6" />
            </button>
          )}
          {isVideo && shareToken ? (
            <motion.div key={currentPhoto.id} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
              onClick={e => e.stopPropagation()}>
              <VideoPlayer
                src={videoStreamUrl(shareToken, currentPhoto.id)}
                resolveUrl={() => getVideoPlaybackUrl(shareToken, currentPhoto.id)}
                filename={currentPhoto.filename}
              />
            </motion.div>
          ) : (
            <div className="relative" onClick={e => e.stopPropagation()}>
              <motion.div key={currentPhoto.id} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}>
                <ProgressiveImage
                  thumbSrc={galleryId ? thumbUrl(galleryId, currentPhoto.subfolder || currentPhoto._subfolder, currentPhoto.filename) : ''}
                  fullSrc={galleryId && currentPhoto.has_preview ? previewUrl(galleryId, currentPhoto.subfolder || currentPhoto._subfolder, currentPhoto.filename) : ''}
                  alt={currentPhoto.filename} className="max-w-[90vw] max-h-[85vh] object-contain" />
              </motion.div>
              {currentPhoto.file_type === 'photo' && (
                <img src="/watermark-logo.png" alt="" className="absolute pointer-events-none"
                  style={{ bottom: '10px', right: '10px', width: '120px', opacity: 0.45 }} />
              )}
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─── Progressive Image: shows thumb instantly (blurred), crossfades to full preview ───
function ProgressiveImage({ thumbSrc, fullSrc, alt, className, style }) {
  const [currentSrc, setCurrentSrc] = useState(thumbSrc);
  const [isFullLoaded, setIsFullLoaded] = useState(false);
  const prevFullSrc = useRef(fullSrc);

  useEffect(() => {
    if (fullSrc === prevFullSrc.current && isFullLoaded) return;
    prevFullSrc.current = fullSrc;
    setCurrentSrc(thumbSrc);
    setIsFullLoaded(false);
    const img = new Image();
    img.onload = () => { setCurrentSrc(fullSrc); setIsFullLoaded(true); };
    img.src = fullSrc;
    return () => { img.onload = null; };
  }, [fullSrc, thumbSrc]);

  return (
    <img src={currentSrc} alt={alt} className={className}
      style={{ ...style, filter: isFullLoaded ? 'none' : 'blur(10px)', transition: 'filter 0.4s ease-out' }} />
  );
}

function ThankYouModal({ show, onClose, count, galleryName, theme = {} }) {
  if (!show) return null;
  const bg = theme.bgCard || 'white';
  const heading = theme.headingColor || '#1C1917';
  const text = theme.text || '#57534E';
  
  return (
    <AnimatePresence>
      <motion.div 
        initial={{ opacity: 0 }} 
        animate={{ opacity: 1 }} 
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          transition={{ type: 'spring', duration: 0.5 }}
          className="rounded-lg p-8 max-w-md w-full text-center shadow-2xl"
          style={{ backgroundColor: bg }}
          onClick={e => e.stopPropagation()}
        >
          <div className="w-16 h-16 mx-auto mb-6 rounded-full flex items-center justify-center" style={{ backgroundColor: '#D4AF37' }}>
            <Heart className="w-8 h-8 text-white" fill="white" />
          </div>
          <h2 className="text-2xl font-semibold mb-3" style={{ fontFamily: 'Cormorant Garamond, serif', color: heading }}>
            Thank You!
          </h2>
          <p className="text-base mb-4" style={{ fontFamily: 'Manrope, sans-serif', color: text }}>
            Your {count} favourite {count === 1 ? 'photo has' : 'photos have'} been submitted for your wedding album.
          </p>
          <p className="text-sm mb-6 p-3 rounded-lg" style={{ fontFamily: 'Manrope, sans-serif', color: text, backgroundColor: theme.bgAlt || '#FEF9E7' }}>
            <strong>Guys... please don't forget!</strong><br />
            Email Mark your chosen image for your front cover at{' '}
            <a href="mailto:mark@perfectweddingsbymark.uk" className="underline font-medium" style={{ color: '#D4AF37' }}>mark@perfectweddingsbymark.uk</a>
          </p>
          <button
            onClick={onClose}
            className="px-8 py-3 rounded-sm text-sm font-medium tracking-wider transition-colors"
            style={{ backgroundColor: '#D4AF37', color: 'white', fontFamily: 'Manrope, sans-serif' }}
          >
            Close
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
