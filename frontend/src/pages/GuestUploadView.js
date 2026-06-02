import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Upload, Camera, Check, Heart, Image as ImageIcon, Film } from "lucide-react";
import { guestUpload, getGuestUploadCount, trackGalleryView, getErrorMessage } from "@/lib/api";

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
        // GUEST MODE: Upload all at once (smaller files)
        const res = await guestUpload(token, files, (e) => {
          setUploadProgress(Math.round((e.loaded * 100) / e.total));
        });
        
        setUploadedFiles(res.data.uploaded || []);
        
        if (res.data.skipped && res.data.skipped.length > 0) {
          toast.warning(`${res.data.skipped.length} file(s) exceeded 500MB limit and were not uploaded`);
        }
        
        if (res.data.uploaded && res.data.uploaded.length > 0) {
          setShowSuccess(true);
          fetchUploadCount();
          setTimeout(() => {
            setShowSuccess(false);
            setUploadedFiles([]);
          }, 5000);
        } else if (!res.data.skipped || res.data.skipped.length === 0) {
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

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Header */}
      <header className="border-b" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-center">
          <img src="/logo.png" alt="Weddings By Mark" className="h-8" style={{ filter: 'invert(1)' }} />
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
              style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}
              data-testid="guest-upload-title"
            >
              {allowAllFileTypes 
                ? <>Upload files for<br />{coupleName}'s wedding</>
                : <>Share your photos & videos from<br />{coupleName}'s wedding!</>
              }
            </h1>
            <p className="text-sm" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
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
            style={{ backgroundColor: '#F5F2EB' }}
            data-testid="upload-counter"
          >
            <Heart className="w-5 h-5 text-[#D4AF37]" fill="#D4AF37" />
            <span className="text-lg font-medium" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>
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
                <p className="text-base mb-3 font-medium" style={{ color: '#1C1917', fontFamily: 'Manrope, sans-serif' }}>
                  Uploading... {uploadProgress}%
                </p>
                <Progress value={uploadProgress} className="h-2" />
              </div>
            ) : (
              <>
                <Upload className="w-14 h-14 mx-auto mb-4 text-[#D4AF37]" strokeWidth={1.5} />
                <p className="text-xl font-medium mb-2" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>
                  {allowAllFileTypes ? "Tap here to choose files" : "Tap here to choose photos & videos"}
                </p>
                <p className="text-sm mb-4" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
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

          <p className="mt-4 text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
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
              className="bg-white rounded-lg p-8 max-w-md w-full text-center shadow-2xl"
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
              
              <h2 className="text-3xl font-medium mb-3" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>
                Thank You!
              </h2>
              <p className="text-base mb-6" style={{ fontFamily: 'Manrope, sans-serif', color: '#57534E' }}>
                {uploadedFiles.length} {uploadedFiles.length === 1 ? 'file has' : 'files have'} been uploaded successfully!
              </p>
              
              {/* Show uploaded file thumbnails */}
              {uploadedFiles.length > 0 && uploadedFiles.length <= 6 && (
                <div className="flex justify-center gap-2 mb-6 flex-wrap">
                  {uploadedFiles.map((file, i) => (
                    <div key={i} className="w-12 h-12 rounded overflow-hidden flex items-center justify-center" style={{ backgroundColor: '#F5F2EB' }}>
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
