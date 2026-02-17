import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog";
import {
  Camera, ArrowLeft, Upload, Trash2, Copy, ExternalLink, Image, Video,
  Calendar, Users, Settings, Star, Download, Check, X
} from "lucide-react";
import { getGallery, updateGallery, uploadPhotos, deletePhoto, mediaUrl } from "@/lib/api";

export default function AdminGalleryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [gallery, setGallery] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [selectedPhotos, setSelectedPhotos] = useState(new Set());

  const loadGallery = useCallback(async () => {
    try {
      const res = await getGallery(id);
      setGallery(res.data);
      setPhotos(res.data.photos || []);
      setEditForm({
        title: res.data.title,
        couple_names: res.data.couple_names,
        wedding_date: res.data.wedding_date,
        description: res.data.description || "",
        is_active: res.data.is_active,
        password: ""
      });
    } catch {
      toast.error("Gallery not found");
      navigate("/admin/dashboard");
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (!token) { navigate("/admin"); return; }
    loadGallery();
  }, [navigate, loadGallery]);

  const handleUpload = async (fileList) => {
    if (!fileList?.length) return;
    const files = Array.from(fileList);
    setUploading(true);
    setUploadProgress(0);
    try {
      await uploadPhotos(id, files, (e) => {
        setUploadProgress(Math.round((e.loaded * 100) / e.total));
      });
      toast.success(`${files.length} file(s) uploaded`);
      loadGallery();
    } catch (err) {
      toast.error("Upload failed");
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

  const handleDeletePhoto = async (photoId) => {
    try {
      await deletePhoto(id, photoId);
      toast.success("Photo deleted");
      loadGallery();
    } catch {
      toast.error("Failed to delete");
    }
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedPhotos.size} selected photos?`)) return;
    for (const photoId of selectedPhotos) {
      try { await deletePhoto(id, photoId); } catch {}
    }
    toast.success(`${selectedPhotos.size} photos deleted`);
    setSelectedPhotos(new Set());
    loadGallery();
  };

  const setCoverPhoto = async (photoId) => {
    try {
      await updateGallery(id, { cover_photo_id: photoId });
      toast.success("Cover photo updated");
      loadGallery();
    } catch {
      toast.error("Failed to update cover");
    }
  };

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updates = { ...editForm };
      if (!updates.password) delete updates.password;
      await updateGallery(id, updates);
      toast.success("Gallery updated");
      setShowSettings(false);
      loadGallery();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  const copyLink = () => {
    const url = `${window.location.origin}/gallery/${gallery.slug}`;
    navigator.clipboard.writeText(url);
    toast.success("Gallery link copied");
  };

  const toggleSelect = (photoId) => {
    setSelectedPhotos(prev => {
      const next = new Set(prev);
      if (next.has(photoId)) next.delete(photoId);
      else next.add(photoId);
      return next;
    });
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!gallery) return null;

  const photoItems = photos.filter(p => p.file_type === 'photo');
  const videoItems = photos.filter(p => p.file_type === 'video');

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Header */}
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              data-testid="back-to-dashboard"
              onClick={() => navigate("/admin/dashboard")}
              className="text-[#57534E] hover:text-[#1C1917]"
              style={{ transition: 'color 0.2s ease' }}
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
                {gallery.title}
              </h1>
              <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                {gallery.couple_names} &middot; {gallery.wedding_date}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              data-testid="copy-gallery-link"
              variant="ghost"
              onClick={copyLink}
              className="text-[#57534E] rounded-sm gap-2 text-xs"
            >
              <Copy className="w-3.5 h-3.5" /> Copy Link
            </Button>
            <Button
              data-testid="gallery-settings-btn"
              variant="ghost"
              onClick={() => setShowSettings(true)}
              className="text-[#57534E] rounded-sm"
            >
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-8">
        {/* Stats bar */}
        <div className="flex items-center gap-6 mb-8 text-sm" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
          <span className="flex items-center gap-1.5"><Image className="w-4 h-4 text-[#D4AF37]" /> {photoItems.length} Photos</span>
          <span className="flex items-center gap-1.5"><Video className="w-4 h-4 text-[#D4AF37]" /> {videoItems.length} Videos</span>
          <span className={`px-2 py-0.5 text-xs tracking-wider uppercase font-bold ${gallery.is_active ? 'text-[#3F6212] bg-[#3F6212]/10' : 'text-[#9F1239] bg-[#9F1239]/10'}`}>
            {gallery.is_active ? 'Active' : 'Inactive'}
          </span>
          {selectedPhotos.size > 0 && (
            <Button
              data-testid="bulk-delete-btn"
              onClick={handleBulkDelete}
              variant="ghost"
              className="ml-auto text-[#9F1239] gap-1 text-xs"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete {selectedPhotos.size} selected
            </Button>
          )}
        </div>

        {/* Upload Zone */}
        <div
          className={`upload-zone mb-8 p-8 flex flex-col items-center justify-center text-center cursor-pointer ${dragOver ? 'drag-over' : ''}`}
          style={{ minHeight: '140px' }}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          data-testid="upload-zone"
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,video/*"
            className="hidden"
            onChange={e => handleUpload(e.target.files)}
            data-testid="file-input"
          />
          {uploading ? (
            <div className="w-full max-w-xs">
              <p className="text-sm mb-3" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>Uploading... {uploadProgress}%</p>
              <Progress value={uploadProgress} className="h-1.5" />
            </div>
          ) : (
            <>
              <Upload className="w-8 h-8 mb-3 text-[#A8A29E]" strokeWidth={1.5} />
              <p className="text-sm font-medium mb-1" style={{ fontFamily: 'Manrope, sans-serif' }}>
                Drop photos & videos here or click to browse
              </p>
              <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                JPG, PNG, GIF, WebP, MP4, MOV up to 100MB each
              </p>
            </>
          )}
        </div>

        {/* Photos Grid */}
        {photos.length === 0 ? (
          <div className="text-center py-20">
            <Camera className="w-16 h-16 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
            <p className="text-2xl mb-2" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No photos yet</p>
            <p className="text-sm" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>Upload photos to start building this gallery</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            <AnimatePresence>
              {photos.map((photo, i) => (
                <motion.div
                  key={photo.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.02 }}
                  className="photo-card relative group aspect-square"
                  data-testid={`photo-${photo.id}`}
                >
                  {photo.file_type === 'photo' && photo.thumbnail_path ? (
                    <img
                      src={mediaUrl(gallery.id, photo.thumbnail_path)}
                      alt={photo.filename}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center" style={{ backgroundColor: '#F5F2EB' }}>
                      <Video className="w-8 h-8 text-[#A8A29E]" />
                    </div>
                  )}

                  {/* Selection checkbox */}
                  <button
                    className="absolute top-2 left-2 w-6 h-6 rounded-sm border flex items-center justify-center opacity-0 group-hover:opacity-100"
                    style={{
                      transition: 'opacity 0.2s ease',
                      backgroundColor: selectedPhotos.has(photo.id) ? '#1C1917' : 'rgba(255,255,255,0.9)',
                      borderColor: selectedPhotos.has(photo.id) ? '#1C1917' : '#D4D4D8'
                    }}
                    onClick={() => toggleSelect(photo.id)}
                  >
                    {selectedPhotos.has(photo.id) && <Check className="w-3.5 h-3.5 text-white" />}
                  </button>

                  {/* Hover overlay */}
                  <div className="photo-overlay" />
                  <div className="photo-actions flex items-center justify-between">
                    <button
                      data-testid={`set-cover-${photo.id}`}
                      onClick={() => setCoverPhoto(photo.id)}
                      className="w-7 h-7 rounded-full flex items-center justify-center"
                      style={{ backgroundColor: gallery.cover_photo_id === photo.id ? '#D4AF37' : 'rgba(255,255,255,0.9)' }}
                      title="Set as cover"
                    >
                      <Star className="w-3.5 h-3.5" style={{ color: gallery.cover_photo_id === photo.id ? '#fff' : '#1C1917' }} />
                    </button>
                    <button
                      data-testid={`delete-photo-${photo.id}`}
                      onClick={() => handleDeletePhoto(photo.id)}
                      className="w-7 h-7 rounded-full flex items-center justify-center"
                      style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
                    >
                      <Trash2 className="w-3.5 h-3.5 text-[#9F1239]" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Settings Dialog */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-lg" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Gallery Settings
            </DialogTitle>
            <DialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Update gallery details and access settings
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSaveSettings} className="space-y-5 mt-2">
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Gallery Title</Label>
              <Input
                data-testid="edit-gallery-title"
                value={editForm.title || ""}
                onChange={e => setEditForm(f => ({...f, title: e.target.value}))}
                className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Couple Names</Label>
              <Input
                data-testid="edit-couple-names"
                value={editForm.couple_names || ""}
                onChange={e => setEditForm(f => ({...f, couple_names: e.target.value}))}
                className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Wedding Date</Label>
                <Input
                  data-testid="edit-wedding-date"
                  type="date"
                  value={editForm.wedding_date || ""}
                  onChange={e => setEditForm(f => ({...f, wedding_date: e.target.value}))}
                  className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>New Password</Label>
                <Input
                  data-testid="edit-gallery-password"
                  type="text"
                  value={editForm.password || ""}
                  onChange={e => setEditForm(f => ({...f, password: e.target.value}))}
                  placeholder="Leave empty to keep"
                  className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Description</Label>
              <Input
                data-testid="edit-gallery-desc"
                value={editForm.description || ""}
                onChange={e => setEditForm(f => ({...f, description: e.target.value}))}
                className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
              />
            </div>
            <div className="flex items-center gap-3 py-2">
              <Switch
                data-testid="edit-gallery-active"
                checked={editForm.is_active}
                onCheckedChange={v => setEditForm(f => ({...f, is_active: v}))}
              />
              <Label className="text-sm" style={{ color: '#57534E' }}>Gallery active</Label>
            </div>
            <DialogFooter>
              <Button
                data-testid="save-settings-btn"
                type="submit"
                disabled={saving}
                className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-5 text-xs tracking-[0.15em] uppercase font-bold"
              >
                {saving ? "Saving..." : "Save Changes"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
