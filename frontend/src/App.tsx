import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleHelp,
  Clapperboard,
  Cpu,
  Film,
  Gauge,
  HardDrive,
  Layers3,
  LoaderCircle,
  MonitorPlay,
  Pause,
  Play,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  SquareStop,
  Upload,
  WandSparkles,
  Zap,
} from "lucide-react";

type Page = "overview" | "media" | "settings";
type Job = {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  stage: string;
  updated_at: string;
  recording_name?: string | null;
};
type Overview = {
  recordings_total: number;
  recordings_ready: number;
  clips_total: number;
  jobs_active: number;
  jobs_failed: number;
  approvals_pending: number;
  published_total: number;
  recent_jobs: Job[];
  updated_at: string;
};
type SystemInfo = {
  checked_at: string;
  platform: string;
  python_version: string;
  cpu: { name: string; logical_processors: number | null };
  memory: { total_bytes: number; available_bytes: number; percent_used: number };
  disk: { free_bytes: number | null; total_bytes: number | null };
  media_tools: { ffmpeg_version: string | null; ffprobe_version: string | null };
  transcription_package_installed: boolean;
  gpu: {
    available: boolean;
    name: string | null;
    memory_total_mb: number | null;
    memory_free_mb: number | null;
    driver_version: string | null;
  };
  ollama: { online: boolean; model_configured: string; model_available: boolean };
  data_directory: string;
};
type Settings = {
  automation_mode: "manual" | "semi_automatic" | "automatic";
  processing_paused: boolean;
  emergency_stop: boolean;
  max_concurrent_jobs: number;
  cpu_limit_percent: number;
  ollama_url: string;
  ollama_model: string;
  transcription_model: "tiny" | "base" | "small";
  public_uploads_enabled: boolean;
};
type Recording = {
  id: string;
  file_path: string;
  display_name: string;
  duration_seconds: number | null;
  status: string;
  authorized: boolean;
  created_at: string;
  transcript_model: string | null;
  transcript_language: string | null;
  language_probability: number | null;
  metadata: {
    size_bytes?: number;
    video?: { width?: number; height?: number; codec?: string };
  } | null;
};
type QueueJob = Job & {
  error_message?: string | null;
  attempt_count?: number;
  recording_id?: string | null;
};
type RecordingAnalysis = {
  recording_id: string;
  transcript: null | {
    language: string | null;
    language_probability: number | null;
    model_name: string;
    device: string;
    transcript_path: string;
    subtitle_path: string;
    created_at: string;
    segments: Array<{ start: number; end: number; text: string; confidence: number }>;
  };
  analysis: null | {
    scene_cuts: number[];
    candidate_count: number;
    audio_profile: { mean_rms: number; peak_rms: number; active_audio_fraction: number };
    scoring: { method: string; weights: Record<string, number> };
  };
  candidates: Array<{
    id: string;
    title: string;
    score: number;
    start_seconds: number;
    end_seconds: number;
    reasons: string[];
    signals: { audio_energy: number; speech_density: number; excitement_cues: number; scene_changes: number };
    status: string;
  }>;
};

const navItems = [
  { label: "Overview", icon: Layers3, page: "overview" as const },
  { label: "Media library", icon: MonitorPlay, page: "media" as const },
  { label: "Settings", icon: Settings2, page: "settings" as const },
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function formatBytes(value: number | null | undefined) {
  if (value == null) return "Unavailable";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatDuration(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  const seconds = Math.max(0, Math.floor(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}` : `${minutes}:${String(rest).padStart(2, "0")}`;
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function App() {
  const [page, setPage] = useState<Page>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const loadDashboard = useCallback(async (background = false) => {
    if (background) setRefreshing(true);
    else setLoading(true);
    try {
      const [nextOverview, nextSettings] = await Promise.all([
        api<Overview>("/api/overview"),
        api<Settings>("/api/settings"),
      ]);
      setOverview(nextOverview);
      setSettings(nextSettings);
      setError(null);
      const nextSystem = await api<SystemInfo>("/api/system");
      setSystem(nextSystem);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The local API could not be reached.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
    const timer = window.setInterval(() => void loadDashboard(true), 20_000);
    return () => window.clearInterval(timer);
  }, [loadDashboard]);

  const saveSettings = async (patch: Partial<Settings>) => {
    try {
      const next = await api<Settings>("/api/settings", {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      setSettings(next);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2200);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Settings could not be saved.");
    }
  };

  const healthItems = useMemo(() => {
    if (!system) return [];
    return [
      {
        name: "FFmpeg",
        detail: system.media_tools.ffmpeg_version ?? "Not found on PATH",
        ready: Boolean(system.media_tools.ffmpeg_version),
        icon: Clapperboard,
      },
      {
        name: "NVIDIA GPU",
        detail: system.gpu.available
          ? `${system.gpu.name} · ${formatBytes((system.gpu.memory_total_mb ?? 0) * 1024 * 1024)}`
          : "No NVIDIA GPU detected",
        ready: system.gpu.available,
        icon: Cpu,
      },
      {
        name: "Transcription",
        detail: system.transcription_package_installed ? "faster-whisper installed" : "faster-whisper not installed",
        ready: system.transcription_package_installed,
        icon: Activity,
      },
      {
        name: "Ollama",
        detail: system.ollama.online
          ? `${system.ollama.model_configured}${system.ollama.model_available ? " · model ready" : " · model not found"}`
          : "Local service offline",
        ready: system.ollama.online && system.ollama.model_available,
        icon: Sparkles,
      },
    ];
  }, [system]);

  const activeJobs = overview?.jobs_active ?? 0;
  const systemReady = Boolean(system?.media_tools.ffmpeg_version && system.transcription_package_installed && !settings?.emergency_stop);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark"><WandSparkles size={19} strokeWidth={2.2} /></div>
          <div className="brand-copy"><span>CLIPFORGE</span><small>AI STUDIO</small></div>
          <button className="icon-button sidebar-collapse" aria-label="Sidebar options"><ChevronDown size={15} /></button>
        </div>

        <div className="workspace-picker">
          <div className="workspace-avatar">C</div>
          <div className="workspace-copy"><span>Creator workspace</span><small>Local machine</small></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>

        <div className="nav-label">STUDIO</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navItems.map(({ label, icon: Icon, page: target }) => (
            <button key={target} className={`nav-item ${page === target ? "active" : ""}`} onClick={() => setPage(target)}>
              <Icon size={17} strokeWidth={1.9} /><span>{label}</span>
              {target === "overview" && activeJobs > 0 && <span className="nav-count">{activeJobs}</span>}
            </button>
          ))}
        </nav>

        <div className="nav-label modules-label">WORKFLOW</div>
        <div className="workflow-list">
          <div className="workflow-item"><span className="workflow-number">01</span><span>Bring in footage</span><span className="workflow-dot" /></div>
          <div className="workflow-item"><span className="workflow-number">02</span><span>Find highlights</span><span className="workflow-dot" /></div>
          <div className="workflow-item"><span className="workflow-number">03</span><span>Review and publish</span><span className="workflow-dot" /></div>
        </div>

        <div className="sidebar-spacer" />
        <div className="local-card">
          <div className="local-card-top"><span className="live-dot" /><span>LOCAL MODE</span><CircleHelp size={14} /></div>
          <p>Your recordings and settings stay on this device.</p>
          <div className="local-card-foot"><ShieldCheck size={14} /><span>Private by default</span></div>
        </div>
        <div className="profile-row">
          <div className="profile-avatar">CF</div>
          <div className="profile-copy"><span>Local creator</span><small>Personal studio</small></div>
          <button className="icon-button" aria-label="Profile options"><ChevronDown size={15} /></button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
              <div className="breadcrumb"><span>CLIPFORGE AI</span><span className="crumb-divider">/</span><span>{page === "overview" ? "OVERVIEW" : page === "media" ? "MEDIA LIBRARY" : "SETTINGS"}</span></div>
          <div className="topbar-actions">
            <div className={`system-pill ${systemReady ? "ready" : "attention"}`}>
              <span className="pill-dot" />{systemReady ? "Studio ready" : "Setup needs attention"}
            </div>
            <button className="icon-button topbar-refresh" onClick={() => void loadDashboard(true)} aria-label="Refresh data" title="Refresh data">
              <RefreshCw size={16} className={refreshing ? "spin" : ""} />
            </button>
          </div>
        </header>

        <div className="page-content">
          {error && <div className="error-banner"><AlertTriangle size={17} /><span>{error}</span><button onClick={() => void loadDashboard(true)}>Retry</button></div>}
          {page === "overview" ? (
            <>
              <section className="page-heading">
                <div>
                  <div className="eyebrow"><span className="eyebrow-line" /> CREATOR CONTROL ROOM</div>
                  <h1>{greeting()}, creator<span className="heading-period">.</span></h1>
                  <p className="heading-subtitle">Your gaming content studio, running locally on this PC.</p>
                </div>
                <div className="heading-meta"><span className="calendar-icon"><Activity size={15} /></span><span>{new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date())}</span></div>
              </section>

              <section className="hero-panel">
                <div className="hero-copy">
                  <div className="hero-kicker"><span className="hero-kicker-dot" /> YOUR STUDIO IS READY</div>
                  <h2>Turn long sessions<br />into <span>your next big moment.</span></h2>
                  <p>Bring in a recording when you’re ready. ClipForge will keep your source file untouched and build from there.</p>
                  <button className="primary-button" onClick={() => setPage("settings")}>
                    <Settings2 size={16} /> Review setup <ArrowUpRight size={15} />
                  </button>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
                  <div className="art-crosshair crosshair-a" /><div className="art-crosshair crosshair-b" />
                  <div className="art-film"><Film size={31} strokeWidth={1.3} /></div>
                  <div className="art-spark spark-one"><Zap size={13} fill="currentColor" /></div>
                  <div className="art-spark spark-two"><Sparkles size={16} /></div>
                  <div className="art-wave"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
                  <div className="art-timecode">00:00:00:00</div>
                </div>
                <div className="hero-footer"><span><ShieldCheck size={14} /> Source files are never overwritten</span><span className="hero-footer-divider" /><span>Local-first workflow</span></div>
              </section>

              <section className="stats-grid" aria-label="Workspace totals">
                <StatCard title="Recordings" value={overview?.recordings_total} icon={MonitorPlay} tone="violet" loading={loading} foot={`${overview?.recordings_ready ?? 0} ready to process`} />
                <StatCard title="Clips created" value={overview?.clips_total} icon={Clapperboard} tone="blue" loading={loading} foot="Generated from your recordings" />
                <StatCard title="Awaiting review" value={overview?.approvals_pending} icon={ShieldCheck} tone="amber" loading={loading} foot="Human review before publishing" />
                <StatCard title="Published" value={overview?.published_total} icon={Upload} tone="green" loading={loading} foot="Approved uploads tracked here" />
              </section>

              <section className="lower-grid">
                <div className="surface-card activity-card">
                  <div className="section-header">
                    <div><div className="section-overline">LIVE WORKSPACE</div><h3>Recent activity</h3></div>
                    <div className="section-header-right"><span className="sync-label"><span className="sync-dot" />Syncs automatically</span><button className="text-button" onClick={() => void loadDashboard(true)}>Refresh <RefreshCw size={13} /></button></div>
                  </div>
                  {loading ? <div className="loading-state"><LoaderCircle className="spin" size={20} /> Loading workspace data…</div> : overview?.recent_jobs.length ? (
                    <div className="activity-list">
                      {overview.recent_jobs.map((job) => <ActivityRow key={job.id} job={job} />)}
                    </div>
                  ) : (
                    <div className="empty-activity">
                      <div className="empty-icon"><MonitorPlay size={21} /></div>
                      <div><strong>No activity yet</strong><p>Processing jobs will appear here after you add a recording.</p></div>
                    </div>
                  )}
                  <div className="activity-footer"><span>Showing the latest jobs recorded by this app</span><span>{overview ? `Updated ${formatDate(overview.updated_at)}` : "Waiting for the local API"}</span></div>
                </div>

                <div className="surface-card readiness-card">
                  <div className="section-header readiness-header">
                    <div><div className="section-overline">ENVIRONMENT CHECK</div><h3>Studio readiness</h3></div>
                    <span className={`readiness-score ${systemReady ? "good" : "warn"}`}><span />{systemReady ? "Ready" : "Check setup"}</span>
                  </div>
                  <div className="readiness-list">
                    {healthItems.map(({ name, detail, ready, icon: Icon }) => (
                      <div className="readiness-row" key={name}>
                        <div className="readiness-icon"><Icon size={15} /></div>
                        <div className="readiness-copy"><span>{name}</span><small title={detail}>{detail}</small></div>
                        <span className={`check-state ${ready ? "ok" : "missing"}`}>{ready ? <Check size={13} /> : <span>!</span>}</span>
                      </div>
                    ))}
                    {!system && <div className="readiness-loading"><LoaderCircle size={17} className="spin" /> Checking local tools…</div>}
                  </div>
                  <button className="readiness-link" onClick={() => setPage("settings")}>View system details <ArrowUpRight size={14} /></button>
                </div>
              </section>
            </>
          ) : page === "media" ? (
            <MediaPage onRefresh={() => void loadDashboard(true)} />
          ) : (
            <SettingsPage
              settings={settings}
              system={system}
              saved={saved}
              saveSettings={saveSettings}
              loading={loading}
            />
          )}

          <footer className="app-footer"><span>CLIPFORGE AI <b>·</b> LOCAL CREATOR STUDIO</span><span>Built for your workflow <Sparkles size={12} /></span></footer>
        </div>
      </main>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, tone, loading, foot }: {
  title: string;
  value: number | undefined;
  icon: typeof Film;
  tone: string;
  loading: boolean;
  foot: string;
}) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-top"><div className="stat-icon"><Icon size={17} /></div><span className="stat-context"><ArrowDownRight size={13} /> All time</span></div>
      <div className="stat-value">{loading ? <span className="value-skeleton" /> : value ?? "—"}</div>
      <div className="stat-title">{title}</div>
      <div className="stat-foot">{foot}</div>
    </div>
  );
}

function ActivityRow({ job }: { job: Job }) {
  const status = job.status.toLowerCase();
  return (
    <div className="activity-row">
      <div className={`activity-job-icon ${status}`}><Clapperboard size={16} /></div>
      <div className="activity-main"><strong>{job.recording_name || job.job_type.replaceAll("_", " ")}</strong><span>{job.stage.replaceAll("_", " ")} · {formatDate(job.updated_at)}</span></div>
      <div className="activity-progress-wrap">
        <div className={`job-status status-${status}`}>{status}</div>
        <div className="progress-track"><span style={{ width: `${Math.max(0, Math.min(job.progress, 100))}%` }} /></div>
      </div>
      <span className="activity-percent">{Math.round(job.progress)}%</span>
    </div>
  );
}

function MediaPage({ onRefresh }: { onRefresh: () => void }) {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [jobs, setJobs] = useState<QueueJob[]>([]);
  const [path, setPath] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RecordingAnalysis | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [nextRecordings, nextJobs] = await Promise.all([
        api<Recording[]>("/api/recordings"),
        api<QueueJob[]>("/api/jobs"),
      ]);
      setRecordings(nextRecordings);
      setJobs(nextJobs);
      setPageError(null);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The media library could not be loaded.");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3500);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const browse = async () => {
    setBusy(true);
    setMessage(null);
    setPageError(null);
    try {
      const result = await api<{ path: string | null }>("/api/recordings/browse", { method: "POST", body: "{}" });
      if (result.path) setPath(result.path);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The file picker could not be opened.");
    } finally {
      setBusy(false);
    }
  };

  const importRecording = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setPageError(null);
    try {
      const result = await api<{ recording_id: string; job_id: string; display_name: string }>("/api/recordings", {
        method: "POST",
        body: JSON.stringify({ path, authorized }),
      });
      setMessage(`${result.display_name} added to the inspection queue.`);
      setPath("");
      setAuthorized(false);
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The recording could not be imported.");
    } finally {
      setBusy(false);
    }
  };

  const retry = async (jobId: string) => {
    setPageError(null);
    try {
      await api<QueueJob>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST", body: "{}" });
      setMessage("The failed job was queued again.");
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The job could not be retried.");
    }
  };

  const startAnalysis = async (recording: Recording) => {
    setAnalyzingId(recording.id);
    setMessage(null);
    setPageError(null);
    try {
      const result = await api<{ id: string; existing: boolean }>(`/api/recordings/${encodeURIComponent(recording.id)}/analyze`, { method: "POST", body: "{}" });
      setMessage(result.existing ? "This recording is already in the analysis queue." : `Analysis queued for ${recording.display_name}. The first run downloads the selected model; transcription then runs locally.`);
      setSelectedAnalysisId(null);
      setAnalysis(null);
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Analysis could not be queued.");
    } finally {
      setAnalyzingId(null);
    }
  };

  const viewAnalysis = async (recordingId: string) => {
    setSelectedAnalysisId(recordingId);
    setAnalysis(null);
    setPageError(null);
    try {
      setAnalysis(await api<RecordingAnalysis>(`/api/recordings/${encodeURIComponent(recordingId)}/analysis`));
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Analysis could not be loaded.");
    }
  };

  return (
    <>
      <section className="page-heading media-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> LOCAL SOURCE LIBRARY</div><h1>Media library<span className="heading-period">.</span></h1><p className="heading-subtitle">Add a recording to inspect its streams and prepare it for analysis.</p></div>
        <button className="secondary-button" onClick={() => void refresh()}><RefreshCw size={14} /> Refresh library</button>
      </section>

      {pageError && <div className="error-banner media-error"><AlertTriangle size={17} /><span>{pageError}</span></div>}
      {message && <div className="success-banner"><Check size={16} /><span>{message}</span><button aria-label="Dismiss message" onClick={() => setMessage(null)}>×</button></div>}

      <section className="surface-card import-card">
        <div className="import-card-header">
          <div className="import-icon"><Upload size={18} /></div>
          <div><div className="section-overline">ADD LOCAL RECORDING</div><h3>Bring a session into your studio</h3><p>The original stays at its current path. ClipForge only reads it and stores its own metadata.</p></div>
        </div>
        <form onSubmit={(event) => void importRecording(event)}>
          <div className="path-entry-row">
            <label className="sr-only" htmlFor="recording-path">Video file path</label>
            <input id="recording-path" type="text" autoComplete="off" spellCheck={false} value={path} onChange={(event) => setPath(event.target.value)} placeholder="Paste a local path or browse for a recording" />
            <button type="button" className="secondary-button browse-button" onClick={() => void browse()} disabled={busy}><HardDrive size={14} /> Browse files</button>
          </div>
          <div className="import-actions-row">
            <label className="authorization-check"><input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} /><span className="checkmark"><Check size={12} /></span><span>I own this recording or have permission to use it.</span></label>
            <button className="primary-button import-submit" type="submit" disabled={!path.trim() || !authorized || busy}>{busy ? <LoaderCircle className="spin" size={15} /> : <Upload size={15} />}{busy ? "Working…" : "Add recording"}<ArrowUpRight size={14} /></button>
          </div>
        </form>
        <div className="import-footnote"><ShieldCheck size={14} /><span>Authorization is required before processing. This confirmation does not clear rights to third-party music or game assets.</span></div>
      </section>

      <div className="media-columns">
        <section className="surface-card library-card">
          <div className="section-header">
            <div><div className="section-overline">SOURCE FILES</div><h3>Recordings <span className="count-badge">{recordings.length}</span></h3></div>
            <span className="library-local-tag"><span /> Stored locally</span>
          </div>
          {recordings.length ? <div className="recording-list">
            {recordings.map((recording) => <div className="recording-row" key={recording.id}>
              <div className="recording-thumb"><MonitorPlay size={19} /></div>
              <div className="recording-copy"><strong title={recording.display_name}>{recording.display_name}</strong><span title={recording.file_path}>{recording.file_path}</span></div>
              <div className="recording-meta"><span>{formatDuration(recording.duration_seconds)}</span><small>{recording.metadata?.video?.width && recording.metadata?.video?.height ? `${recording.metadata.video.width} × ${recording.metadata.video.height}` : "Awaiting probe"}</small></div>
              <span className={`recording-state state-${recording.status}`}>{recording.status.replaceAll("_", " ")}</span>
              <div className="recording-actions">
                {recording.transcript_model && <button className="row-action-button" onClick={() => void viewAnalysis(recording.id)}>View results</button>}
                {jobs.some((job) => job.recording_id === recording.id && job.job_type === "analyze_recording" && ["queued", "running", "paused"].includes(job.status))
                  ? <span className="analysis-running"><LoaderCircle size={12} className="spin" /> Analysis queued</span>
                  : <button className="row-action-button analyze-action" disabled={analyzingId === recording.id || !["ready", "analyzed"].includes(recording.status) && !(recording.status === "failed" && Boolean(recording.metadata))} onClick={() => void startAnalysis(recording)}>{analyzingId === recording.id ? <LoaderCircle size={12} className="spin" /> : <Sparkles size={12} />}{recording.transcript_model ? "Re-analyze" : "Analyze"}</button>}
              </div>
            </div>)}
          </div> : <div className="library-empty"><div className="empty-icon"><MonitorPlay size={20} /></div><strong>No recordings added</strong><p>Choose an authorized video file to create your first local source entry.</p></div>}
        </section>

        <section className="surface-card queue-card">
          <div className="section-header"><div><div className="section-overline">BACKGROUND WORK</div><h3>Inspection queue <span className="count-badge">{jobs.length}</span></h3></div><Activity size={16} className="queue-header-icon" /></div>
          {jobs.length ? <div className="queue-list">{jobs.map((job) => <div className="queue-row" key={job.id}>
            <div className={`queue-icon status-${job.status}`}><Clapperboard size={15} /></div>
            <div className="queue-copy"><strong>{job.recording_name || "Recording"}</strong><span>{job.stage.replaceAll("_", " ")}{job.error_message ? ` · ${job.error_message}` : ""}</span><div className="progress-track"><span style={{ width: `${Math.max(0, Math.min(job.progress, 100))}%` }} /></div></div>
            <div className="queue-status-wrap"><span className={`job-status status-${job.status}`}>{job.status}</span>{job.status === "failed" && <button className="retry-button" onClick={() => void retry(job.id)}>Retry</button>}</div>
          </div>)}</div> : <div className="queue-empty"><div className="empty-icon"><Activity size={18} /></div><strong>Queue is clear</strong><p>Imported recordings will be inspected in the background.</p></div>}
          <div className="queue-footer"><span><span className="queue-live-dot" /> Updates automatically</span><span>{jobs.filter((job) => job.status === "running").length} running</span></div>
        </section>
      </div>
      {selectedAnalysisId && <section className="surface-card analysis-results" aria-live="polite">
        {!analysis ? <div className="analysis-loading"><LoaderCircle className="spin" size={18} /> Loading transcription and highlights…</div> : <>
          <div className="analysis-header">
            <div><div className="section-overline">TRANSCRIPTION & SIGNAL ANALYSIS</div><h3>{recordings.find((item) => item.id === selectedAnalysisId)?.display_name ?? "Recording analysis"}</h3><p>Generated locally with {analysis.transcript?.model_name ?? "faster-whisper"} · {analysis.transcript?.language?.toUpperCase() ?? "Language undetected"} · {analysis.transcript?.device ?? "CPU"}</p></div>
            <div className="analysis-header-actions"><a className="secondary-button subtitle-link" href={`/api/recordings/${encodeURIComponent(selectedAnalysisId)}/subtitles`} download><Upload size={13} /> Download SRT</a><button className="icon-button close-analysis" onClick={() => { setSelectedAnalysisId(null); setAnalysis(null); }} aria-label="Close analysis">×</button></div>
          </div>
          <div className="analysis-summary"><span><strong>{analysis.transcript?.segments.length ?? 0}</strong> transcript segments</span><span><strong>{analysis.candidates.length}</strong> ranked candidates</span><span><strong>{analysis.analysis?.scene_cuts.length ?? 0}</strong> scene changes</span><span>Model: <strong>{analysis.transcript?.model_name}</strong> · CPU int8</span></div>
          <div className="candidate-section-heading"><div><div className="section-overline">HUMAN REVIEW</div><h4>Candidate highlights</h4></div><span>Scores rank signals; review before making clips.</span></div>
          {analysis.candidates.length ? <div className="candidate-list">{analysis.candidates.map((candidate, index) => {
            const excerpt = analysis.transcript?.segments.filter((segment) => segment.end > candidate.start_seconds && segment.start < candidate.end_seconds).slice(0, 5) ?? [];
            return <article className="candidate-card" key={candidate.id}>
              <div className="candidate-rank">{String(index + 1).padStart(2, "0")}</div>
              <div className="candidate-body"><div className="candidate-topline"><h4>{candidate.title}</h4><span className="candidate-score">{candidate.score.toFixed(0)}<small>/100</small></span></div>
                <div className="candidate-meta"><span><Clapperboard size={12} /> {formatDuration(candidate.start_seconds)}–{formatDuration(candidate.end_seconds)}</span>{candidate.reasons.map((reason) => <span className="reason-chip" key={reason}>{reason}</span>)}</div>
                {excerpt.length ? <p className="candidate-excerpt">{excerpt.map((segment) => segment.text).join(" ")}</p> : <p className="candidate-excerpt muted-excerpt">No speech detected in this candidate window.</p>}
              </div>
              <div className="candidate-signals"><span>Audio <b>{Math.round(candidate.signals.audio_energy * 100)}%</b></span><span>Speech <b>{Math.round(candidate.signals.speech_density * 100)}%</b></span><span>Scene cuts <b>{candidate.signals.scene_changes}</b></span></div>
            </article>;
          })}</div> : <div className="no-candidates"><div className="empty-icon"><Sparkles size={18} /></div><div><strong>No clear highlight candidates found</strong><p>The recording was transcribed, but its audio, transcript, and scene signals did not pass the candidate threshold.</p></div></div>}
          <details className="full-transcript"><summary>Full transcript <span>{analysis.transcript?.segments.length ?? 0} segments</span></summary>{analysis.transcript?.segments.length ? <div className="transcript-list">{analysis.transcript.segments.map((segment, index) => <div className="transcript-line" key={`${segment.start}-${index}`}><time>{formatDuration(segment.start)}</time><span>{segment.text}</span></div>)}</div> : <p className="transcript-empty">No speech was recognized in this recording.</p>}</details>
        </>}
      </section>}
    </>
  );
}

function SettingsPage({ settings, system, saved, saveSettings, loading }: {
  settings: Settings | null;
  system: SystemInfo | null;
  saved: boolean;
  saveSettings: (patch: Partial<Settings>) => Promise<void>;
  loading: boolean;
}) {
  if (loading || !settings) {
    return <div className="settings-loading"><LoaderCircle className="spin" size={21} /> Loading settings…</div>;
  }

  return (
    <>
      <section className="page-heading settings-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> STUDIO CONFIGURATION</div><h1>Settings<span className="heading-period">.</span></h1><p className="heading-subtitle">Control how ClipForge runs on this device.</p></div>
        <div className={`save-indicator ${saved ? "visible" : ""}`}><Check size={14} /> Saved locally</div>
      </section>

      <div className="settings-layout">
        <div className="settings-main-column">
          <section className="surface-card settings-card">
            <div className="settings-card-heading"><div className="settings-card-icon violet"><Activity size={17} /></div><div><h3>Automation mode</h3><p>Choose how much control ClipForge takes during processing.</p></div></div>
            <div className="mode-options">
              {([
                ["manual", "Manual", "You start and review each step."],
                ["semi_automatic", "Semi-automatic", "Prepare clips for your approval."],
                ["automatic", "Automatic", "Follow configured policies."],
              ] as const).map(([value, label, description]) => (
                <button key={value} className={`mode-option ${settings.automation_mode === value ? "selected" : ""}`} onClick={() => void saveSettings({ automation_mode: value })}>
                  <span className="radio-dot" /><span className="mode-copy"><strong>{label}</strong><small>{description}</small></span>{settings.automation_mode === value && <Check size={15} className="mode-check" />}
                </button>
              ))}
            </div>
            <div className="settings-note"><ShieldCheck size={15} /><span>Publishing always requires an explicit approval. Public uploads are disabled by default.</span></div>
          </section>

          <section className="surface-card settings-card">
            <div className="settings-card-heading"><div className="settings-card-icon blue"><Gauge size={17} /></div><div><h3>Resource limits</h3><p>Keep local processing responsive while other apps are open.</p></div></div>
            <div className="setting-control-row">
              <div className="setting-control-copy"><strong>Maximum concurrent jobs</strong><small>Start with one worker for this 16 GB system.</small></div>
              <select value={settings.max_concurrent_jobs} onChange={(event) => void saveSettings({ max_concurrent_jobs: Number(event.target.value) })}>
                {[1, 2, 3, 4].map((value) => <option key={value} value={value}>{value} {value === 1 ? "job" : "jobs"}</option>)}
              </select>
            </div>
            <div className="setting-control-row">
              <div className="setting-control-copy"><strong>CPU usage limit</strong><small>Worker target when processing is available.</small></div>
              <select value={settings.cpu_limit_percent} onChange={(event) => void saveSettings({ cpu_limit_percent: Number(event.target.value) })}>
                {[50, 60, 70, 75, 80, 90].map((value) => <option key={value} value={value}>{value}%</option>)}
              </select>
            </div>
            <div className="setting-control-row">
              <div className="setting-control-copy"><strong>Transcription model</strong><small>First use downloads it; transcription runs locally on CPU.</small></div>
              <select value={settings.transcription_model} onChange={(event) => void saveSettings({ transcription_model: event.target.value as Settings["transcription_model"] })}>
                <option value="tiny">Tiny · fastest</option><option value="base">Base · balanced</option><option value="small">Small · more accurate</option>
              </select>
            </div>
            <div className="settings-footnote"><Cpu size={14} /> Transcription uses CPU int8 to leave the 4 GB GPU available to the desktop and local LLM.</div>
          </section>

          <section className="surface-card settings-card control-card">
            <div className="settings-card-heading"><div className="settings-card-icon amber"><Pause size={16} /></div><div><h3>Processing controls</h3><p>Pause future jobs or stop all automated activity immediately.</p></div></div>
            <ToggleRow title="Pause processing" detail="Keep queued work from starting." checked={settings.processing_paused} onChange={(checked) => void saveSettings({ processing_paused: checked })} icon={settings.processing_paused ? Play : Pause} />
            <ToggleRow title="Emergency stop" detail="Block processing and publishing until resumed." checked={settings.emergency_stop} onChange={(checked) => void saveSettings({ emergency_stop: checked })} icon={SquareStop} danger />
          </section>
        </div>

        <div className="settings-side-column">
          <section className="surface-card system-detail-card">
            <div className="section-header"><div><div className="section-overline">DETECTED HARDWARE</div><h3>System health</h3></div><span className="live-label"><i /> Live</span></div>
            {!system ? <div className="system-loading"><LoaderCircle size={17} className="spin" /> Checking system…</div> : <div className="system-detail-list">
              <SystemDetail icon={Cpu} label="Processor" value={system.cpu.name} />
              <SystemDetail icon={Activity} label="Memory" value={`${formatBytes(system.memory.available_bytes)} available of ${formatBytes(system.memory.total_bytes)}`} meter={system.memory.percent_used} />
              <SystemDetail icon={HardDrive} label="Free disk" value={formatBytes(system.disk.free_bytes)} />
              <SystemDetail icon={Clapperboard} label="FFmpeg" value={system.media_tools.ffmpeg_version ?? "Not detected"} ready={Boolean(system.media_tools.ffmpeg_version)} />
              <SystemDetail icon={Activity} label="Transcription" value={system.transcription_package_installed ? "faster-whisper installed" : "faster-whisper not installed"} ready={system.transcription_package_installed} />
              <SystemDetail icon={Zap} label="Graphics" value={system.gpu.name ?? "Not detected"} ready={system.gpu.available} />
              <SystemDetail icon={Sparkles} label="Ollama" value={system.ollama.online ? (system.ollama.model_available ? `${system.ollama.model_configured} ready` : "Service online · model missing") : "Service offline"} ready={system.ollama.online && system.ollama.model_available} />
            </div>}
            <div className="system-detail-footer"><span>Python {system?.python_version ?? "—"}</span><span>{system?.cpu.logical_processors ?? "—"} logical cores</span></div>
          </section>

          <section className="surface-card storage-card">
            <div className="storage-heading"><div className="settings-card-icon green"><HardDrive size={16} /></div><div><h3>Local storage</h3><p>App data and generated clips</p></div></div>
            <div className="storage-path" title={system?.data_directory}>{system?.data_directory ?? "Checking storage path…"}</div>
            <div className="storage-foot"><span><span className="storage-dot" />Originals stay in place</span><span>{formatBytes(system?.disk.free_bytes)} free</span></div>
          </section>
        </div>
      </div>
    </>
  );
}

function ToggleRow({ title, detail, checked, onChange, icon: Icon, danger = false }: {
  title: string;
  detail: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  icon: typeof Pause;
  danger?: boolean;
}) {
  return (
    <div className="toggle-row">
      <div className={`toggle-icon ${danger ? "danger" : ""}`}><Icon size={15} /></div>
      <div className="setting-control-copy"><strong>{title}</strong><small>{detail}</small></div>
      <button className={`switch ${checked ? "on" : ""} ${danger && checked ? "danger-on" : ""}`} role="switch" aria-checked={checked} aria-label={title} onClick={() => onChange(!checked)}><span /></button>
    </div>
  );
}

function SystemDetail({ icon: Icon, label, value, ready, meter }: {
  icon: typeof Cpu;
  label: string;
  value: string;
  ready?: boolean;
  meter?: number;
}) {
  return (
    <div className="system-detail-row">
      <div className="system-detail-icon"><Icon size={15} /></div>
      <div className="system-detail-copy"><span>{label}</span><strong title={value}>{value}</strong>{meter != null && <div className="memory-meter"><span style={{ width: `${meter}%` }} /></div>}</div>
      {ready != null && <span className={`detail-status ${ready ? "ok" : "missing"}`} />}
    </div>
  );
}

export default App;
