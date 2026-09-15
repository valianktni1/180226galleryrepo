import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import {
  Activity, AlertTriangle, ArrowLeft, CheckCircle2, Clock, Cloud,
  Cpu, Database, Download, HardDrive, HeartPulse, Mail, RefreshCw,
  Server, ShieldCheck, Users, Video, XCircle
} from "lucide-react";
import { getSystemHealth } from "@/lib/api";
import AdminThemeToggle from "@/components/AdminThemeToggle";

const STATUS = {
  healthy: { label: "Healthy", color: "#15803D", bg: "#F0FDF4", border: "#BBF7D0", Icon: CheckCircle2 },
  active: { label: "Active", color: "#1D4ED8", bg: "#EFF6FF", border: "#BFDBFE", Icon: Activity },
  warning: { label: "Attention", color: "#B45309", bg: "#FFFBEB", border: "#FDE68A", Icon: AlertTriangle },
  critical: { label: "Critical", color: "#B91C1C", bg: "#FEF2F2", border: "#FECACA", Icon: XCircle },
  neutral: { label: "External", color: "#57534E", bg: "#FAFAF9", border: "#E7E5E4", Icon: ShieldCheck },
};

const tone = (status) => STATUS[status] || STATUS.neutral;

const formatBytes = (bytes = 0) => {
  if (!bytes) return "0 GB";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, index)).toFixed(index >= 3 ? 1 : 0)} ${units[index]}`;
};

const formatDate = (value) => value
  ? new Date(value).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
  : "Not recorded yet";

const formatUptime = (seconds = 0) => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};

function StatusBadge({ status }) {
  const item = tone(status);
  const Icon = item.Icon;
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-[0.12em]"
      style={{ color: item.color, backgroundColor: item.bg, border: `1px solid ${item.border}` }}>
      <Icon className="w-3.5 h-3.5" /> {item.label}
    </span>
  );
}

function SummaryCard({ icon: Icon, label, value, detail, status = "neutral" }) {
  const item = tone(status);
  return (
    <div className="p-5 border rounded-sm bg-white min-w-0" style={{ borderColor: "var(--admin-border)" }}>
      <div className="flex items-center gap-2 mb-3">
        <span className="w-8 h-8 rounded-full flex items-center justify-center" style={{ color: item.color, backgroundColor: item.bg }}>
          <Icon className="w-4 h-4" />
        </span>
        <span className="text-[10px] tracking-[0.15em] uppercase font-semibold text-[#78716C]">{label}</span>
      </div>
      <div className="text-2xl font-medium text-[#1C1917] truncate" style={{ fontFamily: "Cormorant Garamond, serif" }}>{value}</div>
      <p className="text-xs text-[#78716C] mt-1 leading-relaxed">{detail}</p>
    </div>
  );
}

function HealthRow({ icon: Icon, item }) {
  return (
    <div className="p-4 sm:p-5 flex items-start gap-3 border-b last:border-b-0" style={{ borderColor: "var(--admin-border)" }}>
      <div className="w-9 h-9 shrink-0 rounded-full flex items-center justify-center bg-[#F7F5EF] text-[#57534E]">
        <Icon className="w-4 h-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-[#1C1917]">{item.title}</h3>
          <StatusBadge status={item.status} />
        </div>
        <p className="text-xs text-[#78716C] leading-relaxed mt-1">{item.detail}</p>
        {item.latency_ms !== undefined && item.latency_ms !== null && (
          <p className="text-[10px] text-[#A8A29E] mt-1">Response {item.latency_ms} ms</p>
        )}
      </div>
    </div>
  );
}

function Section({ title, subtitle, children }) {
  return (
    <section className="border rounded-sm bg-white overflow-hidden" style={{ borderColor: "var(--admin-border)" }}>
      <div className="px-5 py-4 bg-[#FAFAF9] border-b" style={{ borderColor: "var(--admin-border)" }}>
        <h2 className="text-sm font-semibold text-[#1C1917]">{title}</h2>
        <p className="text-[11px] text-[#A8A29E] mt-0.5">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

export default function AdminSystemHealth() {
  const navigate = useNavigate();
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const response = await getSystemHealth();
      setHealth(response.data);
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "The health summary could not be loaded.");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { navigate("/admin"); return undefined; }
    load();
    const interval = setInterval(() => load(true), 15000);
    return () => clearInterval(interval);
  }, [load, navigate]);

  const storage = health?.summary?.storage;
  const backup = health?.summary?.backup;
  const downloads = health?.work?.folder_downloads;
  const broadcast = health?.work?.broadcast_campaign;
  const overall = tone(health?.status);
  const OverallIcon = overall.Icon;

  return (
    <div className="min-h-screen" data-admin-page data-testid="system-health-page" style={{ backgroundColor: 'var(--admin-bg)' }}>
      <header className="sticky top-0 z-40 border-b backdrop-blur-md" style={{ backgroundColor: 'var(--admin-header-bg)', borderColor: "rgba(212,175,55,0.15)" }}>
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => navigate("/admin/dashboard")} className="gap-2 shrink-0" data-testid="health-back-btn">
              <ArrowLeft className="w-4 h-4" /> <span className="hidden sm:inline">Dashboard</span>
            </Button>
            <div className="min-w-0">
              <h1 className="text-xl sm:text-2xl font-medium truncate" style={{ fontFamily: "Cormorant Garamond, serif" }}>System Health</h1>
              <p className="text-[10px] text-[#A8A29E]">Read-only monitoring</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <AdminThemeToggle />
            <Button variant="outline" size="sm" onClick={() => load()} disabled={loading} className="gap-2" data-testid="refresh-health-btn">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {loading && !health ? (
          <div className="py-24 text-center text-sm text-[#78716C]">Checking the gallery systems…</div>
        ) : error && !health ? (
          <div className="max-w-xl mx-auto p-6 border rounded-sm bg-white text-center" style={{ borderColor: "#FECACA" }}>
            <XCircle className="w-8 h-8 text-red-700 mx-auto mb-3" />
            <h2 className="font-semibold">Health summary unavailable</h2>
            <p className="text-sm text-[#78716C] mt-1">{error}</p>
            <Button className="mt-4" onClick={() => load()}>Try again</Button>
          </div>
        ) : health && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="p-5 sm:p-6 rounded-sm border mb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              style={{ backgroundColor: overall.bg, borderColor: overall.border }} data-testid="overall-health">
              <div className="flex items-start gap-3">
                <OverallIcon className="w-7 h-7 shrink-0 mt-0.5" style={{ color: overall.color }} />
                <div>
                  <h2 className="text-xl font-semibold" style={{ color: overall.color, fontFamily: "Cormorant Garamond, serif" }}>{health.title}</h2>
                  <p className="text-xs mt-1 text-[#57534E]">Checked {formatDate(health.checked_at)} · Backend uptime {formatUptime(health.uptime_seconds)}</p>
                </div>
              </div>
              <StatusBadge status={health.status} />
            </div>

            {error && <div className="mb-5 px-4 py-3 text-xs rounded-sm bg-amber-50 text-amber-800 border border-amber-200">Refresh failed; showing the last successful result.</div>}

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
              <SummaryCard icon={HardDrive} label="Gallery storage" value={storage ? `${storage.used_percent}% used` : "—"}
                detail={storage ? `${formatBytes(storage.free_bytes)} free` : "Unavailable"} status={storage?.status} />
              <SummaryCard icon={ShieldCheck} label="Last gallery backup" value={backup?.status === "active" ? "Running" : formatDate(backup?.last_completed_at)}
                detail={backup?.title || "Not recorded"} status={backup?.status} />
              <SummaryCard icon={Activity} label="Active work" value={health.summary.active_work}
                detail="Backups, broadcasts, video jobs and folder ZIPs" status={health.summary.active_work > 0 ? "active" : "healthy"} />
              <SummaryCard icon={Users} label="Couples online" value={health.summary.couples_online}
                detail="Active gallery sessions now" status={health.summary.couples_online > 0 ? "active" : "healthy"} />
            </div>

            <div className="grid lg:grid-cols-2 gap-5">
              <Section title="Core services" subtitle="Checks performed safely by the gallery application">
                <HealthRow icon={Server} item={health.services.api} />
                <HealthRow icon={Database} item={health.services.database} />
                <HealthRow icon={Mail} item={health.services.email} />
                <HealthRow icon={Cpu} item={health.services.video_gpu} />
              </Section>

              <Section title="Background activity" subtitle="Work currently happening inside the gallery">
                <HealthRow icon={Video} item={{
                  status: health.work.video_optimisations + health.work.video_files_transcoding > 0 ? "active" : "healthy",
                  title: `${health.work.video_optimisations + health.work.video_files_transcoding} video job(s) active`,
                  detail: "Web optimisation and per-file transcoding queues."
                }} />
                <HealthRow icon={Download} item={{
                  status: downloads.active > 0 ? "active" : "healthy",
                  title: `${downloads.active} folder download(s) active`,
                  detail: `${formatBytes(downloads.cache_bytes)} currently held in the temporary ZIP cache.`
                }} />
                <HealthRow icon={Users} item={{
                  status: health.work.couples_online > 0 ? "active" : "healthy",
                  title: `${health.work.couples_online} couple session(s) online`,
                  detail: "Based on gallery heartbeats received within the last minute."
                }} />
                <HealthRow icon={Clock} item={{
                  status: health.work.backup_running ? "active" : "healthy",
                  title: health.work.backup_running ? "Gallery backup running" : "No gallery backup running",
                  detail: health.work.backup_running ? backup.detail : "Background backup worker is available."
                }} />
                <HealthRow icon={Mail} item={{
                  status: broadcast ? "active" : "healthy",
                  title: broadcast ? `Broadcast ${broadcast.sent}/${broadcast.total} sent` : "No broadcast running",
                  detail: broadcast ? broadcast.message : "The paced email queue is available."
                }} />
              </Section>

              <div className="lg:col-span-2">
                <Section title="Data protection" subtitle="Clear separation between app-verified and TrueNAS-managed protection">
                  <div className="grid md:grid-cols-3">
                    <div className="md:border-r" style={{ borderColor: "var(--admin-border)" }}><HealthRow icon={HardDrive} item={health.protection.gallery_backup} /></div>
                    <div className="md:border-r" style={{ borderColor: "var(--admin-border)" }}><HealthRow icon={Database} item={health.protection.database_backup} /></div>
                    <HealthRow icon={Cloud} item={health.protection.offsite_backup} />
                  </div>
                </Section>
              </div>
            </div>

            <p className="text-[10px] text-center text-[#A8A29E] mt-6">Refreshes every 15 seconds. This screen cannot restart, delete or change anything.</p>
          </motion.div>
        )}
      </main>
    </div>
  );
}
