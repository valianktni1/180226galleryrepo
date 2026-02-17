import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import {
  Camera, Plus, LogOut, Image, Video, Calendar, Users, Trash2, Edit, ExternalLink, Copy, Search
} from "lucide-react";
import { getGalleries, createGallery, deleteGallery, mediaUrl } from "@/lib/api";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [galleries, setGalleries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: "", couple_names: "", wedding_date: "", password: "", description: "", is_active: true
  });

  const loadGalleries = useCallback(async () => {
    try {
      const res = await getGalleries();
      setGalleries(res.data);
    } catch {
      toast.error("Failed to load galleries");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (!token) { navigate("/admin"); return; }
    loadGalleries();
  }, [navigate, loadGalleries]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await createGallery(form);
      toast.success("Gallery created");
      setShowCreate(false);
      setForm({ title: "", couple_names: "", wedding_date: "", password: "", description: "", is_active: true });
      navigate(`/admin/gallery/${res.data.id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create gallery");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id, title) => {
    if (!window.confirm(`Delete "${title}" and all its photos?`)) return;
    try {
      await deleteGallery(id);
      toast.success("Gallery deleted");
      loadGalleries();
    } catch {
      toast.error("Failed to delete");
    }
  };

  const copyLink = (slug) => {
    const url = `${window.location.origin}/gallery/${slug}`;
    navigator.clipboard.writeText(url);
    toast.success("Gallery link copied");
  };

  const logout = () => {
    localStorage.removeItem("admin_token");
    navigate("/admin");
  };

  const filtered = galleries.filter(g =>
    g.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    g.couple_names.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalPhotos = galleries.reduce((s, g) => s + (g.photo_count || 0), 0);
  const totalVideos = galleries.reduce((s, g) => s + (g.video_count || 0), 0);
  const activeGalleries = galleries.filter(g => g.is_active).length;

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Header */}
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Camera className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
            <span className="text-xs tracking-[0.2em] uppercase font-bold" style={{ fontFamily: 'Manrope, sans-serif', color: '#1C1917' }}>
              Weddings By Mark
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Button
              data-testid="create-gallery-btn"
              onClick={() => setShowCreate(true)}
              className="bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-6 py-2 text-xs tracking-[0.15em] uppercase font-bold gap-2"
              style={{ fontFamily: 'Manrope, sans-serif' }}
            >
              <Plus className="w-4 h-4" /> New Gallery
            </Button>
            <Button
              data-testid="logout-btn"
              variant="ghost"
              onClick={logout}
              className="text-[#57534E] hover:text-[#1C1917] rounded-sm px-3"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-10">
        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-12"
        >
          {[
            { label: "Galleries", value: galleries.length, icon: Users },
            { label: "Active", value: activeGalleries, icon: Calendar },
            { label: "Photos", value: totalPhotos, icon: Image },
            { label: "Videos", value: totalVideos, icon: Video },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="p-6 border" style={{ borderColor: '#F5F2EB', backgroundColor: '#FDFCF8' }}>
              <div className="flex items-center gap-2 mb-2">
                <Icon className="w-4 h-4 text-[#D4AF37]" strokeWidth={1.5} />
                <span className="text-xs tracking-[0.15em] uppercase font-semibold" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                  {label}
                </span>
              </div>
              <span className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>
                {value}
              </span>
            </div>
          ))}
        </motion.div>

        {/* Search */}
        <div className="flex items-center gap-4 mb-8">
          <h2 className="text-3xl md:text-4xl font-medium flex-1" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
            Galleries
          </h2>
          <div className="relative w-64">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-[#A8A29E]" />
            <Input
              data-testid="gallery-search"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search galleries..."
              className="pl-10 border-[#F5F2EB] bg-white/50 rounded-sm text-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
              style={{ fontFamily: 'Manrope, sans-serif' }}
            />
          </div>
        </div>

        {/* Gallery Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1,2,3].map(i => (
              <div key={i} className="h-72 animate-pulse" style={{ backgroundColor: '#F5F2EB' }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-24">
            <Camera className="w-12 h-12 mx-auto mb-4 text-[#A8A29E]" strokeWidth={1} />
            <p className="text-lg mb-2" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>
              {galleries.length === 0 ? "No galleries yet" : "No results found"}
            </p>
            <p className="text-sm mb-6" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
              {galleries.length === 0 ? "Create your first gallery to get started" : "Try a different search"}
            </p>
            {galleries.length === 0 && (
              <Button
                onClick={() => setShowCreate(true)}
                className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-8 py-3 text-xs tracking-[0.15em] uppercase font-bold"
              >
                Create Gallery
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <AnimatePresence>
              {filtered.map((g, i) => (
                <motion.div
                  key={g.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="group border overflow-hidden cursor-pointer"
                  style={{ borderColor: '#F5F2EB' }}
                  onClick={() => navigate(`/admin/gallery/${g.id}`)}
                  data-testid={`gallery-card-${g.id}`}
                >
                  <div className="aspect-[4/3] relative overflow-hidden" style={{ backgroundColor: '#F5F2EB' }}>
                    {g.cover_photo_id ? (
                      <img
                        src={mediaUrl(g.id, `previews/${g.cover_photo_id}.jpg`)}
                        alt={g.title}
                        className="w-full h-full object-cover"
                        style={{ transition: 'transform 0.7s cubic-bezier(0.33, 1, 0.68, 1)' }}
                        onMouseOver={e => e.target.style.transform = 'scale(1.03)'}
                        onMouseOut={e => e.target.style.transform = 'scale(1)'}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Camera className="w-12 h-12 text-[#D4D4D8]" strokeWidth={1} />
                      </div>
                    )}
                    {!g.is_active && (
                      <div className="absolute top-3 left-3 px-3 py-1 text-xs tracking-wider uppercase font-bold" style={{ backgroundColor: 'rgba(0,0,0,0.7)', color: '#FDFCF8', fontFamily: 'Manrope, sans-serif' }}>
                        Inactive
                      </div>
                    )}
                    <div className="absolute top-3 right-3 flex gap-1.5 opacity-0 group-hover:opacity-100" style={{ transition: 'opacity 0.3s ease' }}>
                      <button
                        data-testid={`copy-link-${g.id}`}
                        onClick={e => { e.stopPropagation(); copyLink(g.slug); }}
                        className="w-8 h-8 rounded-full flex items-center justify-center"
                        style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
                      >
                        <Copy className="w-3.5 h-3.5 text-[#1C1917]" />
                      </button>
                      <button
                        data-testid={`delete-gallery-${g.id}`}
                        onClick={e => { e.stopPropagation(); handleDelete(g.id, g.title); }}
                        className="w-8 h-8 rounded-full flex items-center justify-center"
                        style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
                      >
                        <Trash2 className="w-3.5 h-3.5 text-[#9F1239]" />
                      </button>
                    </div>
                  </div>
                  <div className="p-5">
                    <h3 className="text-xl mb-1 font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
                      {g.title}
                    </h3>
                    <p className="text-sm mb-3" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
                      {g.couple_names}
                    </p>
                    <div className="flex items-center gap-4 text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                      <span className="flex items-center gap-1">
                        <Image className="w-3.5 h-3.5" /> {g.photo_count || 0}
                      </span>
                      <span className="flex items-center gap-1">
                        <Video className="w-3.5 h-3.5" /> {g.video_count || 0}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" /> {g.wedding_date}
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Create Gallery Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-lg" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              New Gallery
            </DialogTitle>
            <DialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Create a new photo gallery for a wedding couple
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5 mt-2">
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Gallery Title</Label>
              <Input
                data-testid="gallery-title-input"
                value={form.title}
                onChange={e => setForm(f => ({...f, title: e.target.value}))}
                placeholder="e.g. Sarah & James"
                className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Couple Names</Label>
              <Input
                data-testid="gallery-couple-input"
                value={form.couple_names}
                onChange={e => setForm(f => ({...f, couple_names: e.target.value}))}
                placeholder="Sarah Thompson & James Williams"
                className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Wedding Date</Label>
                <Input
                  data-testid="gallery-date-input"
                  type="date"
                  value={form.wedding_date}
                  onChange={e => setForm(f => ({...f, wedding_date: e.target.value}))}
                  className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Gallery Password</Label>
                <Input
                  data-testid="gallery-password-input"
                  type="text"
                  value={form.password}
                  onChange={e => setForm(f => ({...f, password: e.target.value}))}
                  placeholder="For couple access"
                  className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
                  required
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Description (optional)</Label>
              <Input
                data-testid="gallery-desc-input"
                value={form.description}
                onChange={e => setForm(f => ({...f, description: e.target.value}))}
                placeholder="A brief note for the couple"
                className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]"
              />
            </div>
            <div className="flex items-center gap-3 py-2">
              <Switch
                data-testid="gallery-active-switch"
                checked={form.is_active}
                onCheckedChange={v => setForm(f => ({...f, is_active: v}))}
              />
              <Label className="text-sm" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>Gallery active (visible to couple)</Label>
            </div>
            <DialogFooter>
              <Button
                data-testid="create-gallery-submit"
                type="submit"
                disabled={creating}
                className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-5 text-xs tracking-[0.15em] uppercase font-bold"
              >
                {creating ? "Creating..." : "Create Gallery"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
