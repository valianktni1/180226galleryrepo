import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { getSystemHealth } from "../lib/api";

// These are the gallery's reported encoder jobs, not overall GPU utilisation.
export function describeEncoding(health) {
  if (!Array.isArray(health?.work?.video_queue)) {
    return { label: "Unavailable", detail: "Encoding status could not be read", tone: "warning" };
  }
  const jobs = health.work.video_queue;
  const active = jobs.filter(job => ["transcoding", "processing"].includes(job.status));
  const queued = jobs.filter(job => job.status === "queued");
  const failed = jobs.find(job => job.status === "failed");
  const complete = jobs.find(job => job.status === "complete");
  if (active.length) {
    const job = active.find(item => item.method === "GPU") || active[0];
    const percent = Number.isFinite(Number(job.percent))
      ? Math.max(0, Math.min(100, Number(job.percent))) : null;
    const gpu = active.some(item => item.method === "GPU");
    const cpu = active.some(item => item.method === "CPU");
    const label = gpu && cpu ? "GPU + CPU" : job.method === "GPU"
      ? (percent > 0 ? "GPU encoding" : "GPU starting")
      : job.method === "CPU" ? "CPU fallback" : "Processing";
    return {
      label, percent, tone: "active", detail: job.filename || "Video",
      fileTitle: `${job.gallery_name || "Gallery"} / ${job.filename || "Video"}`,
      summary: `${active.length} active${queued.length ? ` / ${queued.length} queued` : ""}`,
    };
  }
  if (queued.length) {
    return {
      label: "Queued", detail: queued[0].filename || "Video", tone: "waiting",
      summary: `${queued.length} waiting to encode`,
      fileTitle: `${queued[0].gallery_name || "Gallery"} / ${queued[0].filename || "Video"}`,
    };
  }
  if (failed) return { label: "Encoding failed", detail: failed.filename || "Video", tone: "warning" };
  if (complete) return { label: "Ready", detail: complete.filename || "Video", tone: "idle", summary: "Web video ready" };
  return {
    label: "Idle", detail: "No encoding jobs reported", tone: "idle",
    summary: health.services?.video_gpu?.status === "healthy" ? "GPU detected" : "GPU availability unconfirmed",
  };
}

export default function GpuEncodingMonitor({ onOpen }) {
  const [view, setView] = useState({ label: "Checking...", detail: "Reading encoding status", tone: "idle" });

  useEffect(() => {
    let mounted = true;
    let timer;
    const poll = async () => {
      if (!localStorage.getItem("admin_token")) return;
      if (!document.hidden) {
        try {
          const response = await getSystemHealth({ timeout: 8000 });
          if (mounted) setView(describeEncoding(response.data));
        } catch {
          // Never leave an old "GPU encoding" or "Idle" claim on a failed refresh.
          if (mounted) setView({ label: "Unavailable", detail: "Could not refresh encoding status", tone: "warning" });
        }
      }
      if (mounted) timer = setTimeout(poll, 5000);
    };
    poll();
    return () => { mounted = false; clearTimeout(timer); };
  }, []);

  const color = view.tone === "active" ? "#22C55E" : view.tone === "warning" ? "#EF4444" : "#F59E0B";
  return (
    <button type="button" onClick={onOpen}
      className="p-3 sm:p-5 border-b md:border-b-0 md:border-r min-w-0 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
      style={{ borderColor: "var(--admin-border)", backgroundColor: "rgba(245,158,11,0.06)" }}
      aria-label="GPU and video encoding status. Open System Health for details."
      data-testid="gpu-encoding-monitor">
      <div className="flex items-center gap-2 mb-2">
        <Cpu className="w-3.5 h-3.5 shrink-0" style={{ color }} aria-hidden="true" />
        <span className="text-[10px] tracking-[0.15em] uppercase font-semibold"
          style={{ color: "var(--admin-faint)", fontFamily: "Manrope, sans-serif" }}>GPU / Video</span>
      </div>
      <span className="block text-xl font-medium leading-tight"
        style={{ fontFamily: "Cormorant Garamond, serif", color: "var(--admin-text)" }}>{view.label}</span>
      <p className="text-[10px] mt-1 truncate" title={view.fileTitle || view.detail}
        style={{ color: "var(--admin-muted)", fontFamily: "Manrope, sans-serif" }}>{view.detail}</p>
      {view.percent !== undefined && view.percent !== null && (
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1 flex-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--admin-border)" }}
            role="progressbar" aria-label={`Encoding progress for ${view.detail}`}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={view.percent}>
            <div className="h-full rounded-full" style={{ width: `${view.percent}%`, backgroundColor: color }} />
          </div>
          <span className="text-[10px] shrink-0" style={{ color: "var(--admin-muted)" }}>{Math.round(view.percent)}%</span>
        </div>
      )}
      {view.summary && <p className="text-[10px] mt-1" style={{ color: "var(--admin-faint)", fontFamily: "Manrope, sans-serif" }}>{view.summary}</p>}
    </button>
  );
}
