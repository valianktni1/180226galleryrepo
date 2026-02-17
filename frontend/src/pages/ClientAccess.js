import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Camera, Lock, Heart } from "lucide-react";
import { getGalleryInfo, accessGallery } from "@/lib/api";

export default function ClientAccess() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [galleryInfo, setGalleryInfo] = useState(null);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("client_token");
    const storedSlug = localStorage.getItem("client_gallery_slug");
    if (token && storedSlug === slug) {
      navigate(`/gallery/${slug}/view`);
      return;
    }
    getGalleryInfo(slug)
      .then(r => setGalleryInfo(r.data))
      .catch(() => setNotFound(true));
  }, [slug, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await accessGallery(slug, password);
      localStorage.setItem("client_token", res.data.token);
      localStorage.setItem("client_gallery_slug", slug);
      navigate(`/gallery/${slug}/view`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Incorrect password");
    } finally {
      setLoading(false);
    }
  };

  if (notFound) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8" style={{ backgroundColor: '#FDFCF8' }}>
        <div className="text-center">
          <Camera className="w-16 h-16 mx-auto mb-6 text-[#D4D4D8]" strokeWidth={1} />
          <h1 className="text-4xl mb-3 font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
            Gallery Not Found
          </h1>
          <p className="text-base" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
            This gallery link may have expired or been removed.
          </p>
        </div>
      </div>
    );
  }

  if (!galleryInfo) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

  return (
    <div className="min-h-screen flex relative noise-bg" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Background image */}
      {galleryInfo.cover_url && (
        <div className="hidden lg:block lg:w-1/2 relative overflow-hidden">
          <img
            src={`${BACKEND_URL}${galleryInfo.cover_url}`}
            alt="Gallery cover"
            className="absolute inset-0 w-full h-full object-cover"
          />
          <div className="absolute inset-0" style={{ background: 'linear-gradient(to right, transparent 60%, #FDFCF8 100%)' }} />
        </div>
      )}

      {/* Access form */}
      <div className="flex-1 flex items-center justify-center p-8 lg:p-16">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          <div className="flex items-center gap-2 mb-12">
            <Heart className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
            <span className="text-xs tracking-[0.2em] uppercase font-semibold" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
              Private Gallery
            </span>
          </div>

          <h1
            className="text-4xl md:text-6xl mb-3 font-light italic leading-tight"
            style={{ fontFamily: 'Cormorant Garamond, serif' }}
          >
            {galleryInfo.title}
          </h1>
          <p className="text-lg mb-2" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
            {galleryInfo.couple_names}
          </p>
          {galleryInfo.description && (
            <p className="text-sm mb-8" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
              {galleryInfo.description}
            </p>
          )}
          <div className="flex items-center gap-4 mb-10 text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
            <span>{galleryInfo.photo_count} photos</span>
            {galleryInfo.video_count > 0 && <span>{galleryInfo.video_count} videos</span>}
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="relative">
              <Lock className="absolute left-0 top-3.5 w-4 h-4 text-[#A8A29E]" />
              <Input
                data-testid="gallery-access-password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter gallery password"
                className="border-0 border-b border-[#D4D4D8] bg-transparent rounded-none pl-6 py-3 focus-visible:ring-0 focus-visible:border-[#1C1917] placeholder:text-[#A8A29E] text-base"
                style={{ fontFamily: 'Manrope, sans-serif' }}
                required
              />
            </div>
            <Button
              data-testid="gallery-access-submit"
              type="submit"
              disabled={loading}
              className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-6 text-xs tracking-[0.2em] uppercase font-bold"
              style={{ fontFamily: 'Manrope, sans-serif' }}
            >
              {loading ? "Accessing..." : "View Gallery"}
            </Button>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
