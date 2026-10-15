import { useState, useEffect, useCallback, useRef, lazy, Suspense } from "react";
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
  Heart, Download, X, ChevronLeft, ChevronRight, ChevronUp, Camera, FolderOpen, Film,
  ArrowLeft, Upload, Image as ImageIcon, Trash2, Check, CheckCircle, Printer, FileText, Play, PlayCircle, Moon, Sun, Share2, Star, Clock
} from "lucide-react";
import {
  getShareFiles, toggleShareFavourite, submitFavouritesToAlbum, downloadShareFile, fetchShareAudio, guestUpload, guestDeleteFiles, previewUrl, thumbUrl, trackGalleryView, trackDownload, sendHeartbeat, getErrorMessage, videoStreamUrl, getVideoPlaybackUrl, chooseAlbumCover, getAlbumCoverChoice,
  startShareFolderDownload, startShareFavouritesDownload, getShareFolderDownloadStatus, getDownloadJobFileUrl
} from "@/lib/api";
import { getTheme } from "@/lib/themes";
import InstallBanner from "@/components/InstallBanner";
import DownloadJobProgress from "@/components/DownloadJobProgress";
import SecureAudioPlayer from "@/components/SecureAudioPlayer";

// Code-split heavy components — only loaded when actually needed
const GuestUploadView = lazy(() => import("@/pages/GuestUploadView"));
const Slideshow = lazy(() => import("@/pages/Slideshow"));
const VideoPlayer = lazy(() => import("@/components/VideoPlayer"));

export default function ShareView() {
  const { token } = useParams();

  // Check if this is Guest Upload Mode
  const isGuestUploadMode = localStorage.getItem(`guest_upload_mode_${token}`) === 'true';
  const storedGalleryName = localStorage.getItem(`gallery_name_${token}`);

  // If Guest Upload Mode, render the simplified view
  if (isGuestUploadMode) {
    return (
      <Suspense fallback={<div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}><div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" /></div>}>
        <GuestUploadView galleryName={storedGalleryName} />
      </Suspense>
    );
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
  const [galleryThemeId, setGalleryThemeId] = useState("classic_gold");
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
  const [downloadJob, setDownloadJob] = useState(null);
  const downloadPollRef = useRef(null);
  const downloadStartedRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showAlbumSubmitDialog, setShowAlbumSubmitDialog] = useState(false);
  const [submittingFavourites, setSubmittingFavourites] = useState(false);
  const [showThankYou, setShowThankYou] = useState(false);
  const [submittedCount, setSubmittedCount] = useState(0);
  const [showSlideshow, setShowSlideshow] = useState(false);
  const [albumCoverChoice, setAlbumCoverChoice] = useState(null);
  const [choosingCover, setChoosingCover] = useState(false);
  const [albumSelection, setAlbumSelection] = useState({ enabled: false });

  // Back to top button — show when scrolled past 600px
  const [showBackToTop, setShowBackToTop] = useState(false);
  useEffect(() => {
    const onScroll = () => setShowBackToTop(window.scrollY > 600);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => () => {
    if (downloadPollRef.current) clearTimeout(downloadPollRef.current);
  }, []);
  const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  // Dark mode with localStorage persistence
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('gallery_dark_mode') === 'true');
  const toggleDarkMode = () => {
    setDarkMode(prev => {
      localStorage.setItem('gallery_dark_mode', !prev);
      return !prev;
    });
  };
  // Theme colours — driven by gallery theme preset + dark mode
  const t = getTheme(galleryThemeId, darkMode);
  // Dark Elegance forces dark mode — override toggle
  const effectiveDarkMode = t.forceDarkMode ? true : darkMode;

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
      if (res.data.album_selection) setAlbumSelection(res.data.album_selection);
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
      setGalleryThemeId(res.data.theme || "classic_gold");
      setSubfolders(res.data.subfolders);
      setCovers(res.data.covers || {});
      setAlbumSelection(res.data.album_selection || { enabled: false });
      if (res.data.album_selection?.cover_file_id) {
        setAlbumCoverChoice({
          file_id: res.data.album_selection.cover_file_id,
          filename: res.data.album_selection.cover_filename,
        });
      } else {
        setAlbumCoverChoice(null);
      }
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

  // Always reveal the folder heading and bulk-download controls when a folder
  // is opened. The second reset runs after React has painted the new view and
  // avoids browsers restoring the previous long-gallery scroll position.
  useEffect(() => {
    window.scrollTo(0, 0);
    const frame = window.requestAnimationFrame(() => window.scrollTo(0, 0));
    return () => window.cancelAnimationFrame(frame);
  }, [activeAlbum, showFavourites]);


  // Fetch album cover choice
  useEffect(() => {
    if (token) {
      getAlbumCoverChoice(token).then(res => {
        setAlbumCoverChoice(res.data.choice);
        if (res.data.album_selection) setAlbumSelection(res.data.album_selection);
      }).catch(() => {});
    }
  }, [token]);

  const handleChooseCover = async (fileId) => {
    setChoosingCover(true);
    try {
      const res = await chooseAlbumCover(token, fileId);
      setAlbumCoverChoice({ file_id: fileId, filename: res.data.filename, chosen_at: new Date().toISOString() });
      if (res.data.album_selection) setAlbumSelection(res.data.album_selection);
      toast.success(`"${res.data.filename}" chosen as your album cover!`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to save cover choice"));
    } finally { setChoosingCover(false); }
  };

  const handleFavourite = async (fileId) => {
    try {
      const res = await toggleShareFavourite(token, fileId);
      if (res.data.album_selection) setAlbumSelection(res.data.album_selection);
      setSubfolders(prev => prev.map(sf => ({
        ...sf,
        files: sf.files.map(f => f.id === fileId ? { ...f, is_favourite: res.data.favourited } : f)
      })));
    } catch (err) { toast.error(getErrorMessage(err, "Failed to update album choice")); }
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

  const pollShareDownload = (jobId, ticket) => {
    const check = async () => {
      try {
        const response = await getShareFolderDownloadStatus(token, jobId);
        const nextJob = { ...response.data, ticket };
        setDownloadJob(nextJob);

        if (nextJob.status === "ready" && downloadStartedRef.current !== jobId) {
          downloadStartedRef.current = jobId;
          const link = document.createElement("a");
          link.href = getDownloadJobFileUrl(jobId, ticket);
          link.style.display = "none";
          document.body.appendChild(link);
          link.click();
          link.remove();
          trackDownload(token);
        }
        if (nextJob.status === "complete") {
          setDownloading(false);
          toast.success("Folder download complete");
          return;
        }
        if (nextJob.status === "failed") {
          setDownloading(false);
          toast.error(nextJob.message || "Download failed");
          return;
        }
        downloadPollRef.current = setTimeout(check, 750);
      } catch (err) {
        setDownloading(false);
        toast.error(getErrorMessage(err, "Could not check download progress"));
      }
    };
    check();
  };

  const handleDownloadAlbum = async () => {
    if (!permissions.allowDownloads) {
      toast.error("Downloads are not allowed on this share");
      return;
    }
    
    // Favourites use the same bounded, disk-backed worker as every folder.
    if (showFavourites) {
      if (favCount === 0) {
        toast.error("No favourites selected");
        return;
      }
      if (downloading) return;
      if (downloadPollRef.current) clearTimeout(downloadPollRef.current);
      setDownloading(true);
      setDownloadJob({ status: "queued", files_done: 0, files_total: favCount, percent: 0, label: "Favourites" });
      downloadStartedRef.current = null;
      try {
        const response = await startShareFavouritesDownload(token);
        setDownloadJob(response.data);
        pollShareDownload(response.data.id, response.data.ticket);
      } catch (err) {
        setDownloading(false);
        setDownloadJob(null);
        toast.error(getErrorMessage(err, "Download failed"));
      }
      return;
    }
    
    // Folder downloads are prepared on disk and report genuine progress.
    if (activeAlbum) {
      if (downloading) return;
      if (downloadPollRef.current) clearTimeout(downloadPollRef.current);
      setDownloading(true);
      setDownloadJob({ status: "queued", files_done: 0, files_total: currentAlbumFiles.length, percent: 0, label: activeAlbum });
      downloadStartedRef.current = null;
      try {
        const response = await startShareFolderDownload(token, activeAlbum);
        setDownloadJob(response.data);
        pollShareDownload(response.data.id, response.data.ticket);
      } catch (err) {
        setDownloading(false);
        setDownloadJob(null);
        toast.error(getErrorMessage(err, "Download failed"));
      }
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
  const fileFilter = (f) => permissions.allowAllFileTypes || ['photo', 'video', 'audio'].includes(f.file_type);
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
  const albumEnabled = albumSelection.enabled === true;
  const albumLocked = albumEnabled && albumSelection.locked === true;
  const albumLimit = albumSelection.limit || 40;
  const albumReady = albumEnabled && albumSelection.ready_to_submit === true;
  const isAlbumChoiceFile = (file) => file?.file_type === 'photo' &&
    !['album favourites', 'guest uploads'].includes((file.subfolder || file._subfolder || '').toLowerCase());

  // Clear, folder-specific wording for the prominent bulk-download button.
  // This changes presentation only; every button still uses the existing,
  // proven handleDownloadAlbum download path.
  const folderDownloadItemLabel = (() => {
    const count = currentAlbumFiles.length;
    if (activeAlbum?.toLowerCase() === 'guest uploads') {
      return count === 1 ? 'Guest Upload' : 'Guest Uploads';
    }
    if (count > 0 && currentAlbumFiles.every(file => file.file_type === 'audio')) {
      return count === 1 ? 'Personal Voice Message' : 'Personal Voice Messages';
    }
    if (count > 0 && currentAlbumFiles.every(file => file.file_type === 'video')) {
      return count === 1 ? 'Video' : 'Videos';
    }
    if (count > 0 && currentAlbumFiles.every(file => file.file_type === 'photo')) {
      return count === 1 ? 'Image' : 'Images';
    }
    return count === 1 ? 'File' : 'Files';
  })();
  const folderDownloadLabel = `Download All ${currentAlbumFiles.length} ${folderDownloadItemLabel}`;

  // No-album couples see no album wording or empty Album Favourites folder.
  // Once a configured album is submitted the completed folder becomes visible.
  const visibleAlbums = subfolders.filter(sf =>
    sf.name.toLowerCase() !== 'album favourites' ||
    (albumEnabled && (albumLocked || sf.files.length > 0))
  );

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
      <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: t.accent, borderTopColor: 'transparent' }} />
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
            className="underline"
            style={{ color: t.accent }}
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
                {darkMode ? <Sun className="w-3.5 h-3.5" style={{ color: heroImageUrl ? 'white' : t.accent }} /> : <Moon className="w-3.5 h-3.5" style={{ color: heroImageUrl ? 'white' : '#78716C' }} />}
              </button>
              <Button data-testid="order-prints-btn" onClick={() => navigate(`/s/${token}/prints`)}
                className={`rounded-sm gap-2 text-xs tracking-wider uppercase font-bold px-4 py-2 shadow-md ${heroImageUrl ? 'bg-white/20 backdrop-blur-md hover:bg-white/30 text-white border border-white/20' : 'text-white'}`}
                style={heroImageUrl ? {} : { backgroundColor: t.accent }}>
                <Printer className="w-4 h-4" /> Order Prints
              </Button>
              <Button data-testid="share-whatsapp-btn"
                onClick={() => {
                  const pw = localStorage.getItem(`share_pw_${token}`);
                  const url = pw
                    ? `${window.location.origin}/s/${token}?p=${encodeURIComponent(pw)}`
                    : `${window.location.origin}/s/${token}`;
                  const text = encodeURIComponent(`Have a look at our wedding photos! 💒\n${url}`);
                  window.open(`https://wa.me/?text=${text}`, '_blank');
                }}
                className={`rounded-sm gap-2 text-xs tracking-wider uppercase font-bold px-4 py-2 shadow-md ${heroImageUrl ? 'bg-white/20 backdrop-blur-md hover:bg-white/30 text-white border border-white/20' : 'text-white'}`}
                style={heroImageUrl ? {} : { backgroundColor: '#25D366' }}>
                <Share2 className="w-4 h-4" /> Share
              </Button>
              {albumEnabled && (
                <Button data-testid="show-favourites-landing" variant="ghost" onClick={() => setShowFavourites(true)}
                  className={`rounded-sm gap-2 text-xs tracking-wider ${heroImageUrl ? 'text-white/90 hover:text-white' : ''}`}
                  style={heroImageUrl ? {} : { color: t.text }}>
                  <Heart className="w-3.5 h-3.5" fill={t.accent} stroke={t.accent} />
                  <span className="min-w-[2.5rem] h-5 px-1.5 flex items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: albumLocked ? '#16A34A' : t.accent }}>
                    {albumLocked ? 'Done' : `${favCount}/${albumLimit}`}
                  </span>
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
              <div className="absolute inset-0 z-0 hero-bg-image"
                style={{
                  backgroundImage: `url(${heroImageUrl})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center 30%',
                  filter: 'blur(2px) brightness(0.55)',
                  transform: 'scale(1.05)',
                }} />
              <div className="absolute inset-0 z-[1]" style={{ background: `linear-gradient(to bottom, ${t.heroGradientTop} 0%, transparent 40%, ${t.heroGradientBottom} 100%)` }} />
            </>
          )}

          <div className={`relative ${heroImageUrl ? 'z-10 px-6 py-20 md:py-28' : ''}`}>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-sm tracking-[0.3em] uppercase mb-2"
              style={{ color: heroImageUrl ? 'rgba(255,255,255,0.7)' : t.textSub, fontFamily: t.bodyFont }}
            >
              Welcome
            </motion.p>
            {heroImageUrl && t.showGradientLines && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
                className="flex items-center justify-center gap-4 mb-4">
                <div className="h-px w-12 md:w-20" style={{ background: `linear-gradient(to right, transparent, ${t.accent})` }} />
                {t.showDiamondDividers && <span className="text-sm" style={{ color: t.accent, lineHeight: 1 }}>&#10022;</span>}
                <div className="h-px w-12 md:w-20" style={{ background: `linear-gradient(to left, transparent, ${t.accent})` }} />
              </motion.div>
            )}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="text-5xl md:text-7xl lg:text-8xl mb-3"
              style={{ fontFamily: t.headingFont, fontStyle: t.headingStyle, fontWeight: t.headingWeight, color: heroImageUrl ? 'white' : t.headingColor, textShadow: heroImageUrl ? '0 2px 30px rgba(0,0,0,0.4)' : 'none' }}
              data-testid="couple-name-heading"
            >
              {coupleName}
            </motion.h1>
            {heroImageUrl && t.showGradientLines && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
                className="flex items-center justify-center gap-4 mb-4">
                <div className="h-px w-12 md:w-20" style={{ background: `linear-gradient(to right, transparent, ${t.accent})` }} />
                {t.showDiamondDividers && <span className="text-sm" style={{ color: t.accent, lineHeight: 1 }}>&#10022;</span>}
                <div className="h-px w-12 md:w-20" style={{ background: `linear-gradient(to left, transparent, ${t.accent})` }} />
              </motion.div>
            )}
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="text-base md:text-lg"
              style={{ color: heroImageUrl ? 'rgba(255,255,255,0.8)' : t.text, fontFamily: t.bodyFont }}
            >
              Your special memories, beautifully captured
            </motion.p>
            <motion.img
              src="/wbm-logo-white.png"
              alt="Weddings By Mark"
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.7 }}
              transition={{ delay: 1.0 }}
              className="mt-6 mx-auto w-48 md:w-56 pointer-events-none select-none"
            />
          </div>
        </motion.section>

        {/* Album Instructions — completely absent when this gallery has no album */}
        {albumEnabled && <section className="max-w-screen-xl mx-auto px-6 pt-10 md:pt-14" data-testid="album-selection-guide">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9 }}
            className="mx-auto max-w-3xl text-center px-8 py-10"
          >
            <h3 className="text-2xl font-medium mb-2" style={{ fontFamily: t.headingFont, color: t.headingColor }}>
              {albumLocked ? 'Your Wedding Album Choices Are Submitted' : 'Choose Your Wedding Album'}
            </h3>
            <p className="text-sm mb-10" style={{ fontFamily: t.bodyFont, color: t.textMuted || '#A8A29E' }}>
              {albumLocked
                ? `${albumLimit} album photographs plus your separate cover are safely locked in.`
                : `Choose exactly ${albumLimit} album photographs plus one separate front cover`}
            </p>

            {!albumLocked && <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-10">
              {[
                { step: "1", icon: <Heart className="w-6 h-6" fill={t.accent} stroke={t.accent} />, title: "Heart Your Album Photos", desc: `Tap the heart on exactly ${albumLimit} photographs for the pages of your album` },
                { step: "2", icon: <Star className="w-6 h-6" style={{ color: t.accent }} />, title: "Choose Your Cover", desc: "Tap Cover on one photograph — this is separate from your album-photo allowance" },
                { step: "3", icon: <CheckCircle className="w-6 h-6" style={{ color: t.accent }} />, title: "Submit Your Album", desc: "Open your choices, check the counter and submit when both steps are complete" },
              ].map(({ step, icon, title, desc }) => (
                <div key={step} className="flex flex-col items-center text-center p-6 border" style={{ borderColor: t.border, backgroundColor: t.bgInstructions, borderRadius: t.cardRadius, borderWidth: t.cardBorderWidth }}>
                  {t.instructionIconBg ? (
                    <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4" style={{ backgroundColor: t.accentLight || `${t.accent}18` }}>
                      {icon}
                    </div>
                  ) : (
                    <div className="mb-4">{icon}</div>
                  )}
                  <h4 className="text-base font-medium mb-2" style={{ fontFamily: t.headingFont, fontStyle: t.headingStyle, color: t.headingColor }}>{title}</h4>
                  <p className="text-xs leading-relaxed" style={{ fontFamily: t.bodyFont, color: t.text }}>{desc}</p>
                </div>
              ))}
            </div>}

            <p className="text-xs" style={{ fontFamily: t.bodyFont, color: t.textMuted || '#A8A29E' }}>
              {albumLocked
                ? 'If you need to make a change, contact Mark and he can reopen your choices without losing them.'
                : <>Nothing is final until you press <strong style={{ color: t.headingColor }}>Submit Your Album</strong>. Mark is notified automatically when you submit.</>}
            </p>
          </motion.div>
        </section>}

        {/* Albums Section */}
        <section className="max-w-screen-xl mx-auto px-6 py-12 md:py-16">
          <div className="flex items-center justify-center gap-4 mb-10">
            {t.showGradientLines && <div className="h-px flex-1 max-w-[80px]" style={{ background: `linear-gradient(to right, transparent, ${t.accent})` }} />}
            <h2 className="text-xl tracking-wide" style={{ fontFamily: t.headingFont, fontWeight: t.headingWeight, fontStyle: t.albumNameStyle, color: t.headingColor }}>Your Albums</h2>
            {t.showGradientLines && <div className="h-px flex-1 max-w-[80px]" style={{ background: `linear-gradient(to left, transparent, ${t.accent})` }} />}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 mb-12">
            {visibleAlbums.map((sf, i) => (
              <motion.button
                key={sf.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.08 }}
                onClick={() => { setActiveAlbum(sf.name); setShowFavourites(false); }}
                className="group text-left overflow-hidden"
                style={{ boxShadow: t.cardShadow, transition: 'box-shadow 0.4s ease, transform 0.4s ease', backgroundColor: t.bgCard, borderRadius: t.cardRadius, border: `${t.cardBorderWidth} solid ${t.border}` }}
                onMouseOver={e => { e.currentTarget.style.boxShadow = effectiveDarkMode ? '0 8px 30px rgba(0,0,0,0.4)' : '0 8px 30px rgba(0,0,0,0.12)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
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
                          onMouseOver={e => e.target.style.transform = `scale(${t.cardHoverScale})`}
                          onMouseOut={e => e.target.style.transform = 'scale(1)'}
                        />
                        <div className="absolute inset-x-0 bottom-0 h-20" style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.5), transparent)' }} />
                        <div className="absolute bottom-3 left-4 right-4">
                          <p className="font-medium text-sm text-white" style={{ fontFamily: t.bodyFont, textShadow: '0 1px 4px rgba(0,0,0,0.4)' }}>{sf.name}</p>
                          <p className="text-xs text-white/70" style={{ fontFamily: t.bodyFont }}>{sf.files.length} {sf.files.length === 1 ? 'file' : 'files'}</p>
                        </div>
                      </div>
                    );
                  }
                  return (
                    <div className="w-full aspect-[4/3] flex flex-col items-center justify-center" style={{ backgroundColor: t.emptyBg }}>
                      <FolderOpen className="w-10 h-10 mb-3" strokeWidth={1.5} style={{ color: t.textMuted }} />
                      <p className="font-medium text-sm mb-0.5" style={{ fontFamily: t.bodyFont, color: t.headingColor }}>{sf.name}</p>
                      <p className="text-xs" style={{ color: t.textSub, fontFamily: t.bodyFont }}>{sf.files.length} {sf.files.length === 1 ? 'file' : 'files'}</p>
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
                <Upload className="w-5 h-5" style={{ color: t.accent }} strokeWidth={1.5} />
                <h2 className="text-xl font-semibold" style={{ fontFamily: t.bodyFont, color: t.headingColor }}>
                  {permissions.allowAllFileTypes ? "Upload Files" : "Upload Photos & Videos"}
                </h2>
              </div>
              <p className="text-sm mb-4" style={{ color: t.text, fontFamily: t.bodyFont }}>
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
                    <p className="text-sm mb-2" style={{ color: t.text, fontFamily: t.bodyFont }}>Uploading... {uploadProgress}%</p>
                    <Progress value={uploadProgress} className="h-1.5" />
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 mb-3" style={{ color: t.accent }} strokeWidth={1.5} />
                    <p className="text-sm font-medium mb-1" style={{ fontFamily: t.bodyFont }}>
                      Click to choose files or drag & drop
                    </p>
                    <p className="text-xs" style={{ color: t.textSub, fontFamily: t.bodyFont }}>
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
            <div className="border-t pt-8 text-center" style={{ borderColor: `${t.accent}40` }}>
              {t.showDiamondDividers ? (
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-12" style={{ background: `linear-gradient(to right, transparent, ${t.accent})` }}></div>
                  <span className="text-lg" style={{ color: t.accent }}>✦</span>
                  <div className="h-px w-12" style={{ background: `linear-gradient(to left, transparent, ${t.accent})` }}></div>
                </div>
              ) : t.showGradientLines ? (
                <div className="flex items-center justify-center mb-3">
                  <div className="h-px w-24" style={{ background: `linear-gradient(to right, transparent, ${t.accent}, transparent)` }}></div>
                </div>
              ) : <div className="mb-3" />}
              <p className="text-sm tracking-wide" style={{ fontFamily: t.headingFont, color: t.text }}>
                Site Designed &amp; Maintained by
              </p>
              <p className="text-xl font-medium italic mt-1" style={{ fontFamily: t.headingFont, color: t.headingColor }}>
                Weddings By Mark
              </p>
            </div>
          </div>
        </footer>
        <InstallBanner theme={t} />
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
              <h1 className="text-lg font-medium" style={{ fontFamily: t.headingFont, color: t.headingColor }}>Your Favourites</h1>
              <span className="text-xs font-semibold" style={{ color: albumLocked ? '#16A34A' : t.accent }}>
                {albumLocked ? 'Submitted' : `${favCount} of ${albumLimit}`}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {!albumLocked && (
                <Button data-testid="submit-favourites-btn" variant="default" onClick={() => setShowAlbumSubmitDialog(true)} disabled={submittingFavourites || !albumReady}
                  className="rounded-sm gap-2 text-xs tracking-wider" style={{ backgroundColor: t.accent, color: 'white' }}>
                  <CheckCircle className="w-3.5 h-3.5" /> {submittingFavourites ? "Submitting..." : "Submit Your Album"}
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
            {albumLocked ? (
              <p className="text-sm" style={{ color: t.text, fontFamily: t.bodyFont }}>
                <CheckCircle className="w-4 h-4 inline mr-2 text-green-600" />
                Your <strong>{albumLimit} album photos</strong> and separate cover <strong>{albumSelection.cover_filename}</strong> were submitted successfully. Contact Mark if you need them reopened.
              </p>
            ) : (
              <div className="space-y-2" style={{ color: t.text, fontFamily: t.bodyFont }}>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span><Heart className="w-4 h-4 inline mr-2" fill={t.accent} stroke={t.accent} />Album photos</span>
                  <strong style={{ color: favCount === albumLimit ? '#16A34A' : t.accent }}>{favCount} of {albumLimit}</strong>
                </div>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span><Star className="w-4 h-4 inline mr-2" style={{ color: t.accent }} />Separate front cover</span>
                  <strong style={{ color: albumSelection.cover_selected ? '#16A34A' : t.textSub }}>{albumSelection.cover_filename || 'Not chosen yet'}</strong>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: t.border }}>
                  <div className="h-full transition-all" style={{ width: `${Math.min(100, (favCount / albumLimit) * 100)}%`, backgroundColor: t.accent }} />
                </div>
                {!albumReady && <p className="text-xs" style={{ color: t.textSub }}>
                  {favCount < albumLimit
                    ? `Choose ${albumLimit - favCount} more album photo${albumLimit - favCount === 1 ? '' : 's'}. You can choose your separate cover from any gallery photo.`
                    : 'Your photo count is complete — choose a separate cover to unlock Submit Your Album.'}
                </p>}
              </div>
            )}
          </div>
          {downloadJob?.label === "Favourites" && (
            <DownloadJobProgress job={downloadJob} accent={t.accent} dark={darkMode} className="mb-6" />
          )}
          {displayFiles.length === 0 ? (
            <div className="text-center py-20">
              <Heart className="w-12 h-12 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
              <p className="text-xl" style={{ fontFamily: t.headingFont, color: t.text }}>No favourites yet</p>
              <p className="text-sm mt-2" style={{ color: t.textSub }}>Heart the photos you love to see them here</p>
            </div>
          ) : (
            <div className="masonry-grid">
              {displayFiles.map((file, i) => (
                <LazyFileCard key={file.id} file={file} index={i} galleryId={galleryId}
                  onFav={!albumLocked ? handleFavourite : null} onDownload={handleDownloadSingle}
                  onClick={file.file_type === 'audio' ? undefined : () => setLightboxIndex(i)} permissions={permissions} theme={t}
                  shareToken={token}
                  downloadProgress={downloadProgress}
                  isAlbumCover={albumCoverChoice?.file_id === file.id}
                  onChooseCover={!albumLocked ? handleChooseCover : null} />
              ))}
            </div>
          )}
        </main>
        {/* Back to Top */}
        <AnimatePresence>
          {showBackToTop && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              onClick={scrollToTop}
              className="fixed bottom-6 right-6 z-30 w-10 h-10 rounded-full flex items-center justify-center shadow-lg"
              style={{ backgroundColor: t.accent, color: 'white' }}
              data-testid="back-to-top-btn-fav"
            >
              <ChevronUp className="w-5 h-5" />
            </motion.button>
          )}
        </AnimatePresence>
        <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
          setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
          galleryId={galleryId} onFav={!albumLocked ? handleFavourite : null} onDownload={handleDownloadSingle} permissions={permissions} shareToken={token}
          downloadProgress={downloadProgress} theme={t} />
        <AlertDialog open={showAlbumSubmitDialog} onOpenChange={setShowAlbumSubmitDialog}>
          <AlertDialogContent className="border-none shadow-2xl rounded-none" style={{ backgroundColor: t.bgCard, color: t.text }}>
            <AlertDialogHeader>
              <AlertDialogTitle className="text-2xl font-medium" style={{ fontFamily: t.headingFont, color: t.headingColor }}>Submit Your Album Choices?</AlertDialogTitle>
              <AlertDialogDescription style={{ color: t.text, fontFamily: t.bodyFont }}>
                You are submitting <strong>{albumLimit} album photographs</strong> plus the separate cover <strong>{albumSelection.cover_filename}</strong>. Your choices will be locked, but Mark can reopen them for you if anything needs changing.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="rounded-sm">Check Again</AlertDialogCancel>
              <AlertDialogAction data-testid="confirm-album-submission" onClick={() => { setShowAlbumSubmitDialog(false); handleSubmitFavourites(); }}
                className="rounded-sm" style={{ backgroundColor: t.accent, color: 'white' }}>
                Yes, Submit My Album
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <ThankYouModal show={showThankYou} onClose={() => setShowThankYou(false)} count={submittedCount} galleryName={galleryName} theme={t} />
      </div>
    );
  }

  // ─── ALBUM DETAIL VIEW ───
  return (
    <div className="min-h-screen" style={{ backgroundColor: t.bg, '--card-empty-bg': t.emptyBg }}>
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: darkMode ? 'rgba(26,26,26,0.85)' : 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: darkMode ? '#333' : 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-3 sm:px-6 py-3 sm:py-4 flex items-center gap-2">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
            <button data-testid="back-to-albums" onClick={() => { setActiveAlbum(null); setLightboxIndex(-1); setSelectMode(false); setSelectedFiles(new Set()); }}
              className="shrink-0"
              style={{ color: t.text, transition: 'color 0.2s ease' }}>
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="min-w-0">
              <h1 className="text-base sm:text-lg font-medium truncate" style={{ fontFamily: t.headingFont, color: t.headingColor }}>{activeAlbum}</h1>
              <p className="text-xs truncate" style={{ color: t.textSub, fontFamily: t.bodyFont }}>{coupleName} &middot; {currentAlbumFiles.length} files</p>
            </div>
          </div>
          <div className="flex items-center gap-1 sm:gap-2 shrink-0">
            {permissions.allowDelete && (
              <Button data-testid="select-mode-btn" variant={selectMode ? "default" : "ghost"} 
                onClick={() => { setSelectMode(m => !m); setSelectedFiles(new Set()); }}
                className={`rounded-sm text-xs tracking-wider gap-1.5 ${selectMode ? (darkMode ? 'bg-white/10 text-white' : 'bg-[#1C1917] text-[#FDFCF8]') : ''}`}
                style={selectMode ? { fontFamily: t.bodyFont } : { fontFamily: t.bodyFont, color: t.text }}>
                <Check className="w-3.5 h-3.5" /> {selectMode ? "Cancel" : "Select"}
              </Button>
            )}
            {selectMode && selectedFiles.size > 0 && (
              <Button data-testid="bulk-delete-btn" onClick={() => setShowDeleteDialog(true)} variant="ghost" className="text-[#9F1239] text-xs gap-1">
                <Trash2 className="w-3.5 h-3.5" /> Delete ({selectedFiles.size})
              </Button>
            )}
            {albumEnabled && !selectMode && (
              <Button data-testid="show-favourites-album" variant="ghost" onClick={() => setShowFavourites(true)}
                className="rounded-sm gap-2 text-xs tracking-wider" style={{ color: t.text }}>
                <Heart className="w-3.5 h-3.5" fill={t.accent} stroke={t.accent} />
                <span className="min-w-[2.5rem] h-5 px-1.5 flex items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: albumLocked ? '#16A34A' : t.accent }}>
                  {albumLocked ? 'Done' : `${favCount}/${albumLimit}`}
                </span>
              </Button>
            )}
            {activeAlbum && activeAlbum.toLowerCase().includes('wedding') && !selectMode && currentAlbumFiles.filter(f => f.file_type === 'photo').length > 0 && (
              <Button data-testid="slideshow-btn" variant="ghost" onClick={() => setShowSlideshow(true)}
                className="rounded-sm gap-1.5 sm:gap-2 text-xs tracking-wider px-2 sm:px-4 h-9"
                aria-label="Start slideshow"
                title="Slideshow"
                style={{ color: t.accent, fontFamily: t.bodyFont }}>
                <PlayCircle className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Slideshow</span>
              </Button>
            )}
            {permissions.allowDownloads && currentAlbumFiles.length > 0 && !selectMode && (
              <Button data-testid="download-album-btn" variant="ghost" onClick={handleDownloadAlbum} disabled={downloading}
                className="rounded-sm gap-1.5 sm:gap-2 text-xs tracking-wide px-2 sm:px-4 h-9"
                aria-label={folderDownloadLabel}
                title={folderDownloadLabel}
                style={{ color: t.text }}>
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{downloading ? "Preparing..." : "Download All"}</span>
                <span className="sm:hidden">{downloading ? "..." : `All (${currentAlbumFiles.length})`}</span>
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-8">
        {activeAlbum && activeAlbum.toLowerCase() === 'guest uploads' && (
          <div className="mb-8 p-5 rounded-sm border" style={{ 
            backgroundColor: darkMode ? 'rgba(212,175,55,0.08)' : 'rgba(212,175,55,0.06)', 
            borderColor: 'rgba(212,175,55,0.25)' 
          }}>
            <p className="text-sm leading-relaxed" style={{ fontFamily: t.bodyFont, color: t.text }}>
              <Clock className="w-4 h-4 inline mr-2 -mt-0.5" style={{ color: t.accent }} />
              Guest uploads are available for 90 days after your wedding date. Please download any files you wish to keep — this folder is cleared automatically after that period.
            </p>
          </div>
        )}
        {activeAlbum && activeAlbum.toLowerCase() === 'video' && (
          <div className="mb-8 p-5 rounded-sm border" style={{ 
            backgroundColor: darkMode ? 'rgba(212,175,55,0.08)' : 'rgba(212,175,55,0.06)', 
            borderColor: 'rgba(212,175,55,0.25)' 
          }}>
            <p className="text-sm leading-relaxed" style={{ fontFamily: t.bodyFont, color: t.text }}>
              <Film className="w-4 h-4 inline mr-2 -mt-0.5" style={{ color: t.accent }} />
              Your videos are ready for online viewing, optimised for smooth streaming on all your devices. 
              You can also download the full high-quality original — perfect for watching on your big screen at home.
            </p>
            <p className="text-sm leading-relaxed mt-3" style={{ fontFamily: t.bodyFont, color: t.text, opacity: 0.85 }}>
              <Download className="w-4 h-4 inline mr-2 -mt-0.5" style={{ color: t.accent }} />
              Use &ldquo;Download All&rdquo; to grab every video in one go. Please allow 30–60 seconds while we prepare your files — the download will start automatically.
            </p>
          </div>
        )}
        {activeAlbum && activeAlbum.toLowerCase() === 'personal voice messages' && (
          <div className="mb-8 p-5 rounded-sm border" style={{
            backgroundColor: darkMode ? 'rgba(212,175,55,0.08)' : 'rgba(212,175,55,0.06)',
            borderColor: 'rgba(212,175,55,0.25)'
          }}>
            <p className="text-sm leading-relaxed" style={{ fontFamily: t.bodyFont, color: t.text }}>
              Personal messages recorded by your wedding guests are kept with your gallery. Listen here, download them individually, or use Download All to save every MP3 together.
            </p>
          </div>
        )}
        {activeAlbum && activeAlbum.toLowerCase() !== 'video' && activeAlbum.toLowerCase() !== 'guest uploads' && activeAlbum.toLowerCase() !== 'selfiebooth' && activeAlbum.toLowerCase() !== 'personal voice messages' && (
          <div className="mb-8 p-5 rounded-sm border" style={{ 
            backgroundColor: darkMode ? 'rgba(212,175,55,0.08)' : 'rgba(212,175,55,0.06)', 
            borderColor: 'rgba(212,175,55,0.25)' 
          }}>
            <p className="text-sm leading-relaxed" style={{ fontFamily: t.bodyFont, color: t.text }}>
              <ImageIcon className="w-4 h-4 inline mr-2 -mt-0.5" style={{ color: t.accent }} />
              The small logo you see on your images is only visible here in your online gallery. 
              When you download your photos, they are completely watermark-free and in full quality.
            </p>
          </div>
        )}
        {permissions.allowDownloads && currentAlbumFiles.length > 0 && (
          <button
            data-testid="download-all-folder-btn"
            onClick={handleDownloadAlbum}
            disabled={downloading}
            className={`${downloadJob?.label === activeAlbum ? "mb-3" : "mb-8"} w-full flex items-center justify-center gap-3 py-3.5 text-sm font-bold tracking-[0.12em] uppercase transition-all duration-200`}
            style={{
              backgroundColor: t.accent,
              color: 'white',
              fontFamily: t.bodyFont,
              opacity: downloading ? 0.7 : 1,
              borderRadius: t.buttonStyle === 'pill' ? '9999px' : t.buttonStyle === 'rounded' ? '8px' : '2px',
            }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = t.accentHover; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = t.accent; }}
          >
            <Download className="w-5 h-5" />
            {downloading ? "Preparing Download..." : folderDownloadLabel}
          </button>
        )}
        {downloadJob?.label === activeAlbum && (
          <DownloadJobProgress job={downloadJob} accent={t.accent} dark={darkMode} className="mb-8" />
        )}
        {currentAlbumFiles.length === 0 ? (
          <div className="text-center py-20">
            <FolderOpen className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" strokeWidth={1} />
            <p className="text-xl" style={{ fontFamily: t.headingFont, color: t.text }}>No files in {activeAlbum}</p>
          </div>
        ) : (
          <div className="masonry-grid">
            {currentAlbumFiles.map((file, i) => (
              <LazyFileCard key={file.id} file={file} index={i} galleryId={galleryId}
                onFav={albumEnabled && !albumLocked && isAlbumChoiceFile(file) ? handleFavourite : null} onDownload={handleDownloadSingle}
                onClick={selectMode ? () => toggleSelect(file.id) : file.file_type === 'audio' ? undefined : () => setLightboxIndex(i)}
                permissions={permissions}
                shareToken={token}
                selectMode={selectMode}
                isSelected={selectedFiles.has(file.id)} theme={t}
                downloadProgress={downloadProgress}
                isAlbumCover={albumCoverChoice?.file_id === file.id || albumSelection.cover_output_file_id === file.id}
                onChooseCover={albumEnabled && !albumLocked && isAlbumChoiceFile(file) ? handleChooseCover : null} />
            ))}
          </div>
        )}
      </main>

      {/* Back to Top */}
      <AnimatePresence>
        {showBackToTop && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            onClick={scrollToTop}
            className="fixed bottom-6 right-6 z-30 w-10 h-10 rounded-full flex items-center justify-center shadow-lg"
            style={{ backgroundColor: t.accent, color: 'white' }}
            data-testid="back-to-top-btn"
          >
            <ChevronUp className="w-5 h-5" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Elegant Footer */}
      <footer className="mt-16 mb-8">
        <div className="max-w-screen-xl mx-auto px-6">
          <div className="border-t pt-8 text-center" style={{ borderColor: `${t.accent}40` }}>
            {t.showDiamondDividers ? (
              <div className="flex items-center justify-center gap-3 mb-3">
                <div className="h-px w-12" style={{ background: `linear-gradient(to right, transparent, ${t.accent})` }}></div>
                <span className="text-lg" style={{ color: t.accent }}>✦</span>
                <div className="h-px w-12" style={{ background: `linear-gradient(to left, transparent, ${t.accent})` }}></div>
              </div>
            ) : t.showGradientLines ? (
              <div className="flex items-center justify-center mb-3">
                <div className="h-px w-24" style={{ background: `linear-gradient(to right, transparent, ${t.accent}, transparent)` }}></div>
              </div>
            ) : <div className="mb-3" />}
            <p className="text-sm tracking-wide" style={{ fontFamily: t.headingFont, color: t.text }}>
              Site Designed &amp; Maintained by
            </p>
            <p className="text-xl font-medium italic mt-1" style={{ fontFamily: t.headingFont, color: t.headingColor }}>
              Weddings By Mark
            </p>
          </div>
        </div>
      </footer>

      <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
        setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
        galleryId={galleryId} onFav={albumEnabled && !albumLocked && isAlbumChoiceFile(currentPhoto) ? handleFavourite : null} onDownload={handleDownloadSingle} permissions={permissions} shareToken={token}
        downloadProgress={downloadProgress} theme={t} />
      
      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="border-none shadow-2xl rounded-none" style={{ backgroundColor: t.bgCard, color: t.text }}>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-medium" style={{ fontFamily: t.headingFont, color: t.headingColor }}>
              Delete {selectedFiles.size} file(s)?
            </AlertDialogTitle>
            <AlertDialogDescription style={{ color: t.text, fontFamily: t.bodyFont }}>
              This will permanently delete the selected files. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm" style={{ fontFamily: t.bodyFont }}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-files"
              onClick={handleBulkDelete}
              className="bg-[#9F1239] text-white hover:bg-[#9F1239]/90 rounded-sm text-xs tracking-wider uppercase font-bold"
              style={{ fontFamily: t.bodyFont }}
            >
              Delete Files
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Slideshow */}
      {showSlideshow && (
        <Suspense fallback={null}>
          <Slideshow
            photos={currentAlbumFiles.filter(f => f.file_type === 'photo' && (f.has_preview || f.has_thumb))}
            galleryId={galleryId}
            coupleName={coupleName}
            onClose={() => setShowSlideshow(false)}
            shareToken={token}
          />
        </Suspense>
      )}
    </div>
  );
}

// ─── Lazy visibility wrapper — only renders full card when near viewport ───
function LazyFileCard(props) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); observer.disconnect(); } },
      { rootMargin: '400px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  if (!visible) {
    const aspect = props.file?.file_type === 'video' ? 'aspect-video' : 'aspect-square';
    return <div ref={ref} className={`masonry-item ${aspect}`} style={{ backgroundColor: props.theme?.emptyBg || '#F5F5F0' }} />;
  }
  return <FileCard {...props} />;
}

// ─── Reusable Components ───
// ─── Blur-up thumbnail — starts blurred, transitions to sharp on load ───
function BlurUpImage({ src, alt, className = '', style = {} }) {
  const [loaded, setLoaded] = useState(false);
  return (
    <img
      src={src}
      alt={alt}
      className={`${className} transition-[filter] duration-500 ease-out`}
      style={{ ...style, filter: loaded ? 'blur(0)' : 'blur(12px)', transform: 'translateZ(0)' }}
      loading="lazy"
      onLoad={() => setLoaded(true)}
    />
  );
}

function FileCard({ file, index, galleryId, shareToken, onFav, onDownload, onClick, permissions = {}, selectMode = false, isSelected = false, theme = {}, downloadProgress = null, isAlbumCover = false, onChooseCover = null }) {
  const emptyColor = theme.textSub || '#A8A29E';
  const mutedColor = theme.textMuted || '#C4C0B8';
  const isDownloading = downloadProgress && downloadProgress.fileId === file.id;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.02, 0.4), duration: 0.3 }}
      className={`masonry-item photo-card cursor-pointer`}
      style={isSelected ? { boxShadow: `0 0 0 2px ${theme.accent}` } : {}}
      onClick={onClick}
      data-testid={`share-file-${file.id}`}
    >
      {file.file_type === 'photo' ? (
        file.has_preview ? (
          <div className="relative overflow-hidden">
            <BlurUpImage
              src={thumbUrl(galleryId, file.subfolder || file._subfolder, file.filename)}
              alt={file.filename} className="w-full block" />
            <img src="/watermark-logo.png" alt="" className="absolute pointer-events-none" 
              style={{ bottom: '10px', right: '10px', width: '80px', opacity: 0.72 }} />
            <span className="photo-filename absolute bottom-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded pointer-events-none"
              style={{ backgroundColor: 'rgba(0,0,0,0.55)', color: 'white', opacity: 0, transition: 'opacity 0.2s ease' }}>
              {file.original_filename || file.filename}
            </span>
          </div>
        ) : (
          <div className="aspect-square flex flex-col items-center justify-center file-card-empty">
            <ImageIcon className="w-8 h-8 mb-1" style={{ color: emptyColor }} />
            <span className="text-xs truncate max-w-[80%]" style={{ color: emptyColor }}>{file.filename}</span>
          </div>
        )
      ) : file.file_type === 'video' ? (
        file.has_thumb ? (
          <div className="relative overflow-hidden">
            <BlurUpImage src={thumbUrl(galleryId, file.subfolder || file._subfolder, file.filename)} alt={file.filename} className="w-full block" />
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
      ) : file.file_type === 'audio' ? (
        <div className="aspect-square">
          <SecureAudioPlayer file={file} fetchAudio={() => fetchShareAudio(shareToken, file.id)}
            onDownload={permissions.allowDownloads ? onDownload : null} theme={theme} />
        </div>
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
          style={{ backgroundColor: isSelected ? theme.accent : 'rgba(255,255,255,0.9)', borderColor: isSelected ? theme.accent : '#D4D4D8' }}>
          {isSelected && <Check className="w-3.5 h-3.5 text-white" />}
        </div>
      )}
      {/* Always visible heart button (bottom-left) - permanent overlay */}
      {!selectMode && onFav && file.file_type === 'photo' && (
        <button 
          data-testid={`fav-btn-${file.id}`} 
          onClick={e => { e.stopPropagation(); onFav(file.id); }}
          className="absolute bottom-2 left-2 w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-transform active:scale-95 z-10"
          style={{ backgroundColor: file.is_favourite ? theme.accent : 'rgba(255,255,255,0.95)' }}
        >
          <Heart className="w-5 h-5" fill={file.is_favourite ? 'white' : 'none'} stroke={file.is_favourite ? 'white' : '#1C1917'} />
        </button>
      )}
      {/* Hover overlay for download button */}
      {!selectMode && permissions.allowDownloads && file.file_type !== 'audio' && (
        <>
          <div className="photo-overlay pointer-events-none" />
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
              style={{ width: `${downloadProgress.percent}%`, backgroundColor: theme.accent }} />
          </div>
          <span className="text-white text-xs mt-2" style={{ fontFamily: theme.bodyFont }}>
            {downloadProgress.percent}%
          </span>
        </div>
      )}
      {/* Album Cover badge */}
      {isAlbumCover && (
        <div className="absolute top-2 right-2 z-10 px-2 py-1 rounded-full flex items-center gap-1 shadow-md"
          style={{ backgroundColor: theme.accent, color: 'white' }}
          data-testid={`cover-badge-${file.id}`}>
          <Star className="w-3 h-3" fill="white" />
          <span className="text-[10px] font-bold uppercase tracking-wider" style={{ fontFamily: theme.bodyFont }}>Your Cover</span>
        </div>
      )}
      {/* Choose as Cover button - only in Album Favourites */}
      {onChooseCover && !isAlbumCover && file.file_type === 'photo' && (
        <button
          data-testid={`choose-cover-${file.id}`}
          onClick={e => { e.stopPropagation(); onChooseCover(file.id); }}
          className="absolute top-2 right-2 z-10 px-2 py-1 rounded-full flex items-center gap-1 shadow-md cover-choose-btn"
          style={{ backgroundColor: 'rgba(255,255,255,0.92)', color: theme.accent, border: `1px solid ${theme.accent}` }}
        >
          <Star className="w-3 h-3" />
          <span className="text-[10px] font-bold uppercase tracking-wider" style={{ fontFamily: theme.bodyFont }}>Cover</span>
        </button>
      )}
    </motion.div>
  );
}

function Lightbox({ currentPhoto, lightboxIndex, total, setLightboxIndex, goNext, goPrev, galleryId, onFav, onDownload, permissions = {}, shareToken, downloadProgress, theme = {} }) {
  const isVideo = currentPhoto && currentPhoto.file_type === 'video';
  const isDownloading = downloadProgress && currentPhoto && downloadProgress.fileId === currentPhoto.id;

  // Swipe gesture support for mobile
  const touchStartX = useRef(null);
  const touchStartY = useRef(null);
  const handleTouchStart = (e) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
  };
  const handleTouchEnd = (e) => {
    if (touchStartX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    const dy = e.changedTouches[0].clientY - touchStartY.current;
    touchStartX.current = null;
    // Only swipe if horizontal movement > 50px and dominates vertical
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      if (dx < 0 && lightboxIndex < total - 1) goNext();
      if (dx > 0 && lightboxIndex > 0) goPrev();
    }
  };

  return (
    <AnimatePresence>
      {currentPhoto && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="lightbox-overlay" onClick={() => setLightboxIndex(-1)} data-testid="lightbox-overlay"
          onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
          <button className="absolute top-6 right-6 text-white/70 hover:text-white z-10" onClick={() => setLightboxIndex(-1)}>
            <X className="w-6 h-6" />
          </button>
          <div className="absolute top-6 left-6 flex items-center gap-3 z-10">
            {onFav && currentPhoto.file_type === 'photo' && <button data-testid="lightbox-fav" onClick={e => { e.stopPropagation(); onFav(currentPhoto.id); }}
              className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
              <Heart className="w-5 h-5" fill={currentPhoto.is_favourite ? theme.accent : 'none'} stroke={currentPhoto.is_favourite ? theme.accent : 'white'} />
            </button>}
            {permissions.allowDownloads && (
              <button data-testid="lightbox-download" onClick={e => { e.stopPropagation(); if (!isDownloading) onDownload(currentPhoto); }}
                className="h-10 rounded-full flex items-center justify-center gap-2 px-3" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)', minWidth: '40px' }}>
                {isDownloading ? (
                  <>
                    <Download className="w-5 h-5 text-white animate-bounce" />
                    <span className="text-white text-xs font-medium" style={{ fontFamily: theme.bodyFont }}>{downloadProgress.percent}%</span>
                  </>
                ) : (
                  <Download className="w-5 h-5 text-white" />
                )}
              </button>
            )}
          </div>
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/60 text-sm z-10" style={{ fontFamily: theme.bodyFont }}>
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
              <Suspense fallback={<div className="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin" />}>
                <VideoPlayer
                  src={videoStreamUrl(shareToken, currentPhoto.id)}
                  resolveUrl={() => getVideoPlaybackUrl(shareToken, currentPhoto.id)}
                  filename={currentPhoto.filename}
                />
              </Suspense>
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
          <div className="w-16 h-16 mx-auto mb-6 rounded-full flex items-center justify-center" style={{ backgroundColor: theme.accent || '#D4AF37' }}>
            <Heart className="w-8 h-8 text-white" fill="white" />
          </div>
          <h2 className="text-2xl font-semibold mb-3" style={{ fontFamily: theme.headingFont || 'Cormorant Garamond, serif', color: heading }}>
            Thank You!
          </h2>
          <p className="text-base mb-4" style={{ fontFamily: theme.bodyFont || 'Manrope, sans-serif', color: text }}>
            Your complete wedding album selection has been submitted safely.
          </p>
          <p className="text-sm mb-6 p-3 rounded-lg" style={{ fontFamily: theme.bodyFont || 'Manrope, sans-serif', color: text, backgroundColor: theme.bgAlt || '#FEF9E7' }}>
            <strong>{count} files are ready</strong><br />
            Your album photographs and clearly labelled cover copy are now in <strong>Album Favourites</strong>. Mark has been notified automatically and your choices are locked against accidental changes.
          </p>
          <button
            onClick={onClose}
            className="px-8 py-3 rounded-sm text-sm font-medium tracking-wider transition-colors"
            style={{ backgroundColor: theme.accent || '#D4AF37', color: 'white', fontFamily: theme.bodyFont || 'Manrope, sans-serif' }}
          >
            Close
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
