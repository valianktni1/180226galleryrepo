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
  Camera, Plus, LogOut, FolderOpen, Share2, Trash2, Search, Copy, Layout, X, Settings, ArrowUpDown, Eye, HardDrive, Download, Users, CheckCircle, Monitor, Smartphone, Tablet, Film, Heart, Image as ImageIcon, Mail, Send, Clock, AlertCircle, FolderHeart
} from "lucide-react";
import {
  listGalleries, createGallery, deleteGallery, getTemplates, createTemplate, deleteTemplate, thumbUrl, runBackup, getAllGalleriesStats, getLiveVisitors, getBroadcastPreview, sendBroadcastEmail, getDashboardStats
} from "@/lib/api";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [galleries, setGalleries] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [galleriesStats, setGalleriesStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("date_desc");
  const [showCreate, setShowCreate] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ folder_name: "", template_id: "", client_email: "" });
  const [newTemplate, setNewTemplate] = useState({ name: "", subfolders: "" });
  const [backingUp, setBackingUp] = useState(false);
  const [liveVisitors, setLiveVisitors] = useState([]);
  const [dashStats, setDashStats] = useState({ active_galleries: 0, expiring_soon: 0, downloads_this_week: 0, pending_albums: 0, storage_used_bytes: 0 });
  const [showBroadcast, setShowBroadcast] = useState(false);
  const [broadcastForm, setBroadcastForm] = useState({ subject: "", body: "" });
  const [broadcastRecipients, setBroadcastRecipients] = useState([]);
  const [sendingBroadcast, setSendingBroadcast] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, id: null, name: "", deleteBackup: false });

  const load = useCallback(async () => {
    try {
      const [gRes, tRes] = await Promise.all([listGalleries(sortBy), getTemplates()]);
      setGalleries(gRes.data);
      setTemplates(tRes.data);
      // Load stats separately (don't block main load)
      getAllGalleriesStats().then(statsRes => {
        setGalleriesStats(statsRes.data);
      }).catch(() => {});
      getDashboardStats().then(res => {
        setDashStats(res.data);
      }).catch(() => {});
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

  // Poll live visitors every 10 seconds
  useEffect(() => {
    const fetchVisitors = () => {
      getLiveVisitors().then(res => setLiveVisitors(res.data.visitors || [])).catch(() => {});
    };
    fetchVisitors();
    const interval = setInterval(fetchVisitors, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleBackup = async () => {
    setBackingUp(true);
    try {
      const res = await runBackup();
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Backup failed");
    } finally {
      setBackingUp(false);
    }
  };

  const handleOpenBroadcast = async () => {
    setShowBroadcast(true);
    try {
      const res = await getBroadcastPreview();
      setBroadcastRecipients(res.data.recipients || []);
    } catch {
      setBroadcastRecipients([]);
    }
  };

  const handleSendBroadcast = async () => {
    if (!broadcastForm.subject.trim() || !broadcastForm.body.trim()) {
      toast.error("Please fill in both subject and message");
      return;
    }
    if (broadcastRecipients.length === 0) {
      toast.error("No couples have email addresses set");
      return;
    }
    setSendingBroadcast(true);
    try {
      const res = await sendBroadcastEmail(broadcastForm);
      const { sent, failed } = res.data;
      if (failed > 0) {
        toast.success(`Email sent to ${sent} couple(s), ${failed} failed`);
      } else {
        toast.success(`Email sent to ${sent} couple(s) successfully!`);
      }
      setShowBroadcast(false);
      setBroadcastForm({ subject: "", body: "" });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send broadcast");
    } finally {
      setSendingBroadcast(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.folder_name.trim()) { toast.error("Enter a folder name"); return; }
    setCreating(true);
    try {
      const res = await createGallery({
        folder_name: form.folder_name.trim(),
        template_id: form.template_id || null,
        client_email: form.client_email.trim() || null
      });
      toast.success("Gallery created");
      setShowCreate(false);
      setForm({ folder_name: "", template_id: "", client_email: "" });
      navigate(`/admin/gallery/${res.data.id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id, name) => {
    setDeleteConfirm({ open: true, id, name, deleteBackup: false });
  };

  const confirmDelete = async () => {
    const { id, deleteBackup } = deleteConfirm;
    try {
      await deleteGallery(id, deleteBackup);
      toast.success(deleteBackup ? "Gallery and backup deleted" : "Gallery deleted");
      load();
    } catch { toast.error("Failed to delete"); }
    setDeleteConfirm({ open: false, id: null, name: "", deleteBackup: false });
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
            <img src="/logo.png" alt="Weddings By Mark" className="h-8" style={{ filter: 'invert(1)' }} />
          </div>
          <div className="flex items-center gap-2">
            <Button data-testid="backup-btn" variant="ghost" onClick={handleBackup} disabled={backingUp} className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <HardDrive className={`w-4 h-4 ${backingUp ? 'animate-pulse' : ''}`} /> {backingUp ? 'Backing up...' : 'Backup'}
            </Button>
            <Button data-testid="broadcast-email-btn" variant="ghost" onClick={handleOpenBroadcast} className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Mail className="w-4 h-4" /> Broadcast
            </Button>
            <Button data-testid="manage-templates-btn" variant="ghost" onClick={() => setShowTemplates(true)} className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Layout className="w-4 h-4" /> Templates
            </Button>
            <Button data-testid="activity-btn" variant="ghost" onClick={() => navigate("/admin/activity")} className="text-[#57534E] rounded-sm gap-2 text-xs tracking-wider">
              <Eye className="w-4 h-4" /> Activity
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
        {/* Dashboard Stats */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-5 gap-4 mb-10" data-testid="dashboard-stats">
          {[
            { label: "Active Galleries", value: dashStats.active_galleries, icon: Camera, color: '#D4AF37', bg: 'rgba(212,175,55,0.08)' },
            { label: "Expiring Soon", value: dashStats.expiring_soon, icon: AlertCircle, color: dashStats.expiring_soon > 0 ? '#F59E0B' : '#A8A29E', bg: dashStats.expiring_soon > 0 ? 'rgba(245,158,11,0.08)' : 'rgba(168,162,158,0.06)' },
            { label: "Downloads This Week", value: dashStats.downloads_this_week, icon: Download, color: '#22C55E', bg: 'rgba(34,197,94,0.08)' },
            { label: "Pending Albums", value: dashStats.pending_albums, icon: FolderHeart, color: dashStats.pending_albums > 0 ? '#EC4899' : '#A8A29E', bg: dashStats.pending_albums > 0 ? 'rgba(236,72,153,0.08)' : 'rgba(168,162,158,0.06)' },
            { label: "Storage Used", value: dashStats.storage_used_bytes >= 1099511627776 ? `${(dashStats.storage_used_bytes / 1099511627776).toFixed(2)} TB` : `${(dashStats.storage_used_bytes / 1073741824).toFixed(1)} GB`, icon: HardDrive, color: '#6366F1', bg: 'rgba(99,102,241,0.08)' },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <div key={label} className="p-5 border rounded-sm" style={{ borderColor: '#F5F2EB', backgroundColor: bg }} data-testid={`stat-${label.toLowerCase().replace(/\s+/g, '-')}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icon className="w-4 h-4" style={{ color }} />
                <span className="text-[10px] tracking-[0.15em] uppercase font-semibold" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>{label}</span>
              </div>
              <span className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917' }}>{value}</span>
            </div>
          ))}
        </motion.div>

        {/* Live Visitors Panel */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="mb-8 rounded-sm overflow-hidden shadow-sm"
          style={{ border: liveVisitors.length > 0 ? '1px solid rgba(212,175,55,0.35)' : '1px solid #E8E4DC' }}
          data-testid="live-visitors-panel">
          {/* Header */}
          <div className="px-6 py-4 flex items-center justify-between"
            style={{ backgroundColor: liveVisitors.length > 0 ? '#1C1917' : '#FAFAF9' }}>
            <div className="flex items-center gap-3">
              {liveVisitors.length > 0 ? (
                <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(74,222,128,0.15)' }}>
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
                  </span>
                </div>
              ) : (
                <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: '#F5F2EB' }}>
                  <Eye className="w-4 h-4" style={{ color: '#A8A29E' }} />
                </div>
              )}
              <div>
                <span className="text-sm font-semibold tracking-wide"
                  style={{ fontFamily: 'Manrope, sans-serif', color: liveVisitors.length > 0 ? '#FDFCF8' : '#57534E' }}>
                  Live Gallery Visitors
                </span>
                <p className="text-[10px] mt-0.5 tracking-wider uppercase"
                  style={{ fontFamily: 'Manrope, sans-serif', color: liveVisitors.length > 0 ? '#A8A29E' : '#D4D4D8' }}>
                  {liveVisitors.length > 0 ? `${liveVisitors.length} couple${liveVisitors.length !== 1 ? 's' : ''} viewing right now` : 'No couples are currently viewing galleries'}
                </p>
              </div>
            </div>
            {liveVisitors.length > 0 && (
              <span className="flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-bold tracking-widest uppercase"
                style={{ backgroundColor: 'rgba(74,222,128,0.12)', color: '#4ADE80', letterSpacing: '0.15em' }}>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
                </span>
                Live
              </span>
            )}
          </div>
          {/* Visitor rows */}
          {liveVisitors.length > 0 && (
            <div className="divide-y" style={{ borderColor: '#F5F2EB' }}>
              {liveVisitors.map((v) => {
                const mins = Math.floor(v.duration_seconds / 60);
                const actionIcon = v.action === 'watching_video' ? <Film className="w-3.5 h-3.5 text-purple-500" /> 
                  : v.action === 'viewing_photo' ? <ImageIcon className="w-3.5 h-3.5 text-blue-500" />
                  : v.action === 'downloading' ? <Download className="w-3.5 h-3.5 text-green-500" />
                  : v.action === 'selecting_favourites' ? <Heart className="w-3.5 h-3.5 text-pink-500" />
                  : <Eye className="w-3.5 h-3.5 text-gray-400" />;
                const actionLabel = v.action === 'watching_video' ? 'watching Video'
                  : v.action === 'viewing_photo' ? 'viewing Photos'
                  : v.action === 'downloading' ? 'downloading files'
                  : v.action === 'selecting_favourites' ? 'picking Favourites'
                  : 'browsing gallery';
                const deviceIcon = v.device === 'Mobile' ? <Smartphone className="w-3.5 h-3.5" /> 
                  : v.device === 'Tablet' ? <Tablet className="w-3.5 h-3.5" /> 
                  : <Monitor className="w-3.5 h-3.5" />;
                return (
                  <div key={v.session_id} className="px-6 py-3.5 flex items-center gap-4 bg-white hover:bg-[#FDFCF8] transition-colors" data-testid={`visitor-${v.session_id}`}>
                    <div className="relative shrink-0">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold truncate" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#1C1917', fontSize: '15px' }}>
                          {v.gallery_name}
                        </span>
                        <span className="text-xs" style={{ color: '#A8A29E' }}>&mdash;</span>
                        <span className="flex items-center gap-1.5 text-xs" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
                          {actionIcon} {actionLabel}{v.subfolder ? ` ${v.subfolder}` : ''}
                        </span>
                      </div>
                      {v.detail && (
                        <span className="text-[11px] truncate block max-w-[300px] mt-0.5 italic" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                          {v.detail}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      <span className="flex items-center gap-1.5 text-[11px]" style={{ color: '#78716C', fontFamily: 'Manrope, sans-serif' }}>
                        {deviceIcon} {v.device}
                      </span>
                      <span className="text-[11px] font-semibold tabular-nums px-2 py-0.5 rounded-full"
                        style={{ backgroundColor: mins > 0 ? '#F5F2EB' : 'rgba(74,222,128,0.1)', color: mins > 0 ? '#57534E' : '#16A34A', fontFamily: 'Manrope, sans-serif' }}>
                        {mins > 0 ? `${mins} min` : 'Just joined'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>

        {/* Search and Sort */}
        <div className="flex items-center gap-4 mb-8">
          <h2 className="text-3xl md:text-4xl font-medium flex-1" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Couple Folders</h2>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-40 border-[#F5F2EB] rounded-sm text-xs" data-testid="sort-galleries">
              <ArrowUpDown className="w-3.5 h-3.5 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date_desc">Newest First</SelectItem>
              <SelectItem value="date_asc">Oldest First</SelectItem>
              <SelectItem value="name_asc">Name A-Z</SelectItem>
              <SelectItem value="name_desc">Name Z-A</SelectItem>
            </SelectContent>
          </Select>
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
                const stats = galleriesStats[g.id] || {};
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
                      {/* Album Submitted Badge */}
                      {stats.album_submitted && (
                        <div className="absolute top-3 left-3 px-2 py-1 rounded-sm flex items-center gap-1" 
                          style={{ backgroundColor: 'rgba(34,197,94,0.9)' }}>
                          <CheckCircle className="w-3 h-3 text-white" />
                          <span className="text-xs font-medium text-white">Album Submitted</span>
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
                      {/* Stats Row */}
                      <div className="flex items-center gap-4 mt-2 text-xs" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
                        <span className="flex items-center gap-1" title="Total Views">
                          <Eye className="w-3 h-3" /> {stats.total_views || 0}
                        </span>
                        <span className="flex items-center gap-1" title="Unique Visitors">
                          <Users className="w-3 h-3" /> {stats.unique_visitors || 0}
                        </span>
                        <span className="flex items-center gap-1" title="Downloads">
                          <Download className="w-3 h-3" /> {stats.total_downloads || 0}
                        </span>
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
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Couple&apos;s Email <span className="font-normal text-[#A8A29E]">(optional)</span></Label>
              <Input data-testid="client-email-input" type="email" value={form.client_email}
                onChange={e => setForm(f => ({...f, client_email: e.target.value}))}
                placeholder="e.g. couple@email.com" className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]" />
              <p className="text-xs" style={{ color: '#A8A29E' }}>Used to send gallery-ready notifications</p>
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
      {/* Delete Gallery Confirmation Dialog */}
      <Dialog open={deleteConfirm.open} onOpenChange={(open) => !open && setDeleteConfirm({ open: false, id: null, name: "", deleteBackup: false })}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-md" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Delete Gallery</DialogTitle>
            <DialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Are you sure you want to delete <strong>&ldquo;{deleteConfirm.name}&rdquo;</strong> and ALL its files permanently?
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2">
            <label className="flex items-start gap-3 p-3 rounded-sm border cursor-pointer hover:bg-amber-50/50 transition-colors" style={{ borderColor: '#E8E4DC' }}>
              <input data-testid="delete-backup-checkbox" type="checkbox" checked={deleteConfirm.deleteBackup}
                onChange={e => setDeleteConfirm(d => ({...d, deleteBackup: e.target.checked}))}
                className="mt-0.5 w-4 h-4 rounded accent-[#D4AF37]" />
              <div>
                <span className="text-sm font-semibold" style={{ color: '#1C1917', fontFamily: 'Manrope, sans-serif' }}>Also delete from backup</span>
                <p className="text-xs mt-0.5" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                  This will permanently remove the backup copy too, freeing up storage space
                </p>
              </div>
            </label>
          </div>
          <DialogFooter className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => setDeleteConfirm({ open: false, id: null, name: "", deleteBackup: false })}
              className="flex-1 rounded-sm border-[#D4D4D8] text-xs tracking-wider">
              Cancel
            </Button>
            <Button data-testid="confirm-delete-gallery" onClick={confirmDelete}
              className="flex-1 bg-[#9F1239] text-white hover:bg-[#9F1239]/90 rounded-sm text-xs tracking-wider">
              <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete{deleteConfirm.deleteBackup ? " + Backup" : ""}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Broadcast Email Dialog */}
      <Dialog open={showBroadcast} onOpenChange={setShowBroadcast}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-lg" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Broadcast Email</DialogTitle>
            <DialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Send an email to all couples who have an email address on their gallery
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {/* Recipients preview */}
            <div className="p-3 rounded-sm border" style={{ backgroundColor: '#FAFAF9', borderColor: '#F5F2EB' }}>
              <div className="flex items-center gap-2 mb-2">
                <Users className="w-3.5 h-3.5" style={{ color: '#D4AF37' }} />
                <span className="text-xs font-semibold tracking-wider uppercase" style={{ color: '#57534E' }}>
                  {broadcastRecipients.length} Recipient{broadcastRecipients.length !== 1 ? 's' : ''}
                </span>
              </div>
              {broadcastRecipients.length > 0 ? (
                <div className="max-h-24 overflow-y-auto space-y-1">
                  {broadcastRecipients.map(r => (
                    <div key={r.id} className="flex items-center justify-between text-xs" style={{ fontFamily: 'Manrope, sans-serif', color: '#57534E' }}>
                      <span className="truncate">{r.folder_name}</span>
                      <span className="text-[#A8A29E] truncate ml-2">{r.client_email}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                  No couples have email addresses set. Add emails to gallery settings first.
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Subject</Label>
              <Input data-testid="broadcast-subject" value={broadcastForm.subject}
                onChange={e => setBroadcastForm(f => ({...f, subject: e.target.value}))}
                placeholder="e.g. Happy New Year from Weddings By Mark"
                className="border-[#D4D4D8] rounded-sm focus-visible:ring-1 focus-visible:ring-[#D4AF37]" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Message</Label>
              <textarea data-testid="broadcast-body" value={broadcastForm.body}
                onChange={e => setBroadcastForm(f => ({...f, body: e.target.value}))}
                placeholder="Write your message here..."
                rows={8}
                className="w-full px-3 py-2 text-sm border rounded-sm focus:outline-none focus:ring-1 focus:ring-[#D4AF37] resize-none"
                style={{ borderColor: '#D4D4D8', fontFamily: 'Manrope, sans-serif' }} />
            </div>
          </div>
          <DialogFooter>
            <Button data-testid="send-broadcast-btn" onClick={handleSendBroadcast} 
              disabled={sendingBroadcast || broadcastRecipients.length === 0}
              className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-5 text-xs tracking-[0.15em] uppercase font-bold gap-2">
              <Send className="w-4 h-4" />
              {sendingBroadcast ? "Sending..." : `Send to ${broadcastRecipients.length} Couple${broadcastRecipients.length !== 1 ? 's' : ''}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
