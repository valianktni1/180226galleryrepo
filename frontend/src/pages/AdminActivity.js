import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getAdminActivity } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Eye, Download, Heart, RefreshCw } from "lucide-react";

export default function AdminActivity() {
  const navigate = useNavigate();
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadActivity = async () => {
    setLoading(true);
    try {
      const res = await getAdminActivity(100);
      setActivities(res.data.activities || []);
    } catch (err) {
      console.error("Failed to load activity", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivity();
  }, []);

  const getActionIcon = (action) => {
    switch (action) {
      case "view":
        return <Eye className="w-4 h-4 text-blue-500" />;
      case "download":
        return <Download className="w-4 h-4 text-green-500" />;
      case "favourites_submitted":
        return <Heart className="w-4 h-4 text-amber-500" fill="#D4AF37" />;
      default:
        return <Eye className="w-4 h-4 text-gray-400" />;
    }
  };

  const getActionLabel = (action) => {
    switch (action) {
      case "view":
        return "Viewed Gallery";
      case "download":
        return "Downloaded Files";
      case "favourites_submitted":
        return "Submitted Album Favourites";
      default:
        return action;
    }
  };

  const formatTimestamp = (ts) => {
    const date = new Date(ts);
    return date.toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="min-h-screen bg-[#FDFCF8]">
      <header className="sticky top-0 z-40 border-b bg-white/80 backdrop-blur-md">
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/admin/galleries")}
              className="text-gray-600 hover:text-gray-900"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-xl font-semibold" style={{ fontFamily: "Cormorant Garamond, serif" }}>
              Activity Log
            </h1>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadActivity}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Time
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Action
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Gallery / Couple
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    IP Address
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {activities.map((activity, i) => (
                  <tr key={activity.id || i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {formatTimestamp(activity.timestamp)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {getActionIcon(activity.action)}
                        <span className="text-sm font-medium text-gray-900">
                          {getActionLabel(activity.action)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900">{activity.share_label}</div>
                      <div className="text-xs text-gray-500">{activity.gallery_name}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {activity.details}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
