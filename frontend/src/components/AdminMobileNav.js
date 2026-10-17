import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Activity, Bell, FolderOpen, HeartPulse, Settings } from "lucide-react";
import { getAdminNotificationCount } from "@/lib/api";

const ITEMS = [
  { label: "Galleries", icon: FolderOpen, path: "/admin/dashboard" },
  { label: "Uploads", icon: Bell, path: "/admin/notifications?filter=uploads", badge: true },
  { label: "Activity", icon: Activity, path: "/admin/activity" },
  { label: "Health", icon: HeartPulse, path: "/admin/health" },
  { label: "Settings", icon: Settings, path: "/admin/settings" },
];

export default function AdminMobileNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const [uploadCount, setUploadCount] = useState(0);
  const isAdminPage = location.pathname.startsWith("/admin") && location.pathname !== "/admin";

  useEffect(() => {
    if (!isAdminPage || !localStorage.getItem("admin_token")) return undefined;
    let mounted = true;
    const refresh = () => getAdminNotificationCount()
      .then((response) => { if (mounted) setUploadCount(response.data.uploads || 0); })
      .catch(() => {});
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => { mounted = false; clearInterval(interval); };
  }, [isAdminPage, location.pathname]);

  if (!isAdminPage || !localStorage.getItem("admin_token")) return null;

  const isActive = (item) => {
    if (item.label === "Galleries") {
      return location.pathname === "/admin/dashboard" ||
        location.pathname === "/admin/galleries" ||
        location.pathname.startsWith("/admin/gallery/");
    }
    if (item.label === "Uploads") return location.pathname === "/admin/notifications";
    return location.pathname === item.path;
  };

  return (
    <nav className="admin-mobile-nav md:hidden" aria-label="Admin shortcuts" data-testid="admin-mobile-nav">
      {ITEMS.map((item) => {
        const Icon = item.icon;
        const active = isActive(item);
        return (
          <button
            key={item.label}
            type="button"
            onClick={() => navigate(item.path)}
            className="relative flex min-w-0 flex-1 flex-col items-center justify-center gap-1 py-2"
            style={{ color: active ? '#D4AF37' : 'var(--admin-faint)' }}
            aria-current={active ? "page" : undefined}
          >
            <span className="relative">
              <Icon className="h-5 w-5" />
              {item.badge && uploadCount > 0 && (
                <span className="absolute -right-2.5 -top-2 min-w-[18px] rounded-full bg-[#9F1239] px-1 text-[9px] font-bold leading-[18px] text-white">
                  {uploadCount > 99 ? "99+" : uploadCount}
                </span>
              )}
            </span>
            <span className="truncate text-[9px] font-semibold tracking-wide">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
