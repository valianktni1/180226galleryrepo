import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Heart, Download, X, ChevronLeft, ChevronRight, Camera, LogOut, Upload, FolderOpen, Film
} from "lucide-react";
import {
  getShareFiles, toggleShareFavourite, downloadShareFile, downloadShareZip, guestUpload, previewUrl, thumbUrl
} from "@/lib/api";

export default function ShareView() {
  const { token } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [galleryName, setGalleryName] = useState("");
  const [galleryId, setGalleryId] = useState(null);
  const [subfolders, setSubfolders] = useState([]);
  const [allowUploads, setAllowUploads] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("");
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
      if (!activeTab && res.data.subfolders.length) {
        setActiveTab(res.data.subfolders[0].name);
      }
    } catch {
      localStorage.removeItem("share_token");
      localStorage.removeItem("share_url_token");
      navigate(`/s/${token}`);
    } finally {
      setLoading(false);
    }
  }, [token, navigate, activeTab]);

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
      const a = document.createElement("a");
      a.href = url; a.download = file.filename; a.click();
      window.URL.revokeObjectURL(url);
    } catch { toast.error("Download failed"); }
  };

  const handleDownloadAll = async () => {
    setDownloading(true);
    try {
      const ids = showFavourites
        ? allFiles.filter(f => f.is_favourite).map(f => f.id)
        : [];
      const res = await downloadShareZip(token, ids);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url; a.download = showFavourites ? "favourites.zip" : "gallery.zip"; a.click();
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

  const exitGallery = () => {
    localStorage.removeItem("share_token");
    localStorage.removeItem("share_url_token");
    navigate(`/s/${token}`);
  };

  // Flatten all files across subfolders
  const allFiles = subfolders.flatMap(sf => sf.files.map(f => ({ ...f, _subfolder: sf.name })));
  const currentSf = subfolders.find(sf => sf.name === activeTab);
  const currentFiles = currentSf?.files || [];
  const displayFiles = showFavourites ? allFiles.filter(f => f.is_favourite) : currentFiles;
  const favCount = allFiles.filter(f => f.is_favourite).length;

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

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>{galleryName}</h1>
            <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>{allFiles.length} files</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button data-testid="toggle-favourites" variant={showFavourites ? "default" : "ghost"}
              onClick={() => setShowFavourites(f => !f)}
              className={`rounded-sm gap-2 text-xs tracking-wider ${showFavourites ? 'bg-[#1C1917] text-[#FDFCF8]' : 'text-[#57534E]'}`}>
              <Heart className="w-3.5 h-3.5" fill={showFavourites ? '#D4AF37' : 'none'} /> Favourites ({favCount})
            </Button>
            <Button data-testid="download-all-btn" variant="ghost" onClick={handleDownloadAll} disabled={downloading}
              className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing..." : "Download"}
            </Button>
            {allowUploads && (
              <Button data-testid="guest-upload-btn" onClick={() => fileInputRef.current?.click()}
                className="bg-[#D4AF37] text-white hover:bg-[#D4AF37]/90 rounded-sm gap-2 text-xs tracking-wider font-bold">
                <Upload className="w-3.5 h-3.5" /> Upload Photos
              </Button>
            )}
            <Button data-testid="exit-gallery-btn" variant="ghost" onClick={exitGallery} className="text-[#57534E] rounded-sm">
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Guest upload input */}
      {allowUploads && (
        <input ref={fileInputRef} type="file" multiple accept="image/*,video/*" className="hidden"
          onChange={e => handleGuestUpload(e.target.files)} data-testid="guest-file-input" />
      )}

      {/* Upload progress */}
      {uploading && (
        <div className="max-w-screen-xl mx-auto px-6 pt-4">
          <div className="p-4 border" style={{ borderColor: '#D4AF37', backgroundColor: 'rgba(212,175,55,0.05)' }}>
            <p className="text-sm mb-2" style={{ fontFamily: 'Manrope, sans-serif' }}>Uploading... {uploadProgress}%</p>
            <Progress value={uploadProgress} className="h-1.5" />
          </div>
        </div>
      )}

      <main className="max-w-screen-xl mx-auto px-6 py-6">
        {showFavourites ? (
          /* Favourites view */
          <div>
            <h2 className="text-2xl mb-6 font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Your Favourites</h2>
            {displayFiles.length === 0 ? (
              <div className="text-center py-20">
                <Heart className="w-12 h-12 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
                <p className="text-lg" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No favourites yet</p>
                <p className="text-sm" style={{ color: '#A8A29E' }}>Heart the photos you love</p>
              </div>
            ) : (
              <div className="masonry-grid">
                {displayFiles.map((file, i) => (
                  <FileCard key={file.id} file={file} index={i} galleryId={galleryId}
                    onFav={handleFavourite} onDownload={handleDownloadSingle} onClick={() => setLightboxIndex(i)} />
                ))}
              </div>
            )}
          </div>
        ) : subfolders.length === 1 ? (
          /* Single subfolder - no tabs */
          <div>
            {currentFiles.length === 0 ? (
              <div className="text-center py-20">
                <FolderOpen className="w-12 h-12 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
                <p className="text-lg" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No files yet</p>
                {allowUploads && <p className="text-sm mt-2" style={{ color: '#A8A29E' }}>Use the Upload button to share your photos!</p>}
              </div>
            ) : (
              <div className="masonry-grid">
                {currentFiles.map((file, i) => (
                  <FileCard key={file.id} file={file} index={i} galleryId={galleryId}
                    onFav={handleFavourite} onDownload={handleDownloadSingle} onClick={() => setLightboxIndex(i)} />
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Multiple subfolders - tabs */
          <Tabs value={activeTab} onValueChange={v => { setActiveTab(v); setLightboxIndex(-1); }}>
            <TabsList className="bg-transparent border-b w-full justify-start rounded-none h-auto p-0 mb-6" style={{ borderColor: '#F5F2EB' }}>
              {subfolders.map(sf => (
                <TabsTrigger key={sf.name} value={sf.name}
                  className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#D4AF37] data-[state=active]:text-[#1C1917] data-[state=active]:shadow-none px-4 py-3 text-xs tracking-wider uppercase font-semibold text-[#A8A29E]"
                  style={{ fontFamily: 'Manrope, sans-serif' }}>
                  {sf.name} <span className="ml-1.5 text-[10px] opacity-60">({sf.files.length})</span>
                </TabsTrigger>
              ))}
            </TabsList>
            {subfolders.map(sf => (
              <TabsContent key={sf.name} value={sf.name} className="mt-0">
                {sf.files.length === 0 ? (
                  <div className="text-center py-16">
                    <FolderOpen className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" strokeWidth={1} />
                    <p className="text-lg" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No files in {sf.name}</p>
                  </div>
                ) : (
                  <div className="masonry-grid">
                    {sf.files.map((file, i) => (
                      <FileCard key={file.id} file={file} index={i} galleryId={galleryId}
                        onFav={handleFavourite} onDownload={handleDownloadSingle}
                        onClick={() => setLightboxIndex(currentFiles.findIndex(f => f.id === file.id))} />
                    ))}
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        )}
      </main>

      {/* Lightbox */}
      <AnimatePresence>
        {currentPhoto && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="lightbox-overlay" onClick={() => setLightboxIndex(-1)} data-testid="lightbox-overlay">
            <button className="absolute top-6 right-6 text-white/70 hover:text-white z-10" onClick={() => setLightboxIndex(-1)} style={{ transition: 'color 0.2s ease' }}>
              <X className="w-6 h-6" />
            </button>
            <div className="absolute top-6 left-6 flex items-center gap-3 z-10">
              <button data-testid="lightbox-fav" onClick={e => { e.stopPropagation(); handleFavourite(currentPhoto.id); }}
                className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
                <Heart className="w-5 h-5" fill={currentPhoto.is_favourite ? '#D4AF37' : 'none'} stroke={currentPhoto.is_favourite ? '#D4AF37' : 'white'} />
              </button>
              <button data-testid="lightbox-download" onClick={e => { e.stopPropagation(); handleDownloadSingle(currentPhoto); }}
                className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
                <Download className="w-5 h-5 text-white" />
              </button>
            </div>
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/60 text-sm z-10" style={{ fontFamily: 'Manrope, sans-serif' }}>
              {lightboxIndex + 1} / {displayFiles.length}
            </div>
            {lightboxIndex > 0 && (
              <button className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full flex items-center justify-center text-white/60 hover:text-white z-10"
                style={{ backgroundColor: 'rgba(0,0,0,0.3)' }} onClick={e => { e.stopPropagation(); goPrev(); }}>
                <ChevronLeft className="w-6 h-6" />
              </button>
            )}
            {lightboxIndex < displayFiles.length - 1 && (
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
    </div>
  );
}

function FileCard({ file, index, galleryId, onFav, onDownload, onClick }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.03 }}
      className="masonry-item photo-card cursor-pointer" onClick={onClick} data-testid={`share-file-${file.id}`}>
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
