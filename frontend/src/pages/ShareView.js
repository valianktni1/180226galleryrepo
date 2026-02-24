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
  ArrowLeft, Upload, Image as ImageIcon, Trash2, Check, Printer
} from "lucide-react";
import {
  getShareFiles, toggleShareFavourite, submitFavouritesToAlbum, downloadShareFile, getShareDownloadUrl, getShareFavouritesDownloadUrl, guestUpload, guestDeleteFiles, previewUrl, thumbUrl, trackGalleryView, trackDownload, getErrorMessage
} from "@/lib/api";
import GuestUploadView from "@/pages/GuestUploadView";

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
        accessLevel: res.data.access_level || "download"
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

  const handleDownloadSingle = async (file) => {
    if (!permissions.allowDownloads) {
      toast.error("Downloads are not allowed on this share");
      return;
    }
    try {
      const res = await downloadShareFile(token, file.id);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Download failed");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = file.filename; a.click();
      window.URL.revokeObjectURL(url);
      // Track download
      trackDownload(token);
    } catch (err) { toast.error(err.message || "Download failed"); }
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
      toast.error(err.response?.data?.detail || "Delete failed");
    }
  };

  const handleGuestUpload = async (fileList) => {
    if (!fileList?.length) return;
    setUploading(true);
    setUploadProgress(0);
    try {
      await guestUpload(token, Array.from(fileList), (e) => {
        setUploadProgress(Math.round((e.loaded * 100) / e.total));
      });
      toast.success("Photos uploaded! Thank you!");
      loadFiles();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const allFiles = subfolders.flatMap(sf => sf.files.map(f => ({ ...f, _subfolder: sf.name })));
  const currentAlbumFiles = activeAlbum ? (subfolders.find(sf => sf.name === activeAlbum)?.files || []) : [];
  const displayFiles = showFavourites ? allFiles.filter(f => f.is_favourite) : currentAlbumFiles;
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

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  // If no gallery name, something went wrong - show error
  if (!galleryName) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}>
        <div className="text-center">
          <p className="text-lg mb-4" style={{ color: '#57534E' }}>Unable to load gallery</p>
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

  // ─── LANDING PAGE (Album cards view) ───
  if (!activeAlbum && !showFavourites) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
        {/* Header */}
        <header className="border-b" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
          <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="Weddings By Mark" className="h-8" style={{ filter: 'invert(1)' }} />
            </div>
            <div className="flex items-center gap-3">
              <Button data-testid="order-prints-btn" onClick={() => navigate(`/s/${token}/prints`)}
                className="bg-[#D4AF37] hover:bg-[#B8962E] text-white rounded-sm gap-2 text-xs tracking-wider uppercase font-bold px-4 py-2 shadow-md">
                <Printer className="w-4 h-4" /> Order Prints
              </Button>
              {favCount > 0 && (
                <Button data-testid="show-favourites-landing" variant="ghost" onClick={() => setShowFavourites(true)}
                  className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
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
          transition={{ duration: 0.8 }}
          className="text-center py-16 md:py-24 px-6"
          style={{ backgroundColor: '#F5F2EB' }}
        >
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-sm tracking-[0.2em] uppercase mb-4"
            style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}
          >
            Welcome
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="text-5xl md:text-7xl font-light italic mb-4"
            style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}
            data-testid="couple-name-heading"
          >
            {coupleName}
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="text-base md:text-lg"
            style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}
          >
            Your special memories, beautifully captured
          </motion.p>
          
          {/* Album Instructions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
            className="mt-10 mx-auto max-w-2xl text-left p-6 rounded-lg border-2"
            style={{ backgroundColor: 'white', borderColor: '#D4AF37' }}
          >
            <h3 className="text-xl font-medium mb-4 flex items-center gap-2" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>
              <Heart className="w-5 h-5" fill="#D4AF37" stroke="#D4AF37" />
              Your Wedding Album (If Included in Your Package)
            </h3>
            <div className="space-y-3 text-sm" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              <p>To choose your album images, simply go to your <strong>Wedding Images</strong> folder.</p>
              <ul className="list-disc list-inside space-y-1 pl-2">
                <li>Click the heart icon on each image to select your 40 favourites</li>
                <li>Don't forget to choose one image for your front cover</li>
              </ul>
              <p>At the top of the gallery, you'll see a <span className="inline-flex items-center"><Heart className="w-4 h-4 mx-1" fill="#D4AF37" stroke="#D4AF37" /></span> gold heart showing how many images you've selected.</p>
              <p className="font-medium pt-2">Once you're happy:</p>
              <ol className="list-decimal list-inside space-y-1 pl-2">
                <li>Click the gold heart</li>
                <li>Press <strong>"Submit for Album"</strong></li>
              </ol>
              <p>Your selections will then appear in your <strong>Album Favourites</strong> folder.</p>
              <p className="pt-3 border-t" style={{ borderColor: '#F5F2EB' }}>
                Please email me at <a href="mailto:mark@perfectweddingsbymark.uk" className="underline" style={{ color: '#D4AF37' }}>mark@perfectweddingsbymark.uk</a> to let me know you've submitted your choices, and include the image number of your chosen front cover.
              </p>
              <p className="text-center pt-2">Thank you 😊</p>
            </div>
          </motion.div>
        </motion.section>

        {/* Albums Section */}
        <section className="max-w-screen-xl mx-auto px-6 py-12 md:py-16">
          <div className="flex items-center gap-2 mb-8">
            <FolderOpen className="w-5 h-5 text-[#78716C]" strokeWidth={1.5} />
            <h2 className="text-xl font-semibold" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>Albums</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-12">
            {visibleAlbums.map((sf, i) => (
              <motion.button
                key={sf.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.08 }}
                onClick={() => { setActiveAlbum(sf.name); setShowFavourites(false); }}
                className="group p-6 text-left border bg-white hover:shadow-md"
                style={{ borderColor: '#F5F2EB', transition: 'box-shadow 0.3s ease' }}
                data-testid={`album-card-${sf.name.replace(/\s/g, '-')}`}
              >
                {/* Show cover thumbnail - use custom cover if set, otherwise first image */}
                {(() => {
                  const coverId = covers[sf.name];
                  const coverFile = coverId ? sf.files.find(f => f.id === coverId) : null;
                  const displayFile = coverFile || (sf.files.length > 0 ? sf.files[0] : null);
                  
                  if (displayFile && displayFile.has_thumb) {
                    return (
                      <div className="w-full aspect-[4/3] mb-4 overflow-hidden" style={{ backgroundColor: '#F5F2EB' }}>
                        <img
                          src={thumbUrl(galleryId, sf.name, displayFile.filename)}
                          alt={sf.name}
                          className="w-full h-full object-cover"
                          style={{ transition: 'transform 0.5s ease' }}
                          onMouseOver={e => e.target.style.transform = 'scale(1.05)'}
                          onMouseOut={e => e.target.style.transform = 'scale(1)'}
                        />
                      </div>
                    );
                  }
                  return (
                    <div className="w-12 h-12 mb-4 flex items-center justify-center">
                      <FolderOpen className="w-8 h-8 text-[#A8A29E]" strokeWidth={1.5} />
                    </div>
                  );
                })()}
                <p className="font-medium text-sm mb-1" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>{sf.name}</p>
                <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>{sf.files.length} files</p>
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
                <h2 className="text-xl font-semibold" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>Upload Photos & Videos</h2>
              </div>
              <p className="text-sm mb-4" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
                Share your photos and videos from the event
              </p>
              <div
                className="upload-zone p-8 flex flex-col items-center justify-center text-center cursor-pointer"
                style={{ minHeight: '140px', backgroundColor: 'rgba(212,175,55,0.04)' }}
                onClick={() => guestInputRef.current?.click()}
                data-testid="guest-upload-zone"
              >
                <input ref={guestInputRef} type="file" multiple accept="image/*,video/*" className="hidden"
                  onChange={e => handleGuestUpload(e.target.files)} data-testid="guest-file-input" />
                {uploading ? (
                  <div className="w-full max-w-xs">
                    <p className="text-sm mb-2" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>Uploading... {uploadProgress}%</p>
                    <Progress value={uploadProgress} className="h-1.5" />
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 mb-3 text-[#D4AF37]" strokeWidth={1.5} />
                    <p className="text-sm font-medium mb-1" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      Click to choose files or drag & drop
                    </p>
                    <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                      Photos and videos up to 500MB each
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
              <p className="text-sm tracking-wide" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>
                Site Designed & Maintained by
              </p>
              <p className="text-xl font-medium italic mt-1" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>
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
      <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
        <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
          <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button data-testid="back-from-favourites" onClick={() => setShowFavourites(false)}
                className="text-[#57534E] hover:text-[#1C1917]" style={{ transition: 'color 0.2s ease' }}>
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Your Favourites</h1>
              <span className="text-xs" style={{ color: '#A8A29E' }}>({favCount})</span>
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
                  className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
                  <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : "Download All"}
                </Button>
              )}
            </div>
          </div>
        </header>
        <main className="max-w-screen-xl mx-auto px-6 py-8">
          <div className="mb-6 p-4 rounded-lg" style={{ backgroundColor: '#F5F2EB' }}>
            <p className="text-sm" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              <Heart className="w-4 h-4 inline mr-2" fill="#D4AF37" stroke="#D4AF37" />
              Heart your favourite photos, then click <strong>"Submit for Album"</strong> to send them for your wedding album.
            </p>
          </div>
          {displayFiles.length === 0 ? (
            <div className="text-center py-20">
              <Heart className="w-12 h-12 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
              <p className="text-xl" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No favourites yet</p>
              <p className="text-sm mt-2" style={{ color: '#A8A29E' }}>Heart the photos you love to see them here</p>
            </div>
          ) : (
            <div className="masonry-grid">
              {displayFiles.map((file, i) => (
                <FileCard key={file.id} file={file} index={i} galleryId={galleryId}
                  onFav={handleFavourite} onDownload={handleDownloadSingle}
                  onClick={() => setLightboxIndex(i)} permissions={permissions} />
              ))}
            </div>
          )}
        </main>
        <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
          setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
          galleryId={galleryId} onFav={handleFavourite} onDownload={handleDownloadSingle} permissions={permissions} />
        <ThankYouModal show={showThankYou} onClose={() => setShowThankYou(false)} count={submittedCount} galleryName={galleryName} />
      </div>
    );
  }

  // ─── ALBUM DETAIL VIEW ───
  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button data-testid="back-to-albums" onClick={() => { setActiveAlbum(null); setLightboxIndex(-1); setSelectMode(false); setSelectedFiles(new Set()); }}
              className="text-[#57534E] hover:text-[#1C1917]" style={{ transition: 'color 0.2s ease' }}>
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>{activeAlbum}</h1>
              <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>{coupleName} &middot; {currentAlbumFiles.length} files</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {permissions.allowDelete && (
              <Button data-testid="select-mode-btn" variant={selectMode ? "default" : "ghost"} 
                onClick={() => { setSelectMode(m => !m); setSelectedFiles(new Set()); }}
                className={`rounded-sm text-xs tracking-wider gap-1.5 ${selectMode ? 'bg-[#1C1917] text-[#FDFCF8]' : 'text-[#57534E]'}`}
                style={{ fontFamily: 'Manrope, sans-serif' }}>
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
                className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
                <Heart className="w-3.5 h-3.5" fill="#D4AF37" stroke="#D4AF37" /> ({favCount})
              </Button>
            )}
            {permissions.allowDownloads && !selectMode && (
              <Button data-testid="download-album-btn" variant="ghost" onClick={handleDownloadAlbum} disabled={downloading}
                className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
                <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : "Download All"}
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-8">
        {currentAlbumFiles.length === 0 ? (
          <div className="text-center py-20">
            <FolderOpen className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" strokeWidth={1} />
            <p className="text-xl" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No files in {activeAlbum}</p>
          </div>
        ) : (
          <div className="masonry-grid">
            {currentAlbumFiles.map((file, i) => (
              <FileCard key={file.id} file={file} index={i} galleryId={galleryId}
                onFav={handleFavourite} onDownload={handleDownloadSingle}
                onClick={selectMode ? () => toggleSelect(file.id) : () => setLightboxIndex(i)} 
                permissions={permissions}
                selectMode={selectMode}
                isSelected={selectedFiles.has(file.id)} />
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
            <p className="text-sm tracking-wide" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>
              Site Designed & Maintained by
            </p>
            <p className="text-xl font-medium italic mt-1" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>
              Weddings By Mark
            </p>
          </div>
        </div>
      </footer>

      <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
        setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
        galleryId={galleryId} onFav={handleFavourite} onDownload={handleDownloadSingle} permissions={permissions} />
      
      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="border-none shadow-2xl rounded-none" style={{ backgroundColor: '#FDFCF8' }}>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Delete {selectedFiles.size} file(s)?
            </AlertDialogTitle>
            <AlertDialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
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
    </div>
  );
}

// ─── Reusable Components ───
function FileCard({ file, index, galleryId, onFav, onDownload, onClick, permissions = {}, selectMode = false, isSelected = false }) {
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
          <img src={previewUrl(galleryId, file.subfolder || file._subfolder, file.filename)} alt={file.filename} className="w-full block" loading="lazy" />
        ) : (
          <div className="aspect-square flex flex-col items-center justify-center" style={{ backgroundColor: '#F5F2EB' }}>
            <ImageIcon className="w-8 h-8 text-[#A8A29E] mb-1" />
            <span className="text-xs text-[#A8A29E] truncate max-w-[80%]">{file.filename}</span>
          </div>
        )
      ) : file.file_type === 'video' ? (
        <div className="aspect-video flex flex-col items-center justify-center" style={{ backgroundColor: '#F5F2EB' }}>
          <Film className="w-8 h-8 text-[#A8A29E] mb-1" />
          <span className="text-xs text-[#A8A29E] truncate max-w-[80%]">{file.filename}</span>
        </div>
      ) : (
        <div className="aspect-square flex items-center justify-center" style={{ backgroundColor: '#F5F2EB' }}>
          <span className="text-xs text-[#A8A29E]">{file.filename}</span>
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
    </motion.div>
  );
}

function Lightbox({ currentPhoto, lightboxIndex, total, setLightboxIndex, goNext, goPrev, galleryId, onFav, onDownload, permissions = {} }) {
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
              <button data-testid="lightbox-download" onClick={e => { e.stopPropagation(); onDownload(currentPhoto); }}
                className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
                <Download className="w-5 h-5 text-white" />
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
          <motion.img key={currentPhoto.id} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
            src={galleryId && currentPhoto.has_preview ? previewUrl(galleryId, currentPhoto.subfolder || currentPhoto._subfolder, currentPhoto.filename) : ''}
            alt={currentPhoto.filename} className="max-w-[90vw] max-h-[85vh] object-contain" onClick={e => e.stopPropagation()} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ThankYouModal({ show, onClose, count, galleryName }) {
  if (!show) return null;
  
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
          className="bg-white rounded-lg p-8 max-w-md w-full text-center shadow-2xl"
          onClick={e => e.stopPropagation()}
        >
          <div className="w-16 h-16 mx-auto mb-6 rounded-full flex items-center justify-center" style={{ backgroundColor: '#D4AF37' }}>
            <Heart className="w-8 h-8 text-white" fill="white" />
          </div>
          <h2 className="text-2xl font-semibold mb-3" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>
            Thank You!
          </h2>
          <p className="text-base mb-4" style={{ fontFamily: 'Manrope, sans-serif', color: '#57534E' }}>
            Your {count} favourite {count === 1 ? 'photo has' : 'photos have'} been submitted for your wedding album.
          </p>
          <p className="text-sm mb-6 p-3 rounded-lg" style={{ fontFamily: 'Manrope, sans-serif', color: '#57534E', backgroundColor: '#FEF9E7' }}>
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
