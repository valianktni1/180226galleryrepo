import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle, ArrowLeft, Bell, CheckCheck, Download, Images,
  Mic2, RefreshCw, Trash2, BookOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import AdminThemeToggle from "@/components/AdminThemeToggle";
import {
  dismissAdminNotification, getAdminNotifications,
  markAdminNotificationRead, markAllAdminNotificationsRead,
} from "@/lib/api";

const FILTERS = [
  ["all", "All"], ["uploads", "Uploads"], ["voice", "Voice"],
  ["albums", "Albums"], ["expiring", "Expiring"], ["downloads", "Downloads"],
];

const ICONS = {
  guest_upload: Images,
  voice_message: Mic2,
  album_submission: BookOpen,
  share_expiring: AlertTriangle,
  download_complete: Download,
};

const ACCENTS = {
  guest_upload: "#0891B2",
  voice_message: "#8B5CF6",
  album_submission: "#D4AF37",
  share_expiring: "#F59E0B",
  download_complete: "#16A34A",
};

export default function AdminNotifications() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = FILTERS.some(([value]) => value === searchParams.get("filter"))
    ? searchParams.get("filter") : "all";
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (quiet = false) => {
    try {
      const response = await getAdminNotifications(filter);
      setNotifications(response.data.notifications || []);
      setUnread(response.data.unread || 0);
    } catch {
      if (!quiet) toast.error("Could not load admin updates");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { navigate("/admin"); return undefined; }
    setLoading(true);
    load();
    const interval = setInterval(() => load(true), 30000);
    return () => clearInterval(interval);
  }, [navigate, load]);

  const openNotification = async (notification) => {
    if (!notification.read_at) {
      await markAdminNotificationRead(notification.id).catch(() => {});
    }
    navigate(notification.target_url || "/admin/dashboard");
  };

  const markAll = async () => {
    try {
      await markAllAdminNotificationsRead();
      setNotifications((items) => items.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() })));
      setUnread(0);
    } catch { toast.error("Could not mark updates as read"); }
  };

  const dismiss = async (event, notification) => {
    event.stopPropagation();
    try {
      await dismissAdminNotification(notification.id);
      setNotifications((items) => items.filter((item) => item.id !== notification.id));
      if (!notification.read_at) setUnread((count) => Math.max(0, count - 1));
    } catch { toast.error("Could not dismiss that update"); }
  };

  return (
    <div className="min-h-screen w-full overflow-x-hidden" data-admin-page style={{ backgroundColor: 'var(--admin-bg)', color: 'var(--admin-text)' }}>
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'var(--admin-header-bg)', borderColor: 'var(--admin-border)' }}>
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-3 py-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button onClick={() => navigate("/admin/dashboard")} aria-label="Back to dashboard"><ArrowLeft className="h-5 w-5" /></button>
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-medium">Notification Centre</h1>
              <p className="text-xs" style={{ color: 'var(--admin-muted)' }}>{unread} unread update{unread === 1 ? '' : 's'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <AdminThemeToggle />
            <Button variant="outline" size="sm" onClick={() => load()} aria-label="Refresh updates"><RefreshCw className="h-4 w-4" /></Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-3 py-5 sm:px-6 sm:py-8">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div className="flex min-w-0 gap-2 overflow-x-auto pb-1">
            {FILTERS.map(([value, label]) => (
              <button key={value} onClick={() => setSearchParams(value === 'all' ? {} : { filter: value })}
                className="shrink-0 border px-3 py-2 text-xs font-semibold"
                style={{ backgroundColor: filter === value ? '#D4AF37' : 'var(--admin-surface)', color: filter === value ? '#fff' : 'var(--admin-muted)', borderColor: 'var(--admin-border)' }}>
                {label}
              </button>
            ))}
          </div>
          {unread > 0 && <Button variant="ghost" size="sm" onClick={markAll} className="shrink-0 gap-2"><CheckCheck className="h-4 w-4" /><span className="hidden sm:inline">Mark all read</span></Button>}
        </div>

        {loading ? (
          <div className="space-y-3">{[1,2,3].map((item) => <div key={item} className="h-24 animate-pulse border" style={{ backgroundColor: 'var(--admin-surface)', borderColor: 'var(--admin-border)' }} />)}</div>
        ) : notifications.length === 0 ? (
          <div className="border py-20 text-center" style={{ backgroundColor: 'var(--admin-surface)', borderColor: 'var(--admin-border)' }}>
            <Bell className="mx-auto mb-3 h-9 w-9" style={{ color: 'var(--admin-faint)' }} />
            <h2 className="text-2xl">You&apos;re all caught up</h2>
            <p className="mt-1 text-sm" style={{ color: 'var(--admin-muted)' }}>New uploads, messages and gallery actions will appear here.</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="admin-notification-list">
            {notifications.map((notification) => {
              const Icon = ICONS[notification.type] || Bell;
              const accent = ACCENTS[notification.type] || '#78716C';
              return (
                <article key={notification.id}
                  className="flex w-full items-start border transition-colors"
                  style={{ backgroundColor: notification.read_at ? 'var(--admin-surface)' : 'var(--admin-surface-soft)', borderColor: notification.read_at ? 'var(--admin-border)' : accent }}>
                  <button type="button" onClick={() => openNotification(notification)} className="flex min-w-0 flex-1 items-start gap-3 p-4 text-left">
                    <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full" style={{ color: accent, backgroundColor: `${accent}18` }}><Icon className="h-4 w-4" /></span>
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <strong className="text-sm">{notification.title}</strong>
                        {notification.count > 1 && <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ backgroundColor: `${accent}18`, color: accent }}>{notification.count}</span>}
                        {!notification.read_at && <span className="h-2 w-2 rounded-full" style={{ backgroundColor: accent }} />}
                      </span>
                      <span className="mt-1 block text-xs leading-relaxed" style={{ color: 'var(--admin-muted)' }}>{notification.message}</span>
                      <span className="mt-2 block text-[10px] uppercase tracking-wider" style={{ color: 'var(--admin-faint)' }}>{notification.gallery_name} · {new Date(notification.updated_at).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                    </span>
                  </button>
                  <button type="button" onClick={(event) => dismiss(event, notification)} aria-label="Dismiss update" className="m-2 p-2" style={{ color: 'var(--admin-faint)' }}><Trash2 className="h-4 w-4" /></button>
                </article>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
