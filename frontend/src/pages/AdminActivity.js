import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getAdminActivity, getArchivedActivity, clearActivityLogs, archiveLogsNow, getActivityStats, getEmailLog } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowLeft, Eye, Download, Heart, RefreshCw, ChevronDown, ChevronUp, Filter, FileText, Package, Search, Trash2, Archive, AlertTriangle, Mail, Send, Bell } from "lucide-react";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";

// ─── Helpers ───
const formatTimestamp = (ts) => {
  if (!ts) return "-";
  try {
    const d = new Date(ts);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) + " " +
           d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  } catch { return ts; }
};
const getActionIcon = (action) => {
  if (action === "download") return <Download className="w-4 h-4 text-blue-500" />;
  if (action === "view") return <Eye className="w-4 h-4 text-green-500" />;
  if (action === "favourites_submitted") return <Heart className="w-4 h-4 text-pink-500" />;
  return <FileText className="w-4 h-4 text-gray-400" />;
};
const getActionLabel = (action) => {
  if (action === "download") return "Download";
  if (action === "view") return "Gallery View";
  if (action === "favourites_submitted") return "Favourites Submitted";
  return action || "Unknown";
};
const getDownloadTypeBadge = (activity) => {
  if (activity.action !== "download") return null;
  if (activity.download_type === "all_zip") return <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium"><Package className="w-3 h-3 inline mr-0.5" />Full ZIP</span>;
  if (activity.download_type === "subfolder_zip") return <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 font-medium"><Package className="w-3 h-3 inline mr-0.5" />Folder ZIP</span>;
  if (activity.download_type === "single") return <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium"><FileText className="w-3 h-3 inline mr-0.5" />Single File</span>;
  return null;
};
const getCompletenessBadge = (activity) => {
  if (activity.action !== "download" || !activity.files_count) return null;
  return <span className="text-[10px] text-gray-400">{activity.files_count} file{activity.files_count !== 1 ? "s" : ""}</span>;
};

export default function AdminActivity() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [filterAction, setFilterAction] = useState(searchParams.get("action") || "");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [viewMode, setViewMode] = useState("active"); // "active", "archive", or "emails"
  const [stats, setStats] = useState({ active_count: 0, archived_count: 0 });
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [emailLogs, setEmailLogs] = useState([]);
  const [emailLoading, setEmailLoading] = useState(false);
  const galleryFilter = searchParams.get("gallery_id") || "";

  const loadActivity = async () => {
    setLoading(true);
    try {
      const fetcher = viewMode === "archive" ? getArchivedActivity : getAdminActivity;
      const limit = viewMode === "archive" ? 200 : 200;
      const res = await fetcher(limit, galleryFilter || null, filterAction || null, searchQuery || null);
      setActivities(res.data.activities || []);
    } catch (err) {
      console.error("Failed to load activity", err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const res = await getActivityStats();
      setStats(res.data);
    } catch { /* ignore */ }
  };

  const loadEmailLog = async () => {
    setEmailLoading(true);
    try {
      const res = await getEmailLog();
      setEmailLogs(res.data.emails || []);
    } catch { setEmailLogs([]); }
    finally { setEmailLoading(false); }
  };

  useEffect(() => {
    if (viewMode === "emails") {
      loadEmailLog();
    } else {
      loadActivity();
    }
    loadStats();
  }, [filterAction, searchQuery, viewMode]);

  const toggleExpand = (id) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleClearLogs = async () => {
    try {
      const res = await clearActivityLogs();
      toast.success(`Cleared ${res.data.cleared} log entries`);
      setShowClearConfirm(false);
      loadActivity();
      loadStats();
    } catch (err) {
      toast.error("Failed to clear logs");
    }
  };

  const handleArchiveNow = async () => {
    setArchiving(true);
    try {
      const res = await archiveLogsNow();
      if (res.data.archived > 0) {
        toast.success(`Archived ${res.data.archived} log entries older than 6 months`);
      } else {
        toast.info("No logs older than 6 months to archive");
      }
      loadActivity();
      loadStats();
    } catch (err) {
      toast.error("Failed to archive logs");
    } finally { setArchiving(false); }
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate("/admin/dashboard")} className="gap-2"
              data-testid="back-btn">
              <ArrowLeft className="w-4 h-4" /> Back
            </Button>
            <div>
              <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
                Activity Log
              </h1>
              <p className="text-xs" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                {stats.active_count} active {stats.archived_count > 0 && `· ${stats.archived_count} archived`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
              <Input
                data-testid="search-name"
                type="text"
                placeholder="Search by name..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') setSearchQuery(searchInput); }}
                className="pl-8 h-8 w-48 text-xs border-gray-200 rounded"
              />
            </div>
            {searchQuery && (
              <button
                onClick={() => { setSearchQuery(""); setSearchInput(""); }}
                className="text-[10px] text-gray-500 hover:text-gray-800 underline"
                data-testid="clear-search"
              >
                Clear
              </button>
            )}
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="text-xs border rounded px-2 py-1.5 bg-white text-gray-700"
              data-testid="filter-action"
            >
              <option value="">All Activity</option>
              <option value="download">Downloads Only</option>
              <option value="view">Views Only</option>
              <option value="favourites_submitted">Favourites Only</option>
            </select>
            <Button variant="outline" size="sm" onClick={loadActivity} disabled={loading} className="gap-2" data-testid="refresh-btn">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-8">
        {/* Toolbar: Active/Archive toggle + Clear/Archive buttons */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-1 p-1 rounded-sm border" style={{ borderColor: '#E8E4DC', backgroundColor: '#F5F2EB' }}>
            <button
              onClick={() => setViewMode("active")}
              className={`px-4 py-1.5 text-xs font-semibold tracking-wider uppercase rounded-sm transition-colors ${
                viewMode === "active" ? "bg-white shadow-sm text-[#1C1917]" : "text-[#A8A29E] hover:text-[#57534E]"
              }`}
              style={{ fontFamily: 'Manrope, sans-serif' }}
              data-testid="tab-active"
            >
              Active ({stats.active_count})
            </button>
            <button
              onClick={() => setViewMode("archive")}
              className={`px-4 py-1.5 text-xs font-semibold tracking-wider uppercase rounded-sm transition-colors flex items-center gap-1.5 ${
                viewMode === "archive" ? "bg-white shadow-sm text-[#1C1917]" : "text-[#A8A29E] hover:text-[#57534E]"
              }`}
              style={{ fontFamily: 'Manrope, sans-serif' }}
              data-testid="tab-archive"
            >
              <Archive className="w-3 h-3" /> Archive ({stats.archived_count})
            </button>
            <button
              onClick={() => setViewMode("emails")}
              className={`px-4 py-1.5 text-xs font-semibold tracking-wider uppercase rounded-sm transition-colors flex items-center gap-1.5 ${
                viewMode === "emails" ? "bg-white shadow-sm text-[#1C1917]" : "text-[#A8A29E] hover:text-[#57534E]"
              }`}
              style={{ fontFamily: 'Manrope, sans-serif' }}
              data-testid="tab-emails"
            >
              <Mail className="w-3 h-3" /> Emails
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleArchiveNow} disabled={archiving}
              className="gap-2 text-xs" data-testid="archive-now-btn">
              <Archive className="w-3.5 h-3.5" /> {archiving ? "Archiving..." : "Archive Old Logs"}
            </Button>
            {viewMode === "active" && (
              <Button variant="outline" size="sm" onClick={() => setShowClearConfirm(true)}
                className="gap-2 text-xs text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                data-testid="clear-logs-btn">
                <Trash2 className="w-3.5 h-3.5" /> Clear Logs
              </Button>
            )}
          </div>
        </div>

        {/* Clear Confirmation Dialog */}
        <AnimatePresence>
          {showClearConfirm && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
              className="mb-6 p-4 border rounded-sm flex items-center justify-between"
              style={{ backgroundColor: '#FEF2F2', borderColor: '#FECACA' }}>
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-red-800">Clear all active logs?</p>
                  <p className="text-xs text-red-600 mt-0.5">This will permanently delete {stats.active_count} log entries. Consider archiving first.</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => setShowClearConfirm(false)} className="text-xs">
                  Cancel
                </Button>
                <Button size="sm" onClick={handleClearLogs}
                  className="text-xs bg-red-600 text-white hover:bg-red-700" data-testid="confirm-clear-btn">
                  Yes, Clear All
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Email Log View */}
        {viewMode === "emails" ? (
          <>
            <div className="mb-6 p-4 rounded-sm border flex items-center gap-3" style={{ backgroundColor: 'rgba(212,175,55,0.06)', borderColor: 'rgba(212,175,55,0.25)' }}>
              <Mail className="w-4 h-4 shrink-0" style={{ color: '#D4AF37' }} />
              <p className="text-xs" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
                A record of all emails sent — broadcast messages, gallery-ready notifications, and automated expiry reminders.
              </p>
            </div>
            {emailLoading ? (
              <div className="text-center py-20 text-gray-500">Loading email log...</div>
            ) : emailLogs.length === 0 ? (
              <div className="text-center py-20 text-gray-500">
                <Mail className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>No emails sent yet</p>
                <p className="text-sm mt-2">Emails will appear here when you send broadcasts, notify couples, or expiry reminders go out</p>
              </div>
            ) : (
              <div className="bg-white rounded-lg border shadow-sm overflow-hidden overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date &amp; Time</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subject</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Couple / Gallery</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sent To</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {emailLogs.map((email, i) => {
                      const typeIcon = email.type === "broadcast" ? <Send className="w-3.5 h-3.5 text-blue-500" />
                        : email.type === "gallery_ready" ? <Bell className="w-3.5 h-3.5 text-green-500" />
                        : <Mail className="w-3.5 h-3.5 text-amber-500" />;
                      const typeLabel = email.type === "broadcast" ? "Broadcast"
                        : email.type === "gallery_ready" ? "Gallery Ready"
                        : "Expiry Reminder";
                      const typeBg = email.type === "broadcast" ? "bg-blue-50 text-blue-700"
                        : email.type === "gallery_ready" ? "bg-green-50 text-green-700"
                        : "bg-amber-50 text-amber-700";
                      return (
                        <tr key={i} className="hover:bg-gray-50" data-testid={`email-row-${i}`}>
                          <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                            {formatTimestamp(email.timestamp)}
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium ${typeBg}`}>
                              {typeIcon} {typeLabel}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900" style={{ fontFamily: 'Manrope, sans-serif' }}>
                            {email.subject}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-700" style={{ fontFamily: 'Manrope, sans-serif' }}>
                            {email.gallery_name}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 font-mono">
                            {email.recipient}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
        <>
        {/* Archive info banner */}
        {viewMode === "archive" && (
          <div className="mb-6 p-4 rounded-sm border flex items-center gap-3" style={{ backgroundColor: 'rgba(212,175,55,0.06)', borderColor: 'rgba(212,175,55,0.25)' }}>
            <Archive className="w-4 h-4 shrink-0" style={{ color: '#D4AF37' }} />
            <p className="text-xs" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Archived logs are automatically moved here after 6 months. An email notification is sent when archiving occurs.
            </p>
          </div>
        )}

        {loading && activities.length === 0 ? (
          <div className="text-center py-20 text-gray-500">Loading activity...</div>
        ) : activities.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <Eye className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>{viewMode === "archive" ? "No archived logs" : "No activity recorded yet"}</p>
            <p className="text-sm mt-2">
              {viewMode === "archive"
                ? "Logs older than 6 months will appear here automatically"
                : "Activity will appear here when couples view or download their galleries"}
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-lg border shadow-sm overflow-hidden overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Gallery / Couple</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                  <th className="px-4 py-3 w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {activities.map((activity, i) => {
                  const hasFiles = activity.files_downloaded && activity.files_downloaded.length > 0;
                  const isExpanded = expandedRows.has(activity.id || i);
                  return (
                    <tr key={activity.id || i} className="group" data-testid={`activity-row-${i}`}>
                      <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap align-top">
                        {formatTimestamp(activity.timestamp)}
                      </td>
                      <td className="px-4 py-3 align-top">
                        <div className="flex items-center gap-2">
                          {getActionIcon(activity.action)}
                          <span className="text-sm font-medium text-gray-900">{getActionLabel(activity.action)}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          {getDownloadTypeBadge(activity)}
                        </div>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <div className="text-sm text-gray-900">{activity.share_label}</div>
                        <div className="text-xs text-gray-500">{activity.gallery_name}</div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 font-mono align-top">
                        {activity.ip_address || "-"}
                      </td>
                      <td className="px-4 py-3 align-top">
                        <div className="text-sm text-gray-600">{activity.details}</div>
                        <div className="flex items-center gap-2 mt-1">
                          {getCompletenessBadge(activity)}
                          {activity.subfolder && activity.action === "download" && (
                            <span className="text-[10px] text-gray-400">
                              {activity.subfolder}
                            </span>
                          )}
                        </div>
                        {/* Expanded file list */}
                        {isExpanded && hasFiles && (
                          <div className="mt-2 p-2 bg-gray-50 rounded border text-xs text-gray-600 max-h-48 overflow-y-auto" data-testid={`files-list-${i}`}>
                            <div className="font-medium text-gray-700 mb-1">
                              {activity.files_count} file{activity.files_count !== 1 ? "s" : ""} downloaded:
                            </div>
                            {activity.files_downloaded.map((fn, j) => (
                              <div key={j} className="py-0.5 truncate text-gray-500 pl-2 border-l-2 border-gray-200">
                                {fn}
                              </div>
                            ))}
                            {activity.files_count > activity.files_downloaded.length && (
                              <div className="py-0.5 text-gray-400 italic pl-2">
                                ...and {activity.files_count - activity.files_downloaded.length} more
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 align-top">
                        {hasFiles && (
                          <button
                            onClick={() => toggleExpand(activity.id || i)}
                            className="p-1 text-gray-400 hover:text-gray-700 transition-colors"
                            data-testid={`expand-btn-${i}`}
                            title={isExpanded ? "Hide files" : "Show files"}
                          >
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        </>
        )}
      </main>
    </div>
  );
}
