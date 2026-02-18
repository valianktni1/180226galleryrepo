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
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import {
  Camera, Plus, LogOut, FolderOpen, Share2, Trash2, Search, Copy, Layout, X, Settings, ArrowUpDown
} from "lucide-react";
import {
  listGalleries, createGallery, deleteGallery, getTemplates, createTemplate, deleteTemplate, thumbUrl
} from "@/lib/api";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [galleries, setGalleries] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("date_desc");
  const [showCreate, setShowCreate] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ folder_name: "", template_id: "" });
  const [newTemplate, setNewTemplate] = useState({ name: "", subfolders: "" });

  const load = useCallback(async () => {
    try {
      const [gRes, tRes] = await Promise.all([listGalleries(sortBy), getTemplates()]);
      setGalleries(gRes.data);
      setTemplates(tRes.data);
    } catch {
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [sortBy]);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { navigate("/admin"); return; }
    load();
  }, [navigate, load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.folder_name.trim()) { toast.error("Enter a folder name"); return; }
    setCreating(true);
    try {
      const res = await createGallery({
        folder_name: form.folder_name.trim(),
        template_id: form.template_id || null
      });
      toast.success("Gallery created");
      setShowCreate(false);
      setForm({ folder_name: "", template_id: "" });
      navigate(`/admin/gallery/${res.data.id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete "${name}" and ALL its files permanently?`)) return;
    try {
      await deleteGallery(id);
      toast.success("Gallery deleted");
      load();
    } catch { toast.error("Failed to delete"); }
  };

  const handleCreateTemplate = async () => {
    if (!newTemplate.name.trim()) return;
    const subs = newTemplate.subfolders
      ? newTemplate.subfolders.split(",").map(s => s.trim()).filter(Boolean)
      : ["Wedding Images", "Video", "SelfieBooth", "Album Favourites", "Guest Uploads"];
    try {
      await createTemplate({ name: newTemplate.name.trim(), subfolders: subs });
      toast.success("Template created");
      setNewTemplate({ name: "", subfolders: "" });
      const tRes = await getTemplates();
      setTemplates(tRes.data);
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const handleDeleteTemplate = async (id) => {
    try {
      await deleteTemplate(id);
      toast.success("Template deleted");
      const tRes = await getTemplates();
      setTemplates(tRes.data);
    } catch (err) { toast.error(err.response?.data?.detail || "Cannot delete"); }
  };

  const filtered = galleries.filter(g =>
    g.folder_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalFiles = galleries.reduce((s, g) => {
    const counts = g.file_counts || {};
    return s + Object.values(counts).reduce((a, b) => a + b, 0);
  }, 0);

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Camera className="w-5 h-5 text-[#D4AF37]" strokeWidth={1.5} />
            <span className="text-xs tracking-[0.2em] uppercase font-bold" style={{ fontFamily: 'Manrope, sans-serif' }}>Weddings By Mark</span>
          </div>
          <div className="flex items-center gap-2">
            <Button data-testid="manage-templates-btn" variant="ghost" onClick={() => setShowTemplates(true)} className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Layout className="w-4 h-4" /> Templates
            </Button>
            <Button data-testid="settings-btn" variant="ghost" onClick={() => navigate("/admin/settings")} className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Settings className="w-4 h-4" /> Settings
            </Button>
            <Button data-testid="create-gallery-btn" onClick={() => setShowCreate(true)} className="bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-6 py-2 text-xs tracking-[0.15em] uppercase font-bold gap-2">
              <Plus className="w-4 h-4" /> New Gallery
            </Button>
            <Button data-testid="logout-btn" variant="ghost" onClick={() => { localStorage.removeItem("admin_token"); navigate("/admin"); }} className="text-[#57534E] rounded-sm px-3">
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-10">
        {/* Stats */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-3 gap-6 mb-12">
          {[
            { label: "Galleries", value: galleries.length },
            { label: "Total Files", value: totalFiles },
            { label: "Templates", value: templates.length },
          ].map(({ label, value }) => (
            <div key={label} className="p-6 border" style={{ borderColor: '#F5F2EB' }}>
              <span className="text-xs tracking-[0.15em] uppercase font-semibold block mb-1" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>{label}</span>
              <span className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>{value}</span>
            </div>
          ))}
        </motion.div>

        {/* Search */}
        <div className="flex items-center gap-4 mb-8">
          <h2 className="text-3xl md:text-4xl font-medium flex-1" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Couple Folders</h2>
          <div className="relative w-64">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-[#A8A29E]" />
            <Input data-testid="gallery-search" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search..." className="pl-10 border-[#F5F2EB] bg-white/50 rounded-sm text-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]" />
          </div>
        </div>

        {/* Gallery Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[1,2,3,4].map(i => <div key={i} className="h-64 animate-pulse" style={{ backgroundColor: '#F5F2EB' }} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-24">
            <FolderOpen className="w-12 h-12 mx-auto mb-4 text-[#D4D4D8]" strokeWidth={1} />
            <p className="text-lg mb-2" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>
              {galleries.length === 0 ? "No galleries yet" : "No results found"}
            </p>
            {galleries.length === 0 && (
              <Button onClick={() => setShowCreate(true)} className="mt-4 bg-[#1C1917] text-[#FDFCF8] rounded-sm px-8 py-3 text-xs tracking-[0.15em] uppercase font-bold">
                Create First Gallery
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            <AnimatePresence>
              {filtered.map((g, i) => {
                const fileCounts = g.file_counts || {};
                const total = Object.values(fileCounts).reduce((a, b) => a + b, 0);
                return (
                  <motion.div key={g.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                    className="group border overflow-hidden cursor-pointer" style={{ borderColor: '#F5F2EB' }}
                    onClick={() => navigate(`/admin/gallery/${g.id}`)} data-testid={`gallery-card-${g.id}`}
                  >
                    <div className="aspect-[4/3] relative overflow-hidden" style={{ backgroundColor: '#F5F2EB' }}>
                      {g.cover_thumb ? (
                        <img src={`${process.env.REACT_APP_BACKEND_URL}${g.cover_thumb}`} alt={g.folder_name}
                          className="w-full h-full object-cover" style={{ transition: 'transform 0.7s cubic-bezier(0.33,1,0.68,1)' }}
                          onMouseOver={e => e.target.style.transform = 'scale(1.03)'} onMouseOut={e => e.target.style.transform = 'scale(1)'}
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <FolderOpen className="w-12 h-12 text-[#D4D4D8]" strokeWidth={1} />
                        </div>
                      )}
                      <div className="absolute top-3 right-3 flex gap-1.5 opacity-0 group-hover:opacity-100" style={{ transition: 'opacity 0.3s ease' }}>
                        <button data-testid={`delete-gallery-${g.id}`}
                          onClick={e => { e.stopPropagation(); handleDelete(g.id, g.folder_name); }}
                          className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}>
                          <Trash2 className="w-3.5 h-3.5 text-[#9F1239]" />
                        </button>
                      </div>
                    </div>
                    <div className="p-4">
                      <h3 className="text-lg mb-1 font-medium truncate" style={{ fontFamily: 'Cormorant Garamond, serif' }}>{g.folder_name}</h3>
                      <div className="flex items-center gap-3 text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                        <span>{total} files</span>
                        <span>{g.share_count || 0} shares</span>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Create Gallery Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-lg" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>New Couple Folder</DialogTitle>
            <DialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Clone a template to create a folder structure for a couple
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-5 mt-2">
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Folder Name</Label>
              <Input data-testid="gallery-name-input" value={form.folder_name}
                onChange={e => setForm(f => ({...f, folder_name: e.target.value}))}
                placeholder="e.g. Gina & Mark 30.11.22" className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]" required />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Template</Label>
              <Select value={form.template_id} onValueChange={v => setForm(f => ({...f, template_id: v}))}>
                <SelectTrigger data-testid="template-select" className="border-[#D4D4D8] rounded-sm">
                  <SelectValue placeholder="Select template..." />
                </SelectTrigger>
                <SelectContent>
                  {templates.map(t => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name} ({t.subfolders.length} folders)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {form.template_id && (
                <p className="text-xs mt-1" style={{ color: '#A8A29E' }}>
                  Subfolders: {templates.find(t => t.id === form.template_id)?.subfolders.join(", ")}
                </p>
              )}
            </div>
            <DialogFooter>
              <Button data-testid="create-gallery-submit" type="submit" disabled={creating}
                className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-5 text-xs tracking-[0.15em] uppercase font-bold">
                {creating ? "Creating..." : "Create Gallery"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Templates Dialog */}
      <Dialog open={showTemplates} onOpenChange={setShowTemplates}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-xl" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Folder Templates</DialogTitle>
            <DialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Master folder structures that get cloned for each couple
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2 max-h-[400px] overflow-y-auto">
            {templates.map(t => (
              <div key={t.id} className="p-4 border flex items-start justify-between" style={{ borderColor: '#F5F2EB' }}>
                <div>
                  <p className="font-medium text-sm mb-1" style={{ fontFamily: 'Manrope, sans-serif' }}>
                    {t.name} {t.is_default && <span className="text-xs text-[#D4AF37] ml-1">(Default)</span>}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {t.subfolders.map(sf => (
                      <span key={sf} className="px-2 py-0.5 text-xs" style={{ backgroundColor: '#F5F2EB', color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>{sf}</span>
                    ))}
                  </div>
                </div>
                {!t.is_default && (
                  <button onClick={() => handleDeleteTemplate(t.id)} className="text-[#9F1239] hover:text-[#9F1239]/80 p-1">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="border-t pt-4 mt-4 space-y-3" style={{ borderColor: '#F5F2EB' }}>
            <p className="text-xs font-semibold tracking-wider uppercase" style={{ color: '#57534E' }}>Add New Template</p>
            <Input data-testid="template-name-input" value={newTemplate.name} onChange={e => setNewTemplate(t => ({...t, name: e.target.value}))}
              placeholder="Template name" className="border-[#D4D4D8] rounded-sm text-sm" />
            <Input data-testid="template-subfolders-input" value={newTemplate.subfolders} onChange={e => setNewTemplate(t => ({...t, subfolders: e.target.value}))}
              placeholder="Comma-separated subfolders (leave empty for default)" className="border-[#D4D4D8] rounded-sm text-sm" />
            <Button data-testid="add-template-btn" onClick={handleCreateTemplate} className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-6 py-2 text-xs tracking-wider uppercase font-bold">
              Add Template
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
