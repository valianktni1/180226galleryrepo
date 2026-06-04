import { useState, useEffect } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Camera, Lock, Heart, Upload, Clock } from "lucide-react";
import { getShareInfo, accessShare, openAccessShare, getErrorMessage } from "@/lib/api";

export default function ShareAccess() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const nextDest = searchParams.get('next');

  const redirectPath = nextDest === 'slideshow' ? `/s/${token}/slideshow` : `/s/${token}/view`;
  const [shareInfo, setShareInfo] = useState(null);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    const existing = localStorage.getItem("share_token");
    const existingShareToken = localStorage.getItem("share_url_token");
    if (existing && existingShareToken === token) {
      navigate(redirectPath);
      return;
    }
    getShareInfo(token)
      .then(r => {
        setShareInfo(r.data);
        // Store guest_upload_mode for ShareView to use
        if (r.data.guest_upload_mode) {
          localStorage.setItem(`guest_upload_mode_${token}`, 'true');
        } else {
          localStorage.removeItem(`guest_upload_mode_${token}`);
        }
        // Store allow_all_file_types for upload views
        if (r.data.allow_all_file_types) {
          localStorage.setItem(`allow_all_file_types_${token}`, 'true');
        } else {
          localStorage.removeItem(`allow_all_file_types_${token}`);
        }
        // Store gallery name for guest upload view
        if (r.data.gallery_name) {
          localStorage.setItem(`gallery_name_${token}`, r.data.gallery_name);
        }
        // Auto-access if no password required
        if (!r.data.has_password) {
          openAccessShare(token).then(res => {
            localStorage.setItem("share_token", res.data.jwt);
            localStorage.setItem("share_url_token", token);
            // Store viewer_id for persistent favourites
            if (res.data.viewer_id) {
              localStorage.setItem(`viewer_id_${token}`, res.data.viewer_id);
            }
            navigate(redirectPath);
          }).catch((err) => {
            if (err.response?.status === 410) {
              setExpired(true);
            }
          });
        }
      })
      .catch((err) => {
        if (err.response?.status === 410) {
          setExpired(true);
        } else {
          setNotFound(true);
        }
      });
  }, [token, navigate, redirectPath]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await accessShare(token, password);
      localStorage.setItem("share_token", res.data.jwt);
      localStorage.setItem("share_url_token", token);
      // Store viewer_id for persistent favourites
      if (res.data.viewer_id) {
        localStorage.setItem(`viewer_id_${token}`, res.data.viewer_id);
      }
      navigate(redirectPath);
    } catch (err) {
      if (err.response?.status === 410) {
        setExpired(true);
      } else {
        toast.error(getErrorMessage(err, "Incorrect password"));
      }
    } finally {
      setLoading(false);
    }
  };

  if (expired) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8" style={{ backgroundColor: '#FDFCF8' }}>
        <div className="text-center">
          <Clock className="w-16 h-16 mx-auto mb-6 text-[#D4AF37]" strokeWidth={1} />
          <h1 className="text-4xl mb-3 font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Link Expired</h1>
          <p className="text-base" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
            This share link has expired. Please contact the photographer for a new link.
          </p>
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8" style={{ backgroundColor: '#FDFCF8' }}>
        <div className="text-center">
          <Camera className="w-16 h-16 mx-auto mb-6 text-[#D4D4D8]" strokeWidth={1} />
          <h1 className="text-4xl mb-3 font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Link Not Found</h1>
          <p className="text-base" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>This share link may have expired or been removed.</p>
        </div>
      </div>
    );
  }

  if (!shareInfo || !shareInfo.has_password) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

  return (
    <div className="min-h-screen flex relative noise-bg" style={{ backgroundColor: '#FDFCF8' }}>
      {shareInfo.cover_url && (
        <div className="hidden lg:block lg:w-1/2 relative overflow-hidden">
          <img src={`${BACKEND_URL}${shareInfo.cover_url}`} alt="Gallery cover" className="absolute inset-0 w-full h-full object-cover" />
          <div className="absolute inset-0" style={{ background: 'linear-gradient(to right, transparent 60%, #FDFCF8 100%)' }} />
        </div>
      )}
      <div className="flex-1 flex items-center justify-center p-8 lg:p-16">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="w-full max-w-md">
          <div className="flex items-center gap-2 mb-12">
            {shareInfo.allow_uploads ? (
              <Upload className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
            ) : (
              <Heart className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
            )}
            <span className="text-xs tracking-[0.2em] uppercase font-semibold" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
              {shareInfo.allow_uploads ? "Guest Upload" : "Private Gallery"}
            </span>
          </div>

          <h1 className="text-4xl md:text-6xl mb-3 font-light italic leading-tight" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
            {shareInfo.label || shareInfo.gallery_name}
          </h1>
          {shareInfo.subfolder && (
            <p className="text-sm mb-2" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>{shareInfo.subfolder}</p>
          )}
          <div className="flex items-center gap-4 mb-10 text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
            <span>{shareInfo.file_count} files</span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="relative">
              <Lock className="absolute left-0 top-3.5 w-4 h-4 text-[#A8A29E]" />
              <Input data-testid="share-access-password" type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Enter password" className="border-0 border-b border-[#D4D4D8] bg-transparent rounded-none pl-6 py-3 focus-visible:ring-0 focus-visible:border-[#1C1917] placeholder:text-[#A8A29E] text-base"
                style={{ fontFamily: 'Manrope, sans-serif' }} required />
            </div>
            <Button data-testid="share-access-submit" type="submit" disabled={loading}
              className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-6 text-xs tracking-[0.2em] uppercase font-bold" style={{ fontFamily: 'Manrope, sans-serif' }}>
              {loading ? "Accessing..." : "View Gallery"}
            </Button>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
