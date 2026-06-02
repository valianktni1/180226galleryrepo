import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getAdminActivity } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Eye, Download, Heart, RefreshCw, ChevronDown, ChevronUp, Filter, FileText, Package } from "lucide-react";

export default function AdminActivity() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [filterAction, setFilterAction] = useState(searchParams.get("action") || "");
  const galleryFilter = searchParams.get("gallery_id") || "";

  const loadActivity = async () => {
    setLoading(true);
    try {
      const res = await getAdminActivity(200, galleryFilter || null, filterAction || null);
      setActivities(res.data.activities || []);
    } catch (err) {
      console.error("Failed to load activity", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivity();
  }, [filterAction]);

  const toggleExpand = (id) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const getActionIcon = (action) => {
    switch (action) {
      case "view": return <Eye className="w-4 h-4 text-blue-500" />;
      case "download": return <Download className="w-4 h-4 text-green-600" />;
      case "favourites_submitted": return <Heart className="w-4 h-4 text-amber-500" fill="#D4AF37" />;
      default: return <Eye className="w-4 h-4 text-gray-400" />;
    }
  };

  const getActionLabel = (action) => {
    switch (action) {
      case "view": return "Viewed Gallery";
      case "download": return "Downloaded";
      case "favourites_submitted": return "Submitted Favourites";
      default: return action;
    }
  };

  const getCompletenessBadge = (activity) => {
    if (activity.action !== "download" || !activity.completeness) return null;
    const c = activity.completeness;
    const colors = {
      full: "bg-green-100 text-green-800 border-green-200",
      partial: "bg-amber-100 text-amber-800 border-amber-200",
      single: "bg-blue-100 text-blue-800 border-blue-200",
    };
    const labels = {
      full: "Full Download",
      partial: `Partial (${activity.files_count}/${activity.total_available})`,
      single: "Single File",
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold tracking-wider uppercase border rounded-sm ${colors[c] || ""}`}
        data-testid={`completeness-badge-${c}`}>
        {labels[c] || c}
      </span>
    );
  };

  const getDownloadTypeBadge = (activity) => {
    if (activity.action !== "download" || !activity.download_type) return null;
    const t = activity.download_type;
    const icons = { single: FileText, selection: Filter, album: Package, favourites: Heart };
    const labels = { single: "Single", selection: "Selection", album: "Album", favourites: "Favourites" };
    const Icon = icons[t] || Download;
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-gray-500">
        <Icon className="w-3 h-3" /> {labels[t] || t}
      </span>
    );
  };

  const formatTimestamp = (ts) => {
    const date = new Date(ts);
    return date.toLocaleString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  };

  return (
    <div className="min-h-screen bg-[#FDFCF8]">
      <header className="sticky top-0 z-40 border-b bg-white/80 backdrop-blur-md">
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/admin/galleries")} className="text-gray-600 hover:text-gray-900" data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-xl font-semibold" style={{ fontFamily: "Cormorant Garamond, serif" }}>
              Activity Log
            </h1>
          </div>
          <div className="flex items-center gap-2">
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
        {loading && activities.length === 0 ? (
          <div className="text-center py-20 text-gray-500">Loading activity...</div>
        ) : activities.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <Eye className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No activity recorded yet</p>
            <p className="text-sm mt-2">Activity will appear here when couples view or download their galleries</p>
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
      </main>
    </div>
  );
}
