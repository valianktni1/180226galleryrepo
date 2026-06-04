import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getShareFiles, previewUrl } from "@/lib/api";
import Slideshow from "@/pages/Slideshow";

export default function SlideshowDirect() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [photos, setPhotos] = useState(null);
  const [galleryId, setGalleryId] = useState(null);
  const [coupleName, setCoupleName] = useState("");

  useEffect(() => {
    const jwt = localStorage.getItem("share_token");
    const storedToken = localStorage.getItem("share_url_token");
    if (!jwt || storedToken !== token) {
      navigate(`/s/${token}?next=slideshow`);
      return;
    }

    getShareFiles(token).then(res => {
      const galleryName = res.data.gallery_name || "";
      const name = galleryName.replace(/\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$/, '').trim();
      setCoupleName(name || galleryName);
      setGalleryId(res.data.gallery_id);

      // Find Wedding Images subfolder
      const weddingSf = (res.data.subfolders || []).find(
        sf => sf.name.toLowerCase().includes('wedding') && sf.name.toLowerCase().includes('image')
      );
      if (weddingSf) {
        const photoFiles = weddingSf.files.filter(f => f.file_type === 'photo' && (f.has_preview || f.has_thumb));
        setPhotos(photoFiles);
      } else {
        setPhotos([]);
      }
    }).catch(() => {
      localStorage.removeItem("share_token");
      navigate(`/s/${token}?next=slideshow`);
    });
  }, [token, navigate]);

  const handleClose = useCallback(() => {
    navigate(`/s/${token}/view`);
  }, [token, navigate]);

  // Loading
  if (photos === null) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center">
        <p className="text-white/30 text-sm tracking-wider" style={{ fontFamily: 'Manrope, sans-serif' }}>Loading...</p>
      </div>
    );
  }

  // No photos
  if (photos.length === 0) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center">
        <div className="text-center">
          <p className="text-white/50 text-sm mb-4" style={{ fontFamily: 'Manrope, sans-serif' }}>No wedding images available</p>
          <button onClick={handleClose} className="text-[#D4AF37] text-sm underline cursor-pointer" style={{ fontFamily: 'Manrope, sans-serif' }}>
            Back to gallery
          </button>
        </div>
      </div>
    );
  }

  return (
    <Slideshow
      photos={photos}
      galleryId={galleryId}
      coupleName={coupleName}
      onClose={handleClose}
    />
  );
}
