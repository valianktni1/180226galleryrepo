import { act } from "react";
import { createRoot } from "react-dom/client";
import GpuEncodingMonitor, { describeEncoding } from "./GpuEncodingMonitor";
import { getSystemHealth } from "../lib/api";

jest.mock("../lib/api", () => ({ getSystemHealth: jest.fn() }));

const snapshot = (jobs = []) => ({
  services: { video_gpu: { status: "healthy" } },
  work: { video_queue: jobs },
});
const gpuJob = { status: "transcoding", method: "GPU", percent: 42, filename: "ceremony.mp4", gallery_name: "Mark & Gina" };

test("detecting a GPU never implies that it is currently encoding", () => {
  expect(describeEncoding(snapshot())).toMatchObject({ label: "Idle", summary: "GPU detected" });
  expect(describeEncoding(null).label).toBe("Unavailable");
  expect(describeEncoding({ work: {} }).label).toBe("Unavailable");
});

test("distinguishes a starting GPU attempt, real encoding progress and CPU fallback", () => {
  expect(describeEncoding(snapshot([{ ...gpuJob, percent: 0 }])).label).toBe("GPU starting");
  expect(describeEncoding(snapshot([gpuJob]))).toMatchObject({ label: "GPU encoding", percent: 42, detail: "ceremony.mp4" });
  expect(describeEncoding(snapshot([{ ...gpuJob, method: "CPU" }])).label).toBe("CPU fallback");
  expect(describeEncoding(snapshot([{ ...gpuJob, method: "" }])).label).toBe("Processing");
});

test("shows simultaneous GPU/CPU jobs and counts waiting jobs without averaging their progress", () => {
  const view = describeEncoding(snapshot([
    { ...gpuJob, method: "CPU", percent: 80 }, gpuJob,
    { status: "queued", method: "Waiting", filename: "speeches.mp4" },
  ]));
  expect(view).toMatchObject({ label: "GPU + CPU", percent: 42, summary: "2 active / 1 queued" });
});

test.each([
  ["queued", "Queued"], ["failed", "Encoding failed"], ["complete", "Ready"],
])("reports %s separately from idle or active encoding", (status, label) => {
  expect(describeEncoding(snapshot([{ ...gpuJob, status }])).label).toBe(label);
});

test("bounds progress and omits an invalid percentage", () => {
  expect(describeEncoding(snapshot([{ ...gpuJob, percent: 150 }])).percent).toBe(100);
  expect(describeEncoding(snapshot([{ ...gpuJob, percent: -20 }])).percent).toBe(0);
  expect(describeEncoding(snapshot([{ ...gpuJob, percent: "unknown" }])).percent).toBeNull();
});

describe("live monitor", () => {
  let container;
  let root;
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    global.IS_REACT_ACT_ENVIRONMENT = true;
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    localStorage.setItem("admin_token", "test-admin");
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    localStorage.clear();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  test("clears stale encoding claims on failure and recovers on the next poll", async () => {
    getSystemHealth.mockResolvedValueOnce({ data: snapshot([gpuJob]) })
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ data: snapshot() });
    const onOpen = jest.fn();
    await act(async () => root.render(<GpuEncodingMonitor onOpen={onOpen} />));
    expect(container.textContent).toContain("GPU encoding");
    expect(container.querySelector('[role="progressbar"]').getAttribute("aria-valuenow")).toBe("42");
    expect(getSystemHealth).toHaveBeenCalledWith({ timeout: 8000 });
    await act(async () => container.querySelector("button").click());
    expect(onOpen).toHaveBeenCalledTimes(1);
    await act(async () => jest.advanceTimersByTime(5000));
    expect(container.textContent).toContain("Unavailable");
    expect(container.textContent).not.toContain("GPU encoding");
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
    await act(async () => jest.advanceTimersByTime(5000));
    expect(container.textContent).toContain("Idle");
  });

  test("does not overlap requests or poll after unmount", async () => {
    let resolve;
    getSystemHealth.mockReturnValue(new Promise(done => { resolve = done; }));
    await act(async () => root.render(<GpuEncodingMonitor />));
    await act(async () => jest.advanceTimersByTime(20000));
    expect(getSystemHealth).toHaveBeenCalledTimes(1);
    await act(async () => root.unmount());
    root = createRoot(container);
    await act(async () => resolve({ data: snapshot([gpuJob]) }));
    await act(async () => jest.advanceTimersByTime(20000));
    expect(getSystemHealth).toHaveBeenCalledTimes(1);
  });

  test("pauses polling while the dashboard is hidden", async () => {
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    getSystemHealth.mockResolvedValue({ data: snapshot() });
    await act(async () => root.render(<GpuEncodingMonitor />));
    expect(getSystemHealth).not.toHaveBeenCalled();
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    await act(async () => jest.advanceTimersByTime(5000));
    expect(getSystemHealth).toHaveBeenCalledTimes(1);
  });
});
