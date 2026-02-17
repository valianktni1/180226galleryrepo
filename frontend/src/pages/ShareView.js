import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Heart, Download, X, ChevronLeft, ChevronRight, Camera, FolderOpen, Film,
  ArrowLeft, Upload, Image as ImageIcon
} from "lucide-react";
import {
  getShareFiles, toggleShareFavourite, downloadShareFile, downloadShareZip, guestUpload, previewUrl, thumbUrl
} from "@/lib/api";

export default function ShareView() {
  const { token } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const guestInputRef = useRef(null);

  const [galleryName, setGalleryName] = useState("");
  const [galleryId, setGalleryId] = useState(null);
  const [subfolders, setSubfolders] = useState([]);
  const [allowUploads, setAllowUploads] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeAlbum, setActiveAlbum] = useState(null); // null = landing, string = subfolder name
  const [lightboxIndex, setLightboxIndex] = useState(-1);
  const [showFavourites, setShowFavourites] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const loadFiles = useCallback(async () => {
    try {
      const res = await getShareFiles(token);
      setGalleryName(res.data.gallery_name);
      setGalleryId(res.data.gallery_id);
      setSubfolders(res.data.subfolders);
      setAllowUploads(res.data.allow_uploads);
    } catch {
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
    try {
      const res = await downloadShareFile(token, file.id);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = file.filename; a.click();
      window.URL.revokeObjectURL(url);
    } catch { toast.error("Download failed"); }
  };

  const handleDownloadAlbum = async () => {
    setDownloading(true);
    try {
      const ids = showFavourites
        ? allFiles.filter(f => f.is_favourite).map(f => f.id)
        : activeAlbum
          ? (subfolders.find(sf => sf.name === activeAlbum)?.files || []).map(f => f.id)
          : [];
      const res = await downloadShareZip(token, ids);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = showFavourites ? "favourites.zip" : `${activeAlbum || galleryName}.zip`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Download started");
    } catch { toast.error("Download failed"); }
    finally { setDownloading(false); }
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

  // Only show albums that have files (except for upload-only shares)
  const visibleAlbums = subfolders.filter(sf => sf.files.length > 0 || sf.name === "Guest Uploads");

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
              <Camera className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
              <span className="text-sm tracking-[0.15em] font-bold" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>
                Weddings By Mark
              </span>
            </div>
            {favCount > 0 && (
              <Button data-testid="show-favourites-landing" variant="ghost" onClick={() => setShowFavourites(true)}
                className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
                <Heart className="w-3.5 h-3.5" fill="#D4AF37" stroke="#D4AF37" /> Favourites ({favCount})
              </Button>
            )}
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
        </motion.section>

        {/* Albums Section */}
        <section className="max-w-screen-xl mx-auto px-6 py-12 md:py-16">
          <div className="flex items-center gap-2 mb-8">
            <FolderOpen className="w-5 h-5 text-[#78716C]" strokeWidth={1.5} />
            <h2 className="text-xl font-semibold" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>Albums</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-12">
            {visibleAlbums.filter(sf => sf.name !== "Guest Uploads").map((sf, i) => (
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
                {/* Show cover thumbnail if available */}
                {sf.files.length > 0 && sf.files[0].has_thumb ? (
                  <div className="w-full aspect-[4/3] mb-4 overflow-hidden" style={{ backgroundColor: '#F5F2EB' }}>
                    <img
                      src={thumbUrl(galleryId, sf.name, sf.files[0].filename)}
                      alt={sf.name}
                      className="w-full h-full object-cover"
                      style={{ transition: 'transform 0.5s ease' }}
                      onMouseOver={e => e.target.style.transform = 'scale(1.05)'}
                      onMouseOut={e => e.target.style.transform = 'scale(1)'}
                    />
                  </div>
                ) : (
                  <div className="w-12 h-12 mb-4 flex items-center justify-center">
                    <FolderOpen className="w-8 h-8 text-[#A8A29E]" strokeWidth={1.5} />
                  </div>
                )}
                <p className="font-medium text-sm mb-1" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>{sf.name}</p>
                <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>{sf.files.length} files</p>
              </motion.button>
            ))}
          </div>

          {/* Guest Upload Section */}
          {allowUploads && (
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
            <Button data-testid="download-favourites-btn" variant="ghost" onClick={handleDownloadAlbum} disabled={downloading}
              className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : "Download All"}
            </Button>
          </div>
        </header>
        <main className="max-w-screen-xl mx-auto px-6 py-8">
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
                  onClick={() => setLightboxIndex(i)} />
              ))}
            </div>
          )}
        </main>
        <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
          setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
          galleryId={galleryId} onFav={handleFavourite} onDownload={handleDownloadSingle} />
      </div>
    );
  }

  // ─── ALBUM DETAIL VIEW ───
  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button data-testid="back-to-albums" onClick={() => { setActiveAlbum(null); setLightboxIndex(-1); }}
              className="text-[#57534E] hover:text-[#1C1917]" style={{ transition: 'color 0.2s ease' }}>
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>{activeAlbum}</h1>
              <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>{coupleName} &middot; {currentAlbumFiles.length} files</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {favCount > 0 && (
              <Button data-testid="show-favourites-album" variant="ghost" onClick={() => setShowFavourites(true)}
                className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
                <Heart className="w-3.5 h-3.5" fill="#D4AF37" stroke="#D4AF37" /> ({favCount})
              </Button>
            )}
            <Button data-testid="download-album-btn" variant="ghost" onClick={handleDownloadAlbum} disabled={downloading}
              className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : "Download All"}
            </Button>
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
                onClick={() => setLightboxIndex(i)} />
            ))}
          </div>
        )}
      </main>

      <Lightbox currentPhoto={currentPhoto} lightboxIndex={lightboxIndex} total={displayFiles.length}
        setLightboxIndex={setLightboxIndex} goNext={goNext} goPrev={goPrev}
        galleryId={galleryId} onFav={handleFavourite} onDownload={handleDownloadSingle} />
    </div>
  );
}

// ─── Reusable Components ───
function FileCard({ file, index, galleryId, onFav, onDownload, onClick }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.02 }}
      className="masonry-item photo-card cursor-pointer"
      onClick={onClick}
      data-testid={`share-file-${file.id}`}
    >
      {file.file_type === 'photo' && file.has_preview ? (
        <img src={previewUrl(galleryId, file.subfolder || file._subfolder, file.filename)} alt={file.filename} className="w-full block" loading="lazy" />
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
      <div className="photo-overlay" />
      <div className="photo-actions flex items-center justify-between">
        <button data-testid={`fav-btn-${file.id}`} onClick={e => { e.stopPropagation(); onFav(file.id); }}
          className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}>
          <Heart className="w-4 h-4" fill={file.is_favourite ? '#D4AF37' : 'none'} stroke={file.is_favourite ? '#D4AF37' : '#1C1917'} />
        </button>
        <button data-testid={`download-btn-${file.id}`} onClick={e => { e.stopPropagation(); onDownload(file); }}
          className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}>
          <Download className="w-4 h-4 text-[#1C1917]" />
        </button>
      </div>
    </motion.div>
  );
}

function Lightbox({ currentPhoto, lightboxIndex, total, setLightboxIndex, goNext, goPrev, galleryId, onFav, onDownload }) {
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
            <button data-testid="lightbox-download" onClick={e => { e.stopPropagation(); onDownload(currentPhoto); }}
              className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
              <Download className="w-5 h-5 text-white" />
            </button>
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
