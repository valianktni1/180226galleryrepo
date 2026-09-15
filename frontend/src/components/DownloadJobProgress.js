import { CheckCircle, Download, Loader2, XCircle } from "lucide-react";


const formatBytes = (bytes = 0) => {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / (1024 ** index);
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
};


export default function DownloadJobProgress({ job, accent = "#D4AF37", dark = false, className = "" }) {
  if (!job) return null;

  const failed = job.status === "failed";
  const complete = job.status === "complete";
  const downloading = job.status === "downloading";
  const percent = Math.max(0, Math.min(100, job.percent || 0));
  let title = "Preparing your ZIP…";
  let detail = `${job.files_done || 0} of ${job.files_total || 0} files`;

  if (job.status === "queued") {
    detail = "Your download is safely queued";
  } else if (job.status === "ready") {
    title = "ZIP ready";
    detail = "Your browser download is starting…";
  } else if (downloading) {
    title = `Downloading: ${percent}%`;
    detail = `${formatBytes(job.bytes_sent)} of ${formatBytes(job.bytes_total)}`;
  } else if (complete) {
    title = "Download complete";
    detail = `${job.files_total || 0} files • ${formatBytes(job.bytes_total)}`;
  } else if (failed) {
    title = "Download failed";
    detail = job.message || "Please try again";
  } else if (job.status === "preparing") {
    title = `Preparing ZIP: ${percent}%`;
    detail = `${job.files_done || 0} of ${job.files_total || 0} files • ${formatBytes(job.bytes_prepared)} of ${formatBytes(job.source_bytes_total)}`;
  }

  const statusColour = failed ? "#BE123C" : complete ? "#16A34A" : accent;
  const Icon = failed ? XCircle : complete ? CheckCircle : downloading ? Download : Loader2;

  return (
    <div
      data-testid="folder-download-progress"
      className={`w-full rounded-sm border px-3 py-2.5 ${className}`}
      style={{
        borderColor: `${statusColour}55`,
        backgroundColor: dark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.92)",
      }}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2.5">
        <Icon
          className={`w-4 h-4 shrink-0 ${!failed && !complete && !downloading ? "animate-spin" : ""}`}
          style={{ color: statusColour }}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="font-semibold truncate" style={{ color: dark ? "#F5F5F4" : "#44403C" }}>{title}</span>
            {!failed && <span className="font-bold tabular-nums" style={{ color: statusColour }}>{percent}%</span>}
          </div>
          <p className="mt-0.5 text-[11px] truncate" style={{ color: dark ? "#D6D3D1" : "#78716C" }}>{detail}</p>
        </div>
      </div>
      {!failed && !complete && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full" style={{ backgroundColor: dark ? "rgba(255,255,255,0.12)" : "#E7E5E4" }}>
          <div className="h-full rounded-full transition-[width] duration-300" style={{ width: `${percent}%`, backgroundColor: statusColour }} />
        </div>
      )}
    </div>
  );
}
