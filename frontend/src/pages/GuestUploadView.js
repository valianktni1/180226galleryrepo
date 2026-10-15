import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Upload, Camera, Check, Heart, Image as ImageIcon, Film, Mic2, Moon, Sun, ArrowLeft } from "lucide-react";
import { guestUpload, getGuestUploadCount, trackGalleryView, getErrorMessage } from "@/lib/api";
import VoiceMessageRecorder from "@/components/VoiceMessageRecorder";

export default function GuestUploadView({ galleryName }) {
  const { token } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [guestName, setGuestName] = useState("");
  const [uploadCount, setUploadCount] = useState(0);
  const [showSuccess, setShowSuccess] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);

  const allowAllFileTypes = localStorage.getItem(`allow_all_file_types_${token}`) === 'true';
  const [mode, setMode] = useState(allowAllFileTypes ? 'media' : 'choice');
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('gallery_dark_mode') === 'true');

  const colours = darkMode ? {
    bg: '#171717', card: '#242424', text: '#FAFAF9', muted: '#C4C0B8', border: '#3F3F46', soft: 'rgba(212,175,55,0.12)'
  } : {
    bg: '#FDFCF8', card: '#FFFFFF', text: '#1C1917', muted: '#57534E', border: '#E7E5E4', soft: 'rgba(212,175,55,0.08)'
  };

  const toggleDarkMode = () => {
    setDarkMode((current) => {
      localStorage.setItem('gallery_dark_mode', String(!current));
      return !current;
    });
  };

  // Extract couple name from gallery folder name (e.g., "Gina & Mark 30.11.22" -> "Gina & Mark")
  const coupleName = galleryName?.replace(/\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$/, '').trim() || galleryName || "the happy couple";

  // Fetch initial upload count
  const fetchUploadCount = useCallback(async () => {
    try {
      const res = await getGuestUploadCount(token);
      setUploadCount(res.data.count);
    } catch (err) {
      console.error("Failed to fetch upload count:", err);
    }
  }, [token]);

  useEffect(() => {
    if (!localStorage.getItem("share_token")) {
      navigate(`/s/${token}`);
      return;
    }
    fetchUploadCount();
    trackGalleryView(token);
  }, [token, navigate, fetchUploadCount]);

  const handleUpload = async (fileList) => {
    if (!fileList?.length) return;
    
    setUploading(true);
    setUploadProgress(0);
    setUploadedFiles([]);
    
    try {
      const files = Array.from(fileList);
      
      if (allowAllFileTypes) {
        // PHOTOGRAPHER MODE: Upload files one at a time for reliability with large files
        const allUploaded = [];
        for (let i = 0; i < files.length; i++) {
          setUploadProgress(Math.round(((i) / files.length) * 100));
          try {
            const res = await guestUpload(token, [files[i]], (e) => {
              const fileProgress = Math.round((e.loaded * 100) / e.total);
              const overallProgress = Math.round(((i + fileProgress / 100) / files.length) * 100);
              setUploadProgress(overallProgress);
            });
            if (res.data.uploaded) {
              allUploaded.push(...res.data.uploaded);
            }
          } catch (err) {
            toast.error(`Failed to upload ${files[i].name}: ${getErrorMessage(err, "Upload error")}`);
          }
        }
        
        setUploadedFiles(allUploaded);
        setUploadProgress(100);
        
        if (allUploaded.length > 0) {
          toast.success(`${allUploaded.length} file(s) uploaded successfully`);
          setShowSuccess(true);
          fetchUploadCount();
          setTimeout(() => {
            setShowSuccess(false);
            setUploadedFiles([]);
          }, 5000);
        }
      } else {
        // GUEST MODE: Upload files one at a time for reliability (avoids proxy body size limits)
        const allUploaded = [];
        const allSkipped = [];
        for (let i = 0; i < files.length; i++) {
          try {
            const res = await guestUpload(token, [files[i]], (e) => {
              const fileProgress = Math.round((e.loaded * 100) / e.total);
              const overallProgress = Math.round(((i + fileProgress / 100) / files.length) * 100);
              setUploadProgress(overallProgress);
            });
            if (res.data.uploaded) allUploaded.push(...res.data.uploaded);
            if (res.data.skipped) allSkipped.push(...res.data.skipped);
          } catch (err) {
            toast.error(`Failed to upload ${files[i].name}: ${getErrorMessage(err, "Upload error")}`);
          }
        }
        
        setUploadedFiles(allUploaded);
        setUploadProgress(100);
        
        if (allSkipped.length > 0) {
          toast.warning(`${allSkipped.length} file(s) exceeded 500MB limit and were not uploaded`);
        }
        
        if (allUploaded.length > 0) {
          setShowSuccess(true);
          fetchUploadCount();
          setTimeout(() => {
            setShowSuccess(false);
            setUploadedFiles([]);
          }, 5000);
        } else if (allSkipped.length === 0) {
          toast.error("No files were uploaded");
        }
      }
      
    } catch (err) {
      toast.error(getErrorMessage(err, "Upload failed. Please try again."));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  if (!allowAllFileTypes && mode === 'choice') {
    return (
      <div className="min-h-screen flex flex-col transition-colors" style={{ backgroundColor: colours.bg, color: colours.text }}>
        <header className="border-b" style={{ borderColor: colours.border }}>
          <div className="max-w-screen-xl mx-auto px-5 py-4 flex items-center justify-between">
            <img src="/logo.png" alt="Weddings By Mark" className="h-8" style={{ filter: 'invert(1)' }} />
            <button type="button" onClick={toggleDarkMode} className="w-10 h-10 rounded-full flex items-center justify-center border"
              style={{ borderColor: colours.border, color: colours.text }} aria-label={darkMode ? 'Use light mode' : 'Use dark mode'}>
              {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </header>
        <main className="flex-1 flex items-center justify-center px-5 py-10">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-2xl text-center">
            <p className="text-xs uppercase tracking-[0.28em] mb-3" style={{ color: '#D4AF37', fontFamily: 'Manrope, sans-serif' }}>Share a memory</p>
            <h1 className="text-3xl sm:text-4xl font-light italic mb-3" style={{ fontFamily: 'Cormorant Garamond, serif', color: colours.text }}>
              Celebrate {coupleName}
            </h1>
            <p className="text-sm mb-8" style={{ color: colours.muted, fontFamily: 'Manrope, sans-serif' }}>
              Add a moment from the day, or leave a personal message they can listen to for years to come.
            </p>
            <div className="grid sm:grid-cols-2 gap-4 text-left">
              <button type="button" onClick={() => setMode('media')} data-testid="choose-photo-video"
                className="p-6 rounded-lg border transition-transform hover:-translate-y-0.5 text-left"
                style={{ backgroundColor: colours.card, borderColor: colours.border, color: colours.text }}>
                <span className="w-11 h-11 rounded-full flex items-center justify-center mb-5" style={{ backgroundColor: colours.soft }}>
                  <Camera className="w-5 h-5 text-[#D4AF37]" />
                </span>
                <strong className="block text-lg mb-2" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Upload Photos &amp; Videos</strong>
                <span className="text-sm leading-relaxed" style={{ color: colours.muted, fontFamily: 'Manrope, sans-serif' }}>Share the moments you captured on your phone.</span>
              </button>
              <button type="button" onClick={() => setMode('voice')} data-testid="choose-voice-message"
                className="p-6 rounded-lg border transition-transform hover:-translate-y-0.5 text-left"
                style={{ backgroundColor: colours.card, borderColor: '#D4AF37', color: colours.text, boxShadow: '0 12px 30px rgba(212,175,55,0.10)' }}>
                <span className="w-11 h-11 rounded-full flex items-center justify-center mb-5" style={{ backgroundColor: colours.soft }}>
                  <Mic2 className="w-5 h-5 text-[#D4AF37]" />
                </span>
                <strong className="block text-lg mb-2" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Record Your Personal Message</strong>
                <span className="text-sm leading-relaxed" style={{ color: colours.muted, fontFamily: 'Manrope, sans-serif' }}>Leave your own voice message, up to four minutes long.</span>
              </button>
            </div>
          </motion.div>
        </main>
      </div>
    );
  }

  if (!allowAllFileTypes && mode === 'voice') {
    return (
      <div className="min-h-screen flex flex-col transition-colors" style={{ backgroundColor: colours.bg, color: colours.text }}>
        <header className="border-b" style={{ borderColor: colours.border }}>
          <div className="max-w-screen-xl mx-auto px-5 py-4 flex items-center justify-between">
            <img src="/logo.png" alt="Weddings By Mark" className="h-8" style={{ filter: 'invert(1)' }} />
            <button type="button" onClick={toggleDarkMode} className="w-10 h-10 rounded-full flex items-center justify-center border"
              style={{ borderColor: colours.border, color: colours.text }} aria-label={darkMode ? 'Use light mode' : 'Use dark mode'}>
              {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </header>
        <VoiceMessageRecorder token={token} coupleName={coupleName} darkMode={darkMode}
          onBack={() => setMode('choice')} onComplete={() => setMode('choice')} />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: colours.bg }}>
      {/* Header */}
      <header className="border-b" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          {!allowAllFileTypes ? (
            <button type="button" onClick={() => setMode('choice')} className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ color: colours.text }} aria-label="Back to sharing choices"><ArrowLeft className="w-5 h-5" /></button>
          ) : <span className="w-10" />}
          <img src="/logo.png" alt="Weddings By Mark" className="h-8" style={{ filter: 'invert(1)' }} />
          <button type="button" onClick={toggleDarkMode} className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ color: colours.text }} aria-label={darkMode ? 'Use light mode' : 'Use dark mode'}>
            {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-lg text-center"
        >
          {/* Welcome Message */}
          <div className="mb-8">
            <Camera className="w-12 h-12 mx-auto mb-4 text-[#D4AF37]" strokeWidth={1.5} />
            <h1 
              className="text-3xl md:text-4xl font-light italic mb-3"
              style={{ fontFamily: 'Cormorant Garamond, serif', color: colours.text }}
              data-testid="guest-upload-title"
            >
              {allowAllFileTypes 
                ? <>Upload files for<br />{coupleName}'s wedding</>
                : <>Share your photos & videos from<br />{coupleName}'s wedding!</>
              }
            </h1>
            <p className="text-sm" style={{ color: colours.muted, fontFamily: 'Manrope, sans-serif' }}>
              {allowAllFileTypes
                ? "Upload RAW files, photos, videos and any other files"
                : "Help capture every special moment by uploading your photos and videos"
              }
            </p>
          </div>

          {/* Live Counter */}
          <motion.div
            key={uploadCount}
            initial={{ scale: 0.95 }}
            animate={{ scale: 1 }}
            className="mb-8 p-4 rounded-lg inline-flex items-center gap-3"
            style={{ backgroundColor: colours.card }}
            data-testid="upload-counter"
          >
            <Heart className="w-5 h-5 text-[#D4AF37]" fill="#D4AF37" />
            <span className="text-lg font-medium" style={{ fontFamily: 'Manrope, sans-serif', color: colours.text }}>
              <strong>{uploadCount}</strong> {uploadCount === 1 ? 'photo' : 'photos'} shared by guests so far!
            </span>
          </motion.div>

          {/* Optional Name Field */}
          <div className="mb-6">
            <Input
              type="text"
              value={guestName}
              onChange={(e) => setGuestName(e.target.value)}
              placeholder="Your name (optional)"
              className="max-w-xs mx-auto border-[#D4D4D8] rounded-sm text-center"
              style={{ fontFamily: 'Manrope, sans-serif' }}
              data-testid="guest-name-input"
            />
          </div>

          {/* Upload Zone */}
          <div
            className={`upload-zone p-8 md:p-12 cursor-pointer transition-all duration-300 ${dragOver ? 'drag-over ring-2 ring-[#D4AF37]' : ''}`}
            style={{ 
              backgroundColor: dragOver ? 'rgba(212,175,55,0.1)' : 'rgba(212,175,55,0.04)',
              borderRadius: '8px'
            }}
            onClick={() => !uploading && fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            data-testid="guest-upload-zone"
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={allowAllFileTypes ? undefined : "image/*,video/*"}
              className="hidden"
              onChange={(e) => handleUpload(e.target.files)}
              data-testid="guest-file-input"
            />
            
            {uploading ? (
              <div className="w-full max-w-xs mx-auto">
                <Upload className="w-10 h-10 mx-auto mb-4 text-[#D4AF37] animate-bounce" strokeWidth={1.5} />
                <p className="text-base mb-3 font-medium" style={{ color: colours.text, fontFamily: 'Manrope, sans-serif' }}>
                  Uploading... {uploadProgress}%
                </p>
                <Progress value={uploadProgress} className="h-2" />
              </div>
            ) : (
              <>
                <Upload className="w-14 h-14 mx-auto mb-4 text-[#D4AF37]" strokeWidth={1.5} />
                <p className="text-xl font-medium mb-2" style={{ fontFamily: 'Manrope, sans-serif', color: colours.text }}>
                  {allowAllFileTypes ? "Tap here to choose files" : "Tap here to choose photos & videos"}
                </p>
                <p className="text-sm mb-4" style={{ color: colours.muted, fontFamily: 'Manrope, sans-serif' }}>
                  or drag & drop your files
                </p>
                <Button
                  className="bg-[#D4AF37] text-white hover:bg-[#D4AF37]/90 rounded-sm px-8 py-3 text-sm tracking-wider uppercase font-bold"
                  style={{ fontFamily: 'Manrope, sans-serif' }}
                  data-testid="upload-button"
                >
                  <Upload className="w-4 h-4 mr-2" /> {allowAllFileTypes ? "Upload Files" : "Upload Photos"}
                </Button>
              </>
            )}
          </div>

          <p className="mt-4 text-xs" style={{ color: colours.muted, fontFamily: 'Manrope, sans-serif' }}>
            {allowAllFileTypes ? "All file types accepted - up to 500MB each" : "Photos and videos up to 500MB each"}
          </p>
        </motion.div>
      </main>

      {/* Success Animation Modal */}
      <AnimatePresence>
        {showSuccess && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
            onClick={() => setShowSuccess(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.8, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.8, y: 20 }}
              transition={{ type: 'spring', duration: 0.5 }}
              className="rounded-lg p-8 max-w-md w-full text-center shadow-2xl"
              style={{ backgroundColor: colours.card }}
              onClick={(e) => e.stopPropagation()}
              data-testid="success-modal"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.2, duration: 0.5 }}
                className="w-20 h-20 mx-auto mb-6 rounded-full flex items-center justify-center"
                style={{ backgroundColor: '#D4AF37' }}
              >
                <Check className="w-10 h-10 text-white" strokeWidth={3} />
              </motion.div>
              
              <h2 className="text-3xl font-medium mb-3" style={{ fontFamily: 'Cormorant Garamond, serif', color: colours.text }}>
                Thank You!
              </h2>
              <p className="text-base mb-6" style={{ fontFamily: 'Manrope, sans-serif', color: colours.muted }}>
                {uploadedFiles.length} {uploadedFiles.length === 1 ? 'file has' : 'files have'} been uploaded successfully!
              </p>
              
              {/* Show uploaded file thumbnails */}
              {uploadedFiles.length > 0 && uploadedFiles.length <= 6 && (
                <div className="flex justify-center gap-2 mb-6 flex-wrap">
                  {uploadedFiles.map((file, i) => (
                    <div key={i} className="w-12 h-12 rounded overflow-hidden flex items-center justify-center" style={{ backgroundColor: colours.soft }}>
                      {file.file_type === 'photo' ? (
                        <ImageIcon className="w-6 h-6 text-[#A8A29E]" />
                      ) : (
                        <Film className="w-6 h-6 text-[#A8A29E]" />
                      )}
                    </div>
                  ))}
                </div>
              )}
              
              <Button
                onClick={() => setShowSuccess(false)}
                className="px-8 py-3 rounded-sm text-sm font-medium tracking-wider"
                style={{ backgroundColor: '#D4AF37', color: 'white', fontFamily: 'Manrope, sans-serif' }}
              >
                Upload More
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
