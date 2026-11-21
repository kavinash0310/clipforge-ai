import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Check,
  CalendarClock,
  ChevronDown,
  Clock3,
  CircleHelp,
  Clapperboard,
  Cpu,
  Download,
  ExternalLink,
  Film,
  Gauge,
  HardDrive,
  Layers3,
  Link2,
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
  Unlink,
  WandSparkles,
  Zap,
} from "lucide-react";

type Page = "overview" | "media" | "youtube" | "settings";
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
  processing_schedule_enabled: boolean;
  processing_schedule_start: string;
  processing_schedule_end: string;
  processing_schedule_days: number[];
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
  clip_id?: string | null;
};
type SubtitleSegment = { start: number; end: number; text: string };
type MetadataTone = "hype" | "funny" | "clean" | "competitive";
type ClipMetadataForm = {
  game_name: string;
  tone: MetadataTone;
  title: string;
  description: string;
  hashtags: string[];
  tags: string[];
};
type ClipMetadata = ClipMetadataForm & {
  clip_id: string;
  provider: string | null;
  model_name: string | null;
  status: string;
  generation_note: string | null;
  error_message: string | null;
  updated_at: string | null;
};
type Clip = {
  id: string;
  recording_id: string;
  recording_name: string;
  title: string;
  score: number;
  start_seconds: number;
  end_seconds: number;
  reasons: string[];
  signals: { audio_energy: number; speech_density: number; excitement_cues: number; scene_changes: number };
  subtitles: SubtitleSegment[];
  status: string;
  preview_url: string | null;
  render_metadata: { duration_seconds?: number; width?: number; height?: number; codec?: string };
  rendered_at: string | null;
  upload_title: string;
  upload_description: string;
  upload_hashtags: string[];
  upload_tags: string[];
  upload_metadata_status: string;
};
type YouTubeConnection = {
  configured: boolean;
  connected: boolean;
  status: string;
  error: string | null;
  client_secrets_path: string;
};
type YouTubePublication = {
  id: string;
  clip_id: string;
  job_id: string | null;
  remote_id: string | null;
  privacy_status: string;
  status: string;
  progress: number;
  analytics: { views?: number; likes?: number; comments?: number; shares?: number };
  analytics_updated_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  scheduled_at: string | null;
  clip_title: string;
  upload_title: string | null;
  video_url: string | null;
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
    subtitles: SubtitleSegment[];
    render_metadata: Clip["render_metadata"];
    rendered_at: string | null;
    status: string;
  }>;
};

const navItems = [
  { label: "Overview", icon: Layers3, page: "overview" as const },
  { label: "Media library", icon: MonitorPlay, page: "media" as const },
  { label: "YouTube", icon: Upload, page: "youtube" as const },
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

function localDateTimeInput(minutesFromNow = 15) {
  const minute = 60_000;
  const date = new Date(Math.ceil((Date.now() + minutesFromNow * minute) / minute) * minute);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
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
          <div className="workflow-item"><span className="workflow-number">03</span><span>Prepare and publish</span><span className="workflow-dot" /></div>
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
              <div className="breadcrumb"><span>CLIPFORGE AI</span><span className="crumb-divider">/</span><span>{page === "overview" ? "OVERVIEW" : page === "media" ? "MEDIA LIBRARY" : page === "youtube" ? "YOUTUBE" : "SETTINGS"}</span></div>
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
                <StatCard title="Published" value={overview?.published_total} icon={Upload} tone="green" loading={loading} foot="Completed uploads tracked here" />
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
          ) : page === "youtube" ? (
            <YouTubePage onRefresh={() => void loadDashboard(true)} />
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
  const [clips, setClips] = useState<Clip[]>([]);
  const [path, setPath] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [clipCount, setClipCount] = useState(1);
  const [clipDuration, setClipDuration] = useState(30);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RecordingAnalysis | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [captionDraft, setCaptionDraft] = useState<SubtitleSegment[]>([]);
  const [clipBusy, setClipBusy] = useState(false);
  const [metadata, setMetadata] = useState<ClipMetadata | null>(null);
  const [metadataForm, setMetadataForm] = useState<ClipMetadataForm>({ game_name: "", tone: "hype", title: "", description: "", hashtags: [], tags: [] });
  const [metadataBusy, setMetadataBusy] = useState(false);
  const metadataDirty = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const [nextRecordings, nextJobs, nextClips] = await Promise.all([
        api<Recording[]>("/api/recordings"),
        api<QueueJob[]>("/api/jobs"),
        api<Clip[]>("/api/clips"),
      ]);
      setRecordings(nextRecordings);
      setJobs(nextJobs);
      setClips(nextClips);
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

  useEffect(() => {
    if (!selectedClipId) {
      setMetadata(null);
      return;
    }
    let cancelled = false;
    metadataDirty.current = false;
    setMetadata(null);
    const loadMetadata = async () => {
      try {
        const next = await api<ClipMetadata>(`/api/clips/${encodeURIComponent(selectedClipId)}/metadata`);
        if (cancelled) return;
        setMetadata(next);
        if (!metadataDirty.current) {
          setMetadataForm({ game_name: next.game_name, tone: next.tone, title: next.title, description: next.description, hashtags: next.hashtags, tags: next.tags });
        }
      } catch (reason) {
        if (!cancelled) setPageError(reason instanceof Error ? reason.message : "Metadata could not be loaded.");
      }
    };
    void loadMetadata();
    const timer = window.setInterval(() => void loadMetadata(), 3000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [selectedClipId]);

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
      const result = await api<{ id: string; existing: boolean }>(`/api/recordings/${encodeURIComponent(recording.id)}/analyze`, {
        method: "POST",
        body: JSON.stringify({ clip_count: clipCount, clip_duration_seconds: clipDuration }),
      });
      setMessage(result.existing ? "This recording is already in the analysis queue." : `ClipForge is looking for up to ${clipCount} highlights from ${recording.display_name}. It will caption, render, and draft metadata for each result.`);
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
    setSelectedClipId(null);
    setAnalysis(null);
    setPageError(null);
    try {
      setAnalysis(await api<RecordingAnalysis>(`/api/recordings/${encodeURIComponent(recordingId)}/analysis`));
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Analysis could not be loaded.");
    }
  };

  const selectedClip = clips.find((clip) => clip.id === selectedClipId) ?? null;
  const metadataWorking = Boolean(metadata && ["queued", "running", "generating", "paused"].includes(metadata.status));
  const metadataFormChanged = Boolean(metadata && JSON.stringify({
    game_name: metadataForm.game_name,
    tone: metadataForm.tone,
    title: metadataForm.title,
    description: metadataForm.description,
    hashtags: metadataForm.hashtags,
    tags: metadataForm.tags,
  }) !== JSON.stringify({
    game_name: metadata.game_name,
    tone: metadata.tone,
    title: metadata.title,
    description: metadata.description,
    hashtags: metadata.hashtags,
    tags: metadata.tags,
  }));
  const captionDraftChanged = selectedClip
    ? JSON.stringify(captionDraft) !== JSON.stringify(selectedClip.subtitles)
    : false;

  const editClip = (clip: Clip | RecordingAnalysis["candidates"][number]) => {
    setSelectedClipId(clip.id);
    setCaptionDraft(clip.subtitles.map((segment) => ({ ...segment })));
    metadataDirty.current = false;
    setPageError(null);
  };

  const updateMetadata = (patch: Partial<ClipMetadataForm>) => {
    metadataDirty.current = true;
    setMetadataForm((current) => ({ ...current, ...patch }));
  };

  const generateMetadata = async () => {
    if (!selectedClip) return;
    setMetadataBusy(true);
    setPageError(null);
    metadataDirty.current = false;
    try {
      const job = await api<{ id: string; status: string; existing: boolean }>(`/api/clips/${encodeURIComponent(selectedClip.id)}/metadata/generate`, {
        method: "POST",
        body: JSON.stringify({ game_name: metadataForm.game_name, tone: metadataForm.tone }),
      });
      setMetadata((current) => ({
        clip_id: selectedClip.id,
        game_name: metadataForm.game_name,
        tone: metadataForm.tone,
        title: current?.title ?? "",
        description: current?.description ?? "",
        hashtags: current?.hashtags ?? [],
        tags: current?.tags ?? [],
        provider: current?.provider ?? null,
        model_name: current?.model_name ?? null,
        generation_note: current?.generation_note ?? null,
        error_message: null,
        updated_at: current?.updated_at ?? null,
        status: job.status,
      }));
      setMessage(job.existing ? "Metadata generation is already in the queue." : "Metadata generation queued. It will use local Ollama when available, with an offline template fallback.");
      await refresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Metadata generation could not be queued.");
    } finally {
      setMetadataBusy(false);
    }
  };

  const saveMetadata = async () => {
    if (!selectedClip) return;
    setMetadataBusy(true);
    setPageError(null);
    try {
      const savedMetadata = await api<ClipMetadata>(`/api/clips/${encodeURIComponent(selectedClip.id)}/metadata`, {
        method: "PATCH",
        body: JSON.stringify(metadataForm),
      });
      metadataDirty.current = false;
      setMetadata(savedMetadata);
      setMetadataForm({ game_name: savedMetadata.game_name, tone: savedMetadata.tone, title: savedMetadata.title, description: savedMetadata.description, hashtags: savedMetadata.hashtags, tags: savedMetadata.tags });
      setMessage("Clip metadata saved locally.");
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Metadata could not be saved.");
    } finally {
      setMetadataBusy(false);
    }
  };

  const updateCaption = (index: number, key: keyof SubtitleSegment, value: string) => {
    setCaptionDraft((segments) => segments.map((segment, current) => current === index
      ? { ...segment, [key]: key === "text" ? value : Number(value) }
      : segment));
  };

  const saveCaptions = async () => {
    if (!selectedClip) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const updated = await api<Clip>(`/api/clips/${encodeURIComponent(selectedClip.id)}/subtitles`, {
        method: "PATCH",
        body: JSON.stringify({ segments: captionDraft }),
      });
      setCaptionDraft(updated.subtitles.map((segment) => ({ ...segment })));
      setMessage("Caption edits saved. Render the clip to refresh its preview.");
      await refresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Caption edits could not be saved.");
    } finally {
      setClipBusy(false);
    }
  };

  const renderClip = async () => {
    if (!selectedClip) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const job = await api<{ id: string | null; status: string; existing: boolean }>(`/api/clips/${encodeURIComponent(selectedClip.id)}/render`, {
        method: "POST",
        body: "{}",
      });
      setMessage(job.status === "rendered" ? "This candidate already has a rendered preview." : "Vertical render queued. The preview will appear when FFmpeg finishes.");
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The clip could not be queued for rendering.");
    } finally {
      setClipBusy(false);
    }
  };

  return (
    <>
      <section className="page-heading media-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> LOCAL SOURCE LIBRARY</div><h1>Media library<span className="heading-period">.</span></h1><p className="heading-subtitle">Add a local video to analyze moments and build captioned clips.</p></div>
        <button className="secondary-button" onClick={() => void refresh()}><RefreshCw size={14} /> Refresh library</button>
      </section>

      {pageError && <div className="error-banner media-error"><AlertTriangle size={17} /><span>{pageError}</span></div>}
      {message && <div className="success-banner"><Check size={16} /><span>{message}</span><button aria-label="Dismiss message" onClick={() => setMessage(null)}>×</button></div>}

      <section className="surface-card import-card">
        <div className="import-card-header">
          <div className="import-icon"><Upload size={18} /></div>
          <div><div className="section-overline">ADD LOCAL RECORDING</div><h3>Bring a session into your studio</h3><p>Choose a local file or paste its path. For your own YouTube uploads, <a href="https://studio.youtube.com" target="_blank" rel="noreferrer">download the MP4 in YouTube Studio</a>, then import it here. ClipForge does not download watch links.</p></div>
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

      <section className="surface-card clip-plan-card">
        <div className="clip-plan-copy"><div className="section-overline">AI CLIP SETTINGS</div><h3>Choose how many clips to create</h3><p>ClipForge ranks gameplay moments, prepares captions, renders vertical video, and drafts relevant upload metadata automatically.</p></div>
        <div className="clip-plan-fields">
          <label>Number of clips<input type="number" min={1} max={100} value={clipCount} onChange={(event) => setClipCount(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /></label>
          <label>Clip duration<select value={clipDuration} onChange={(event) => setClipDuration(Number(event.target.value))}><option value={15}>15 seconds</option><option value={30}>30 seconds</option><option value={45}>45 seconds</option></select></label>
        </div>
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
          <div className="candidate-section-heading"><div><div className="section-overline">AI SELECTED MOMENTS</div><h4>Candidate highlights</h4></div><span>Clips, captions, and metadata are prepared in the background. You can still edit each result.</span></div>
          {analysis.candidates.length ? <div className="candidate-list">{analysis.candidates.map((candidate, index) => {
            const excerpt = analysis.transcript?.segments.filter((segment) => segment.end > candidate.start_seconds && segment.start < candidate.end_seconds).slice(0, 5) ?? [];
            const currentClip = clips.find((clip) => clip.id === candidate.id) ?? candidate;
            return <article className="candidate-card" key={candidate.id}>
              <div className="candidate-rank">{String(index + 1).padStart(2, "0")}</div>
              <div className="candidate-body"><div className="candidate-topline"><h4>{candidate.title}</h4><span className="candidate-score">{candidate.score.toFixed(0)}<small>/100</small></span></div>
                <div className="candidate-meta"><span><Clapperboard size={12} /> {formatDuration(candidate.start_seconds)}–{formatDuration(candidate.end_seconds)}</span>{candidate.reasons.map((reason) => <span className="reason-chip" key={reason}>{reason}</span>)}</div>
                {excerpt.length ? <p className="candidate-excerpt">{excerpt.map((segment) => segment.text).join(" ")}</p> : <p className="candidate-excerpt muted-excerpt">No speech detected in this candidate window.</p>}
                <div className="candidate-actions"><span className={`clip-state clip-state-${currentClip.status}`}>{currentClip.status.replaceAll("_", " ")}</span><button className="row-action-button clip-edit-button" onClick={() => editClip(currentClip)}><Film size={12} /> Edit captions</button></div>
              </div>
              <div className="candidate-signals"><span>Audio <b>{Math.round(candidate.signals.audio_energy * 100)}%</b></span><span>Speech <b>{Math.round(candidate.signals.speech_density * 100)}%</b></span><span>Scene cuts <b>{candidate.signals.scene_changes}</b></span></div>
            </article>;
          })}</div> : <div className="no-candidates"><div className="empty-icon"><Sparkles size={18} /></div><div><strong>No clear highlight candidates found</strong><p>The recording was transcribed, but its audio, transcript, and scene signals did not pass the candidate threshold.</p></div></div>}
          {selectedClip && selectedClip.recording_id === selectedAnalysisId && <section className="clip-editor" id="clip-editor">
            <div className="clip-editor-heading"><div><div className="section-overline">CLIP EDITOR</div><h4>{selectedClip.title}</h4><p>{formatDuration(selectedClip.end_seconds - selectedClip.start_seconds)} clip · Vertical 1080 × 1920 · source remains unchanged</p></div><span className={`clip-state clip-state-${selectedClip.status}`}>{selectedClip.status.replaceAll("_", " ")}</span></div>
            <div className="clip-editor-grid">
              <div className="clip-preview-column">
                {selectedClip.preview_url ? <video className="clip-preview-video" controls preload="metadata" src={`${selectedClip.preview_url}?rendered=${encodeURIComponent(selectedClip.rendered_at ?? "latest")}`} /> : <div className="clip-preview-placeholder"><div className="empty-icon"><MonitorPlay size={19} /></div><strong>{selectedClip.status === "paused" ? "Render paused" : selectedClip.status === "rendering" || selectedClip.status === "queued" ? "Rendering your vertical clip" : "Preview appears after rendering"}</strong><p>FFmpeg fills the vertical frame with a blurred game backdrop and burns in the corrected captions.</p>{(selectedClip.status === "rendering" || selectedClip.status === "queued") && <LoaderCircle className="spin" size={16} />}</div>}
                {selectedClip.preview_url && <div className="clip-download-actions"><a className="secondary-button" href={`/api/clips/${encodeURIComponent(selectedClip.id)}/download`}><Upload size={13} /> Download MP4</a><a className="secondary-button" href={`/api/clips/${encodeURIComponent(selectedClip.id)}/subtitles`} download>Download clip SRT</a></div>}
                {jobs.find((job) => job.clip_id === selectedClip.id && job.status === "failed")?.error_message && <p className="clip-render-error"><AlertTriangle size={13} />{jobs.find((job) => job.clip_id === selectedClip.id && job.status === "failed")?.error_message}</p>}
              </div>
              <div className="clip-caption-editor">
                <div className="caption-editor-heading"><div><strong>Caption correction</strong><span>Times are relative to this clip.</span></div><button className="row-action-button" disabled={captionDraft.length >= 300 || clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || (captionDraft.length > 0 && captionDraft[captionDraft.length - 1].end >= selectedClip.end_seconds - selectedClip.start_seconds)} onClick={() => { const clipDuration = selectedClip.end_seconds - selectedClip.start_seconds; const start = captionDraft.length ? captionDraft[captionDraft.length - 1].end : 0; setCaptionDraft((segments) => [...segments, { start, end: Math.min(clipDuration, start + 2), text: "" }]); }}>Add line</button></div>
                {captionDraft.length ? <div className="caption-edit-list">{captionDraft.map((segment, index) => <div className="caption-edit-row" key={`${index}-${segment.start}`}>
                  <div className="caption-time-fields"><label>In<input aria-label={`Caption ${index + 1} start time`} type="number" min="0" max={selectedClip.end_seconds - selectedClip.start_seconds} step="0.1" value={segment.start} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => updateCaption(index, "start", event.target.value)} /></label><label>Out<input aria-label={`Caption ${index + 1} end time`} type="number" min="0.1" max={selectedClip.end_seconds - selectedClip.start_seconds} step="0.1" value={segment.end} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => updateCaption(index, "end", event.target.value)} /></label><button className="icon-button caption-remove" aria-label={`Remove caption ${index + 1}`} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => setCaptionDraft((segments) => segments.filter((_item, current) => current !== index))}>×</button></div>
                  <label className="sr-only" htmlFor={`caption-text-${index}`}>Caption text {index + 1}</label><textarea id={`caption-text-${index}`} maxLength={500} rows={2} value={segment.text} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => updateCaption(index, "text", event.target.value)} />
                </div>)}</div> : <div className="caption-empty">No speech was detected in this highlight. Add caption lines if needed.</div>}
                <div className="clip-editor-actions"><button className="secondary-button" disabled={!captionDraftChanged || clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => void saveCaptions()}>{clipBusy ? <LoaderCircle size={13} className="spin" /> : <Check size={13} />}{captionDraftChanged ? "Save captions" : "Captions saved"}</button><button className="primary-button" disabled={clipBusy || captionDraftChanged || ["queued", "rendering", "paused", "rendered"].includes(selectedClip.status)} onClick={() => void renderClip()}>{clipBusy ? <LoaderCircle size={13} className="spin" /> : selectedClip.status === "rendered" ? <Check size={13} /> : <Play size={13} />}{selectedClip.status === "rendered" ? "Rendered" : selectedClip.status === "paused" ? "Render paused" : selectedClip.status === "queued" || selectedClip.status === "rendering" ? "Rendering…" : "Render vertical clip"}</button></div>
                <section className="metadata-editor" aria-label="Clip metadata">
                <div className="metadata-editor-heading"><div><div className="section-overline">AI UPLOAD METADATA</div><strong>Title, description & relevant tags</strong><span>Generated from the gameplay context, ready for you to review and edit.</span></div><span className={`clip-state clip-state-${metadata?.status ?? "empty"}`}>{metadata?.status ?? "loading"}</span></div>
                  {!metadata ? <div className="metadata-loading"><LoaderCircle size={14} className="spin" /> Loading saved metadata…</div> : <>
                    <div className="metadata-context-row"><label>Game or category<input maxLength={80} value={metadataForm.game_name} disabled={metadataWorking || metadataBusy} onChange={(event) => updateMetadata({ game_name: event.target.value })} placeholder="e.g. Valorant" /></label><label>Tone<select value={metadataForm.tone} disabled={metadataWorking || metadataBusy} onChange={(event) => updateMetadata({ tone: event.target.value as MetadataTone })}><option value="hype">Hype</option><option value="funny">Funny</option><option value="clean">Clean</option><option value="competitive">Competitive</option></select></label><button className="secondary-button metadata-generate-button" disabled={metadataBusy || metadataWorking} onClick={() => void generateMetadata()}>{metadataBusy ? <LoaderCircle size={13} className="spin" /> : <Sparkles size={13} />}{metadataWorking ? "Generating…" : "Generate metadata"}</button></div>
                    {metadata.error_message && <p className="clip-render-error"><AlertTriangle size={13} />{metadata.error_message}</p>}
                    {metadata.generation_note && <p className="metadata-note">{metadata.provider === "ollama" ? <Sparkles size={12} /> : <CircleHelp size={12} />}{metadata.generation_note}{metadata.model_name ? ` · ${metadata.model_name}` : ""}</p>}
                    <label className="metadata-field">Title<input maxLength={100} value={metadataForm.title} disabled={metadataWorking || metadataBusy} onChange={(event) => updateMetadata({ title: event.target.value })} placeholder="Generated title" /></label>
                    <label className="metadata-field">Description<textarea rows={4} maxLength={5000} value={metadataForm.description} disabled={metadataWorking || metadataBusy} onChange={(event) => updateMetadata({ description: event.target.value })} placeholder="Generated description" /></label>
                    <label className="metadata-field">Hashtags<input value={metadataForm.hashtags.join(", ")} disabled={metadataWorking || metadataBusy} onChange={(event) => updateMetadata({ hashtags: event.target.value.split(",").map((tag) => tag.trim()).filter(Boolean) })} placeholder="#gaming, #shorts" /></label>
                    <label className="metadata-field">Search tags<input value={metadataForm.tags.join(", ")} disabled={metadataWorking || metadataBusy} onChange={(event) => updateMetadata({ tags: event.target.value.split(",").map((tag) => tag.trim()).filter(Boolean) })} placeholder="gameplay, match highlight" /></label>
                    <div className="metadata-editor-actions"><span>{metadata.generation_note ?? "Metadata stays local and can be edited at any time."}</span><button className="primary-button" disabled={metadataBusy || metadataWorking || !metadataForm.title.trim() || !metadataFormChanged && metadata.status !== "empty"} onClick={() => void saveMetadata()}>{metadataBusy ? <LoaderCircle size={13} className="spin" /> : <Check size={13} />}{metadata.status === "empty" ? "Save metadata" : "Save edits"}</button></div>
                  </>}
                </section>
              </div>
            </div>
          </section>}
          <details className="full-transcript"><summary>Full transcript <span>{analysis.transcript?.segments.length ?? 0} segments</span></summary>{analysis.transcript?.segments.length ? <div className="transcript-list">{analysis.transcript.segments.map((segment, index) => <div className="transcript-line" key={`${segment.start}-${index}`}><time>{formatDuration(segment.start)}</time><span>{segment.text}</span></div>)}</div> : <p className="transcript-empty">No speech was recognized in this recording.</p>}</details>
        </>}
      </section>}
    </>
  );
}

function YouTubePage({ onRefresh }: { onRefresh: () => void }) {
  const [connection, setConnection] = useState<YouTubeConnection | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [publications, setPublications] = useState<YouTubePublication[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [scheduleAt, setScheduleAt] = useState(() => localDateTimeInput(15));
  const [minimumScheduleAt] = useState(() => localDateTimeInput(15));
  const [scheduleInterval, setScheduleInterval] = useState(90);
  const [analyticsUpdatedAt, setAnalyticsUpdatedAt] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [status, nextClips, nextPublications] = await Promise.all([
        api<YouTubeConnection>("/api/youtube/status"),
        api<Clip[]>("/api/clips"),
        api<YouTubePublication[]>("/api/youtube/publications"),
      ]);
      setConnection(status);
      setClips(nextClips);
      setPublications(nextPublications);
      setPageError(status.error);
      if (nextPublications.some((item) => item.analytics_updated_at)) {
        setAnalyticsUpdatedAt(nextPublications.find((item) => item.analytics_updated_at)?.analytics_updated_at ?? null);
      }
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "YouTube status could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const connect = async () => {
    const authWindow = window.open("about:blank", "_blank", "popup,width=560,height=760");
    if (!authWindow) {
      setPageError("Allow the YouTube sign-in window to open, then try again.");
      return;
    }
    authWindow.opener = null;
    setWorking("connect");
    setPageError(null);
    try {
      const result = await api<{ authorization_url: string }>("/api/youtube/connect", { method: "POST" });
      authWindow.location.replace(result.authorization_url);
      setMessage("Complete Google account access in the browser window. ClipForge will update when it returns.");
      await refresh();
    } catch (reason) {
      authWindow.close();
      setPageError(reason instanceof Error ? reason.message : "YouTube could not be connected.");
    } finally {
      setWorking(null);
    }
  };

  const disconnect = async () => {
    setWorking("disconnect");
    setPageError(null);
    try {
      const next = await api<YouTubeConnection>("/api/youtube/connect", { method: "DELETE" });
      setConnection(next);
      setMessage("YouTube account disconnected. Saved publication history remains on this device.");
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The YouTube account could not be disconnected.");
    } finally {
      setWorking(null);
    }
  };

  const upload = async (clip: Clip) => {
    setWorking(clip.id);
    setPageError(null);
    setMessage(null);
    try {
      const result = await api<{ id: string | null; status: string; existing: boolean }>(`/api/clips/${encodeURIComponent(clip.id)}/youtube-upload`, { method: "POST" });
      setMessage(result.existing ? "This clip already has a YouTube publication record." : "Private YouTube upload queued.");
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The YouTube upload could not be queued.");
    } finally {
      setWorking(null);
    }
  };

  const schedule = async (items: Clip[]) => {
    if (!items.length) return;
    const startAt = new Date(scheduleAt);
    if (Number.isNaN(startAt.valueOf())) {
      setPageError("Choose a valid schedule date and time.");
      return;
    }
    setWorking("schedule");
    setPageError(null);
    setMessage(null);
    try {
      let queued = 0;
      for (let offset = 0; offset < items.length; offset += 100) {
        const batch = items.slice(offset, offset + 100);
        const batchStart = new Date(startAt.valueOf() + offset * scheduleInterval * 60_000);
        const result = await api<{ scheduled: Array<{ status: string }>; interval_minutes: number }>("/api/youtube/schedule", {
          method: "POST",
          body: JSON.stringify({
            clip_ids: batch.map((clip) => clip.id),
            start_at: batchStart.toISOString(),
            interval_minutes: scheduleInterval,
          }),
        });
        queued += result.scheduled.filter((item) => !["complete", "failed"].includes(item.status)).length;
      }
      setMessage(`${queued} ${queued === 1 ? "video" : "videos"} scheduled. Batch spacing: ${scheduleInterval} minutes.`);
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The YouTube schedule could not be created.");
    } finally {
      setWorking(null);
    }
  };

  const downloadAll = async () => {
    if (!renderedClips.length) return;
    setWorking("download-all");
    setPageError(null);
    try {
      const response = await fetch("/api/clips/download-all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clip_ids: renderedClips.map((clip) => clip.id) }),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(error?.detail ?? `Download failed (${response.status})`);
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "clipforge-clips.zip";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setMessage(`${renderedClips.length} rendered clips downloaded as a ZIP file.`);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The clip bundle could not be downloaded.");
    } finally {
      setWorking(null);
    }
  };

  const retry = async (publication: YouTubePublication) => {
    if (!publication.job_id) return;
    setWorking(publication.id);
    setPageError(null);
    try {
      await api(`/api/jobs/${encodeURIComponent(publication.job_id)}/retry`, { method: "POST" });
      setMessage("The existing upload session was queued to resume. ClipForge will not create a second publication for this clip.");
      await refresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The upload could not be retried.");
    } finally {
      setWorking(null);
    }
  };

  const refreshAnalytics = async () => {
    setWorking("analytics");
    setPageError(null);
    try {
      const result = await api<{ publications: YouTubePublication[]; refreshed_at: string }>("/api/youtube/analytics/refresh", { method: "POST" });
      setPublications(result.publications);
      setAnalyticsUpdatedAt(result.refreshed_at);
      setMessage("Channel analytics refreshed for the latest available 28-day period.");
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "YouTube analytics could not be refreshed.");
    } finally {
      setWorking(null);
    }
  };

  const publicationByClip = new Map(publications.map((item) => [item.clip_id, item]));
  const renderedClips = clips.filter((clip) => clip.status === "rendered" && clip.preview_url);
  const publishableClips = renderedClips.filter((clip) => clip.upload_metadata_status === "complete" && !publicationByClip.has(clip.id));
  const isConnected = Boolean(connection?.connected);
  const completed = publications.filter((item) => item.status === "complete" && (!item.scheduled_at || Date.parse(item.scheduled_at) <= Date.now()));
  const totals = completed.reduce((value, item) => ({
    views: value.views + (item.analytics.views ?? 0),
    likes: value.likes + (item.analytics.likes ?? 0),
    comments: value.comments + (item.analytics.comments ?? 0),
    shares: value.shares + (item.analytics.shares ?? 0),
  }), { views: 0, likes: 0, comments: 0, shares: 0 });

  return (
    <>
      <section className="page-heading youtube-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> CHANNEL CONNECTION</div><h1>YouTube<span className="heading-period">.</span></h1><p className="heading-subtitle">Download rendered clips or upload and schedule them on your channel.</p></div>
        <span className={`youtube-state ${isConnected ? "connected" : "disconnected"}`}><span />{loading ? "Checking" : isConnected ? "Connected" : "Not connected"}</span>
      </section>

      {pageError && <div className="youtube-feedback error"><AlertTriangle size={14} /><span>{pageError}</span></div>}
      {message && <div className="youtube-feedback success"><Check size={14} /><span>{message}</span></div>}

      <section className="surface-card youtube-connect-card">
        <div className="youtube-connect-copy"><div className="youtube-connect-icon"><Upload size={18} /></div><div><div className="section-overline">YOUTUBE PUBLISHING</div><h3>{isConnected ? "Connected to YouTube" : "Connect your channel"}</h3><p>{isConnected ? "Scheduled videos stay private until YouTube publishes them at the chosen date and time. Immediate uploads remain private." : "Link your Google account using OAuth in your system browser. ClipForge stores refresh tokens protected with Windows DPAPI."}</p>{connection?.error && <small className="youtube-error-detail">{connection.error}</small>}</div></div>
        <div className="youtube-connect-actions">
          {isConnected ? <button className="secondary-button" disabled={working !== null} onClick={() => void disconnect()}>{working === "disconnect" ? <LoaderCircle size={13} className="spin" /> : <Unlink size={13} />}Disconnect</button> : <button className="primary-button" disabled={working !== null || !connection?.configured} onClick={() => void connect()}>{working === "connect" ? <LoaderCircle size={13} className="spin" /> : <Link2 size={13} />}Connect YouTube</button>}
          {connection?.status === "pending" && <span className="youtube-pending"><LoaderCircle size={13} className="spin" />Waiting for Google…</span>}
        </div>
        {!connection?.configured && <div className="youtube-setup-note"><CircleHelp size={14} /><span>Add a Google Desktop OAuth client JSON file here: <code>{connection?.client_secrets_path ?? "%LOCALAPPDATA%\\ClipForgeAI\\client_secrets.json"}</code>. Enable YouTube Data API v3 and YouTube Analytics API in that Google Cloud project.</span><a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer">Google Cloud credentials <ExternalLink size={12} /></a></div>}
        {connection?.configured && !isConnected && <div className="youtube-setup-note"><ShieldCheck size={14} /><span>Google consent is required for channel upload and analytics access. ClipForge requests only YouTube upload, read, and analytics scopes.</span><a href="https://developers.google.com/identity/protocols/oauth2/native-app" target="_blank" rel="noreferrer">Desktop OAuth guide <ExternalLink size={12} /></a></div>}
      </section>

      <section className="surface-card youtube-schedule-card">
        <div className="youtube-schedule-copy"><div className="section-overline">PUBLISH SCHEDULE</div><h3>Choose when videos go live</h3><p>One video defaults to 15 minutes from now. For a batch, the first video uses this time and each next video is spaced by your interval.</p></div>
        <div className="youtube-schedule-fields">
          <label>Start date and time<input type="datetime-local" value={scheduleAt} min={minimumScheduleAt} onChange={(event) => setScheduleAt(event.target.value)} /></label>
          <label>Batch interval<select value={scheduleInterval} onChange={(event) => setScheduleInterval(Number(event.target.value))}><option value={15}>15 minutes</option><option value={30}>30 minutes</option><option value={60}>1 hour</option><option value={90}>1.5 hours</option><option value={120}>2 hours</option><option value={360}>6 hours</option><option value={1440}>1 day</option></select></label>
          <button className="primary-button" disabled={!isConnected || working !== null || publishableClips.length === 0} onClick={() => void schedule(publishableClips)}>{working === "schedule" ? <LoaderCircle size={13} className="spin" /> : <CalendarClock size={13} />}Schedule all ready</button>
        </div>
      </section>

      <section className="surface-card youtube-clips-card">
        <div className="section-header"><div><div className="section-overline">READY TO UPLOAD</div><h3>Rendered clips</h3></div><div className="youtube-list-actions"><span className="youtube-subtle-count">{publishableClips.length} ready · {renderedClips.length} rendered</span><button className="secondary-button" disabled={working !== null || renderedClips.length === 0} onClick={() => void downloadAll()}>{working === "download-all" ? <LoaderCircle size={13} className="spin" /> : <Download size={13} />}Download all</button></div></div>
        {loading ? <div className="loading-state"><LoaderCircle className="spin" size={18} /> Loading rendered clips…</div> : renderedClips.length ? <div className="youtube-clips-list">{renderedClips.map((clip) => {
          const publication = publicationByClip.get(clip.id);
          const busy = publication && ["queued", "uploading", "paused"].includes(publication.status);
          return <article className="youtube-clip-row" key={clip.id}>
            <div className="youtube-clip-mark"><Film size={17} /></div>
            <div className="youtube-clip-copy"><strong>{clip.upload_title || clip.title}</strong><span>{clip.recording_name} · {formatDuration(clip.render_metadata.duration_seconds)} · {clip.upload_metadata_status === "complete" ? "AI metadata ready" : "Preparing metadata"}</span>{publication?.scheduled_at && <span>Scheduled for {new Date(publication.scheduled_at).toLocaleString()}</span>}{publication?.status === "uploading" && <div className="youtube-progress"><span style={{ width: `${Math.max(0, Math.min(publication.progress, 100))}%` }} /></div>}{publication?.status === "failed" && <small className="youtube-error-detail">{publication.error_message || "Upload failed."}</small>}</div>
            <div className="youtube-clip-action">
              <a className="secondary-button" href={`/api/clips/${encodeURIComponent(clip.id)}/download`}><Download size={13} />Download</a>
              {publication?.status === "complete" ? <a className="secondary-button" href={publication.video_url ?? undefined} target="_blank" rel="noreferrer">{publication.scheduled_at && Date.parse(publication.scheduled_at) > Date.now() ? "Scheduled" : "Uploaded privately"}<ExternalLink size={12} /></a> : publication?.status === "failed" ? <button className="secondary-button" disabled={working !== null || !isConnected} onClick={() => void retry(publication)}>{working === publication.id ? <LoaderCircle size={13} className="spin" /> : <RefreshCw size={13} />}Retry upload</button> : publication ? <span className={`clip-state clip-state-${publication.status}`}>{busy ? <LoaderCircle size={12} className="spin" /> : null}{publication.status.replaceAll("_", " ")}{publication.status === "uploading" ? ` ${Math.round(publication.progress)}%` : ""}</span> : <><button className="secondary-button" disabled={!isConnected || working !== null || clip.upload_metadata_status !== "complete"} onClick={() => void upload(clip)}>{working === clip.id ? <LoaderCircle size={13} className="spin" /> : <Upload size={13} />}Upload privately</button><button className="primary-button" disabled={!isConnected || working !== null || clip.upload_metadata_status !== "complete"} onClick={() => void schedule([clip])}>{working === "schedule" ? <LoaderCircle size={13} className="spin" /> : <CalendarClock size={13} />}Schedule</button></>}
            </div>
          </article>;
        })}</div> : <div className="youtube-empty"><div className="empty-icon"><Film size={18} /></div><div><strong>No rendered clips yet</strong><p>Render a candidate in Media library to make it available for a private upload.</p></div></div>}
      </section>

      <section className="surface-card youtube-analytics-card">
        <div className="section-header"><div><div className="section-overline">CHANNEL ANALYTICS</div><h3>Recent performance</h3></div><button className="text-button" disabled={!isConnected || working !== null || completed.length === 0} onClick={() => void refreshAnalytics()}>{working === "analytics" ? <LoaderCircle size={13} className="spin" /> : <RefreshCw size={13} />}Refresh analytics</button></div>
        <p className="youtube-analytics-caption">Latest available 28-day channel report; analytics can lag behind recent views.</p>
        {completed.length > 0 && <div className="youtube-metric-grid"><Metric value={totals.views} label="Views" /><Metric value={totals.likes} label="Likes" /><Metric value={totals.comments} label="Comments" /><Metric value={totals.shares} label="Shares" /></div>}
        {completed.length > 0 ? <div className="youtube-publication-list">{completed.map((publication) => <article className="youtube-publication-row" key={publication.id}><div className="youtube-publication-icon"><BarChart3 size={15} /></div><div className="youtube-publication-copy"><strong>{publication.upload_title || publication.clip_title}</strong><span>Uploaded video · {publication.remote_id}</span></div><div className="youtube-publication-metrics"><span>{(publication.analytics.views ?? 0).toLocaleString()} views</span><span>{(publication.analytics.likes ?? 0).toLocaleString()} likes</span><span>{(publication.analytics.comments ?? 0).toLocaleString()} comments</span></div><span className="youtube-updated">{publication.analytics_updated_at ? `Updated ${formatDate(publication.analytics_updated_at)}` : "Not refreshed"}</span></article>)}</div> : <div className="youtube-empty"><div className="empty-icon"><BarChart3 size={18} /></div><div><strong>No YouTube analytics yet</strong><p>Uploaded clips will appear here when YouTube has report data.</p></div></div>}
        {analyticsUpdatedAt && <div className="youtube-analytics-foot">Last refreshed {formatDate(analyticsUpdatedAt)} · {completed.length} private uploads</div>}
      </section>
    </>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return <div className="youtube-metric"><strong>{value.toLocaleString()}</strong><span>{label}</span></div>;
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
                ["manual", "Manual", "You start each processing step."],
                ["semi_automatic", "Semi-automatic", "Prepare clips and metadata automatically."],
                ["automatic", "Automatic", "Follow configured local processing settings."],
              ] as const).map(([value, label, description]) => (
                <button key={value} className={`mode-option ${settings.automation_mode === value ? "selected" : ""}`} onClick={() => void saveSettings({ automation_mode: value })}>
                  <span className="radio-dot" /><span className="mode-copy"><strong>{label}</strong><small>{description}</small></span>{settings.automation_mode === value && <Check size={15} className="mode-check" />}
                </button>
              ))}
            </div>
            <div className="settings-note"><ShieldCheck size={15} /><span>YouTube uploads are always private in this release.</span></div>
          </section>

          <section className="surface-card settings-card">
            <div className="settings-card-heading"><div className="settings-card-icon blue"><Gauge size={17} /></div><div><h3>Resource limits</h3><p>Keep local processing responsive while other apps are open.</p></div></div>
            <div className="setting-control-row">
              <div className="setting-control-copy"><strong>Maximum concurrent jobs</strong><small>Overall worker slots; CPU-heavy jobs still run one at a time.</small></div>
              <select value={settings.max_concurrent_jobs} onChange={(event) => void saveSettings({ max_concurrent_jobs: Number(event.target.value) })}>
                {[1, 2, 3, 4].map((value) => <option key={value} value={value}>{value} {value === 1 ? "job" : "jobs"}</option>)}
              </select>
            </div>
            <div className="setting-control-row">
              <div className="setting-control-copy"><strong>CPU thread budget</strong><small>Limits parallel threads used by transcription and FFmpeg.</small></div>
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
            <div className="settings-footnote"><Cpu size={14} /> Thread counts are a practical resource target, not a hard operating-system CPU cap. Transcription uses CPU int8.</div>
          </section>

          <section className="surface-card settings-card schedule-card">
            <div className="settings-card-heading"><div className="settings-card-icon green"><Clock3 size={16} /></div><div><h3>Processing schedule</h3><p>Choose when queued jobs may start on this device.</p></div></div>
            <ToggleRow title="Use a weekly schedule" detail="Jobs wait in the queue outside the selected window." checked={settings.processing_schedule_enabled} onChange={(checked) => void saveSettings({ processing_schedule_enabled: checked })} icon={Clock3} />
            <div className={`schedule-controls ${settings.processing_schedule_enabled ? "" : "disabled"}`}>
              <div className="schedule-time-grid">
                <label><span>Start</span><input type="time" value={settings.processing_schedule_start} disabled={!settings.processing_schedule_enabled} onChange={(event) => void saveSettings({ processing_schedule_start: event.target.value })} /></label>
                <label><span>End</span><input type="time" value={settings.processing_schedule_end} disabled={!settings.processing_schedule_enabled} onChange={(event) => void saveSettings({ processing_schedule_end: event.target.value })} /></label>
              </div>
              <div className="schedule-days-heading"><strong>Active days</strong><small>Uses this computer’s local time ({Intl.DateTimeFormat().resolvedOptions().timeZone || "local timezone"}).</small></div>
              <div className="schedule-days" aria-label="Scheduled weekdays">
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => {
                  const selected = settings.processing_schedule_days.includes(index);
                  return <button key={day} type="button" className={selected ? "selected" : ""} aria-pressed={selected} disabled={!settings.processing_schedule_enabled || (selected && settings.processing_schedule_days.length === 1)} onClick={() => {
                    const days = selected ? settings.processing_schedule_days.filter((value) => value !== index) : [...settings.processing_schedule_days, index];
                    void saveSettings({ processing_schedule_days: days.sort((a, b) => a - b) });
                  }}>{day}</button>;
                })}
              </div>
            </div>
            <div className="settings-footnote"><Clock3 size={14} /> An end time earlier than the start time runs overnight. Equal times mean the full selected day.</div>
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
