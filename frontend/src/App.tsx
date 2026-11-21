import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent, type PointerEvent } from "react";
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
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Star,
  SquareStop,
  Upload,
  Unlink,
  Zap,
} from "lucide-react";

const TRANSCRIPTION_LANGUAGE_OPTIONS = [
  ["auto", "Auto detect"], ["hinglish", "Hinglish · Hindi in English letters"], ["hi", "Hindi · हिंदी"], ["en", "English"],
  ["ur", "Urdu · اردو"], ["bn", "Bengali · বাংলা"], ["ta", "Tamil · தமிழ்"], ["te", "Telugu · తెలుగు"], ["mr", "Marathi · मराठी"],
  ["gu", "Gujarati · ગુજરાતી"], ["kn", "Kannada · ಕನ್ನಡ"], ["ml", "Malayalam · മലയാളം"], ["pa", "Punjabi · ਪੰਜਾਬੀ"],
  ["ne", "Nepali · नेपाली"], ["si", "Sinhala · සිංහල"], ["ar", "Arabic · العربية"], ["fa", "Persian · فارسی"],
  ["he", "Hebrew · עברית"], ["tr", "Turkish · Türkçe"], ["ru", "Russian · Русский"], ["uk", "Ukrainian · Українська"],
  ["pl", "Polish · Polski"], ["cs", "Czech · Čeština"], ["sk", "Slovak · Slovenčina"], ["hu", "Hungarian · Magyar"],
  ["ro", "Romanian · Română"], ["bg", "Bulgarian · Български"], ["sr", "Serbian · Српски"], ["hr", "Croatian · Hrvatski"],
  ["el", "Greek · Ελληνικά"], ["de", "German · Deutsch"], ["fr", "French · Français"], ["es", "Spanish · Español"],
  ["pt", "Portuguese · Português"], ["it", "Italian · Italiano"], ["nl", "Dutch · Nederlands"], ["ca", "Catalan · Català"],
  ["sv", "Swedish · Svenska"], ["da", "Danish · Dansk"], ["no", "Norwegian · Norsk"], ["fi", "Finnish · Suomi"],
  ["is", "Icelandic · Íslenska"], ["id", "Indonesian · Bahasa Indonesia"], ["ms", "Malay · Bahasa Melayu"],
  ["tl", "Filipino · Tagalog"], ["vi", "Vietnamese · Tiếng Việt"], ["th", "Thai · ไทย"], ["zh", "Chinese · 中文"],
  ["ja", "Japanese · 日本語"], ["ko", "Korean · 한국어"], ["sw", "Swahili · Kiswahili"], ["af", "Afrikaans"],
  ["am", "Amharic · አማርኛ"], ["az", "Azerbaijani · Azərbaycan"],
] as const;
type TranscriptionLanguage = typeof TRANSCRIPTION_LANGUAGE_OPTIONS[number][0];
type Page = "overview" | "media" | "clips" | "youtube" | "live" | "settings";
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
type FrameRegion = { x: number; y: number; width: number; height: number };
type FrameRegionKey = "gameplay_box" | "facecam_box";
type SourceViewport = { left: number; top: number; width: number; height: number; stageWidth: number; stageHeight: number };
type FramingPreset = { name: string; layout: RenderOptions["layout"]; gameplay_box: FrameRegion | null; facecam_box: FrameRegion | null; facecam_position: RenderOptions["facecam_position"]; facecam_size_percent: number };
type RenderOptions = {
  aspect_ratio: "9:16" | "1:1" | "4:5" | "16:9";
  format_preset: "youtube_shorts" | "tiktok" | "instagram_reels" | "instagram_portrait" | "square" | "landscape" | "custom";
  resolution: 720 | 1080 | 2160;
  frame_rate: "source" | 24 | 30 | 60;
  layout: "blur" | "blur_top" | "blur_bottom" | "fit" | "fill" | "fill_top" | "fill_bottom" | "gameplay_only" | "facecam_overlay" | "facecam_circle" | "camera_top" | "camera_bottom" | "side_by_side" | "no_facecam";
  gameplay_box: FrameRegion | null;
  facecam_box: FrameRegion | null;
  facecam_position: "top_left" | "top_right" | "bottom_left" | "bottom_right" | "bottom_center";
  facecam_size_percent: number;
  caption_style: "neon" | "impact" | "clean" | "hormozi" | "mrbeast";
  template: "none" | "x_light" | "x_dark" | "tiktok_hook" | "breaking_news";
  template_name: string;
  template_handle: string;
  background_mode: "none" | "blur" | "color" | "gradient" | "image";
  background_color: string;
  background_color2: string;
  background_asset_id: string | null;
  background_name: string;
  background_dim_percent: number;
  card_padding_percent: number;
  watermark_text: string;
  logo_asset_id: string | null;
  logo_name: string;
  logo_position: "top_left" | "top_right" | "bottom_left" | "bottom_right";
  logo_size_percent: number;
  logo_opacity: number;
  credit_text: string;
  opening_hook: string;
  opening_hook_seconds: number;
  outro_text: string;
  outro_seconds: number;
  caption_font: "Arial" | "Impact" | "Tahoma" | "Verdana";
  caption_size: number;
  caption_text_color: string;
  caption_outline_color: string;
  caption_words_per_line: number;
  caption_animation: "static" | "word_highlight" | "pop_in" | "pop_in_line" | "one_by_one" | "build_up";
  music_asset_id: string | null;
  music_name: string;
  music_volume: number;
  music_peak_volume: number;
  music_riser_seconds: number;
  music_fade_seconds: number;
};
const defaultRenderOptions: RenderOptions = { aspect_ratio: "9:16", format_preset: "youtube_shorts", resolution: 1080, frame_rate: "source", layout: "blur", gameplay_box: null, facecam_box: null, facecam_position: "top_right", facecam_size_percent: 31, caption_style: "neon", template: "none", template_name: "", template_handle: "", background_mode: "none", background_color: "#181326", background_color2: "#542558", background_asset_id: null, background_name: "", background_dim_percent: 22, card_padding_percent: 14, watermark_text: "", logo_asset_id: null, logo_name: "", logo_position: "top_right", logo_size_percent: 16, logo_opacity: 85, credit_text: "", opening_hook: "", opening_hook_seconds: 8, outro_text: "", outro_seconds: 3, caption_font: "Arial", caption_size: 50, caption_text_color: "#FFFFFF", caption_outline_color: "#351633", caption_words_per_line: 5, caption_animation: "static", music_asset_id: null, music_name: "", music_volume: 20, music_peak_volume: 85, music_riser_seconds: 4, music_fade_seconds: 1.5 };
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
  user_rating: number | null;
  start_seconds: number;
  end_seconds: number;
  reasons: string[];
  signals: { audio_energy: number; speech_density: number; excitement_cues: number; scene_changes: number };
  subtitles: SubtitleSegment[];
  status: string;
  preview_url: string | null;
  render_metadata: { duration_seconds?: number; width?: number; height?: number; codec?: string; settings?: RenderOptions };
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
type LiveCaptureStatus = {
  running: boolean;
  session_id: string | null;
  source_url: string | null;
  started_at: string | null;
  segment_count: number;
  available_seconds: number;
  error: string | null;
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
type AIPartSuggestion = {
  id: string;
  title: string;
  start_seconds: number;
  end_seconds: number;
  reason: string;
};

const navItems = [
  { label: "Create clips", icon: Clapperboard, page: "media" as const },
  { label: "My clips", icon: Film, page: "clips" as const },
  { label: "YouTube", icon: Upload, page: "youtube" as const },
  { label: "Live clipping", icon: Activity, page: "live" as const },
  { label: "Overview", icon: Layers3, page: "overview" as const },
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
  const [page, setPage] = useState<Page>("media");
  const [requestedClipId, setRequestedClipId] = useState<string | null>(null);
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
              <div className="brand-mark"><Clapperboard size={18} strokeWidth={2} /></div>
          <div className="brand-copy"><span>CLIPFORGE</span><small>VIDEO STUDIO</small></div>
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
              {target === "live" && <span className="nav-new-badge">NEW</span>}
              {target === "media" && activeJobs > 0 && <span className="nav-count">{activeJobs}</span>}
              {target === "clips" && (overview?.clips_total ?? 0) > 0 && <span className="nav-count">{overview?.clips_total}</span>}
            </button>
          ))}
        </nav>

        <div className="nav-label modules-label">THE PROCESS</div>
        <div className="workflow-list">
          <div className="workflow-item"><span className="workflow-number">01</span><span>Add a recording</span><span className="workflow-dot" /></div>
          <div className="workflow-item"><span className="workflow-number">02</span><span>Pick the moments</span><span className="workflow-dot" /></div>
          <div className="workflow-item"><span className="workflow-number">03</span><span>Export or schedule</span><span className="workflow-dot" /></div>
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
              <div className="breadcrumb"><span>CLIPFORGE</span><span className="crumb-divider">/</span><span>{page === "overview" ? "OVERVIEW" : page === "media" ? "CREATE CLIPS" : page === "clips" ? "MY CLIPS" : page === "youtube" ? "YOUTUBE" : page === "live" ? "LIVE CLIPPING" : "SETTINGS"}</span></div>
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
            <MediaPage onRefresh={() => void loadDashboard(true)} focusClipId={requestedClipId} onFocusHandled={() => setRequestedClipId(null)} />
          ) : page === "clips" ? (
            <MyClipsPage onNavigate={setPage} onEditClip={(clipId) => { setRequestedClipId(clipId); setPage("media"); }} />
          ) : page === "youtube" ? (
            <YouTubePage onRefresh={() => void loadDashboard(true)} />
          ) : page === "live" ? (
            <LivePage onRefresh={() => void loadDashboard(true)} />
          ) : (
            <SettingsPage
              settings={settings}
              system={system}
              saved={saved}
              saveSettings={saveSettings}
              loading={loading}
            />
          )}

          <footer className="app-footer"><span>CLIPFORGE <b>·</b> LOCAL VIDEO STUDIO</span><span>Made for the moments worth sharing</span></footer>
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

function MediaPage({ onRefresh, focusClipId, onFocusHandled }: { onRefresh: () => void; focusClipId: string | null; onFocusHandled: () => void }) {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [jobs, setJobs] = useState<QueueJob[]>([]);
  const [clips, setClips] = useState<Clip[]>([]);
  const [path, setPath] = useState("");
  const [sourceMode, setSourceMode] = useState<"upload" | "link" | "path">("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [clipCount, setClipCount] = useState(1);
  const [clipDuration, setClipDuration] = useState(30);
  const [clipMinDuration, setClipMinDuration] = useState(15);
  const [clipMaxDuration, setClipMaxDuration] = useState(45);
  const [analysisMode, setAnalysisMode] = useState<"fast" | "deep">("fast");
  const [momentMix, setMomentMix] = useState<"balanced" | "action" | "dialogue">("balanced");
  const [focusPrompt, setFocusPrompt] = useState("");
  const [transcriptionLanguage, setTranscriptionLanguage] = useState<TranscriptionLanguage>("auto");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RecordingAnalysis | null>(null);
  const [transcriptQuery, setTranscriptQuery] = useState("");
  const [aiPartCount, setAiPartCount] = useState(5);
  const [aiParts, setAiParts] = useState<AIPartSuggestion[]>([]);
  const [selectedAiPartIds, setSelectedAiPartIds] = useState<string[]>([]);
  const [aiPartsProvider, setAiPartsProvider] = useState<string | null>(null);
  const [aiPartsNote, setAiPartsNote] = useState<string | null>(null);
  const [aiPartsBusy, setAiPartsBusy] = useState(false);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [captionDraft, setCaptionDraft] = useState<SubtitleSegment[]>([]);
  const [trimDraft, setTrimDraft] = useState({ start_seconds: 0, end_seconds: 30 });
  const [renderOptions, setRenderOptions] = useState<RenderOptions>(defaultRenderOptions);
  const [frameRegionMode, setFrameRegionMode] = useState<FrameRegionKey | null>(null);
  const [frameBoxDraft, setFrameBoxDraft] = useState<{ key: FrameRegionKey; box: FrameRegion } | null>(null);
  const [sourceViewport, setSourceViewport] = useState<SourceViewport | null>(null);
  const [framingPresets, setFramingPresets] = useState<FramingPreset[]>([]);
  const [framingPresetName, setFramingPresetName] = useState("");
  const [framingPresetSelection, setFramingPresetSelection] = useState("");
  const [imageUploadTarget, setImageUploadTarget] = useState<"logo" | "background">("logo");
  const [clipBusy, setClipBusy] = useState(false);
  const [metadata, setMetadata] = useState<ClipMetadata | null>(null);
  const [metadataForm, setMetadataForm] = useState<ClipMetadataForm>({ game_name: "", tone: "hype", title: "", description: "", hashtags: [], tags: [] });
  const [metadataBusy, setMetadataBusy] = useState(false);
  const metadataDirty = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const captionFileRef = useRef<HTMLInputElement>(null);
  const musicFileRef = useRef<HTMLInputElement>(null);
  const creationMusicFileRef = useRef<HTMLInputElement>(null);
  const imageFileRef = useRef<HTMLInputElement>(null);
  const sourcePreviewRef = useRef<HTMLVideoElement>(null);
  const frameBoxStartRef = useRef<{ x: number; y: number } | null>(null);

  const updateSourceViewport = useCallback(() => {
    const video = sourcePreviewRef.current;
    const stage = video?.parentElement;
    if (!video || !stage || !video.videoWidth || !video.videoHeight) return;
    const videoRect = video.getBoundingClientRect();
    const stageRect = stage.getBoundingClientRect();
    const scale = Math.min(videoRect.width / video.videoWidth, videoRect.height / video.videoHeight);
    const width = video.videoWidth * scale;
    const height = video.videoHeight * scale;
    setSourceViewport({
      left: videoRect.left - stageRect.left + (videoRect.width - width) / 2,
      top: videoRect.top - stageRect.top + (videoRect.height - height) / 2,
      width,
      height,
      stageWidth: stageRect.width,
      stageHeight: stageRect.height,
    });
  }, []);

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
    window.addEventListener("resize", updateSourceViewport);
    return () => window.removeEventListener("resize", updateSourceViewport);
  }, [updateSourceViewport]);

  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem("clipforge-framing-presets") || "[]") as unknown;
      if (Array.isArray(saved)) {
        const layouts: RenderOptions["layout"][] = ["blur", "blur_top", "blur_bottom", "fit", "fill", "fill_top", "fill_bottom", "gameplay_only", "facecam_overlay", "facecam_circle", "camera_top", "camera_bottom", "side_by_side", "no_facecam"];
        const safeBox = (box: unknown): box is FrameRegion => {
          if (!box || typeof box !== "object") return false;
          const candidate = box as FrameRegion;
          return [candidate.x, candidate.y, candidate.width, candidate.height].every(Number.isFinite)
            && candidate.x >= 0 && candidate.y >= 0 && candidate.width >= 0.04 && candidate.height >= 0.04
            && candidate.x + candidate.width <= 1.000001 && candidate.y + candidate.height <= 1.000001;
        };
        const allowedPositions: RenderOptions["facecam_position"][] = ["top_left", "top_right", "bottom_left", "bottom_right", "bottom_center"];
        setFramingPresets(saved.flatMap((item): FramingPreset[] => {
          if (!item || typeof item !== "object") return [];
          const preset = item as Partial<FramingPreset>;
          if (typeof preset.name !== "string" || !preset.name.trim() || !layouts.includes(preset.layout as RenderOptions["layout"])) return [];
          return [{
            name: preset.name.slice(0, 40),
            layout: preset.layout as RenderOptions["layout"],
            gameplay_box: safeBox(preset.gameplay_box) ? preset.gameplay_box : null,
            facecam_box: safeBox(preset.facecam_box) ? preset.facecam_box : null,
            facecam_position: allowedPositions.includes(preset.facecam_position as RenderOptions["facecam_position"]) ? preset.facecam_position as RenderOptions["facecam_position"] : "top_right",
            facecam_size_percent: Number.isFinite(preset.facecam_size_percent) ? Math.max(16, Math.min(50, Number(preset.facecam_size_percent))) : 31,
          }];
        }));
      }
    } catch {
      setFramingPresets([]);
    }
  }, []);

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
    if (!authorized) return;
    setBusy(true);
    setMessage(null);
    setPageError(null);
    try {
      const clipOptions = { authorized, auto_analyze: true, clip_count: clipCount, clip_duration_seconds: clipDuration, clip_min_seconds: clipMinDuration, clip_max_seconds: clipMaxDuration, analysis_mode: analysisMode, moment_mix: momentMix, transcription_language: transcriptionLanguage, render_options: renderOptions, focus_prompt: focusPrompt };
      let result: { recording_id: string; job_id: string; display_name: string };
      if (sourceMode === "upload") {
        if (!selectedFile) throw new Error("Choose a video file first.");
        const query = new URLSearchParams({
          filename: selectedFile.name,
          authorized: String(authorized),
          auto_analyze: "true",
          clip_count: String(clipCount),
          clip_duration_seconds: String(clipDuration),
          clip_min_seconds: String(clipMinDuration),
          clip_max_seconds: String(clipMaxDuration),
          analysis_mode: analysisMode,
          moment_mix: momentMix,
          transcription_language: transcriptionLanguage,
          render_options: JSON.stringify(renderOptions),
          focus_prompt: focusPrompt,
        });
        result = await api<{ recording_id: string; job_id: string; display_name: string }>(`/api/recordings/upload?${query.toString()}`, {
          method: "POST",
          headers: { "Content-Type": selectedFile.type || "application/octet-stream" },
          body: selectedFile,
        });
      } else if (sourceMode === "link") {
        if (!sourceUrl.trim()) throw new Error("Paste a direct video-file link first.");
        result = await api<{ recording_id: string; job_id: string; display_name: string }>("/api/recordings/import-link", {
          method: "POST",
          body: JSON.stringify({ ...clipOptions, url: sourceUrl.trim() }),
        });
      } else {
        if (!path.trim()) throw new Error("Choose a local video path first.");
        result = await api<{ recording_id: string; job_id: string; display_name: string }>("/api/recordings", {
          method: "POST",
          body: JSON.stringify({ ...clipOptions, path: path.trim() }),
        });
      }
      setMessage(`${result.display_name} added. ClipForge will find up to ${clipCount} clips after it checks the video.`);
      setPath("");
      setSourceUrl("");
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setAuthorized(false);
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The video could not be imported.");
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
        body: JSON.stringify({ clip_count: clipCount, clip_duration_seconds: clipDuration, clip_min_seconds: clipMinDuration, clip_max_seconds: clipMaxDuration, analysis_mode: analysisMode, moment_mix: momentMix, transcription_language: transcriptionLanguage, render_options: renderOptions, focus_prompt: focusPrompt }),
      });
      setMessage(result.existing ? "This recording is already in the analysis queue." : `ClipForge is looking for up to ${clipCount} ${momentMix} moments from ${recording.display_name}. It will caption, render, and draft metadata for each result.`);
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
    setAiParts([]);
    setSelectedAiPartIds([]);
    setAiPartsNote(null);
    setPageError(null);
    try {
      setAnalysis(await api<RecordingAnalysis>(`/api/recordings/${encodeURIComponent(recordingId)}/analysis`));
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Analysis could not be loaded.");
    }
  };

  const selectedClip = clips.find((clip) => clip.id === selectedClipId) ?? null;
  const selectedRecording = recordings.find((recording) => recording.id === selectedAnalysisId) ?? null;
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
  const trimDraftChanged = Boolean(selectedClip && (Math.abs(trimDraft.start_seconds - selectedClip.start_seconds) > 0.001 || Math.abs(trimDraft.end_seconds - selectedClip.end_seconds) > 0.001));
  const renderSettingsChanged = Boolean(selectedClip && JSON.stringify(selectedClip.render_metadata.settings ?? defaultRenderOptions) !== JSON.stringify(renderOptions));

  const sourcePointFromEvent = (event: PointerEvent<HTMLDivElement>) => {
    const video = sourcePreviewRef.current;
    if (!video?.videoWidth || !video.videoHeight) return null;
    const rect = video.getBoundingClientRect();
    const scale = Math.min(rect.width / video.videoWidth, rect.height / video.videoHeight);
    const width = video.videoWidth * scale;
    const height = video.videoHeight * scale;
    const left = rect.left + (rect.width - width) / 2;
    const top = rect.top + (rect.height - height) / 2;
    return {
      x: Math.min(1, Math.max(0, (event.clientX - left) / width)),
      y: Math.min(1, Math.max(0, (event.clientY - top) / height)),
    };
  };

  const frameRegionStyle = (box: FrameRegion | null): CSSProperties => {
    if (!box || !sourceViewport) return { display: "none" };
    return {
      left: `${sourceViewport.left + box.x * sourceViewport.width}px`,
      top: `${sourceViewport.top + box.y * sourceViewport.height}px`,
      width: `${box.width * sourceViewport.width}px`,
      height: `${box.height * sourceViewport.height}px`,
    };
  };

  const beginFrameRegion = (event: PointerEvent<HTMLDivElement>) => {
    if (!frameRegionMode || !selectedClip || clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)) return;
    const point = sourcePointFromEvent(event);
    if (!point) return;
    frameBoxStartRef.current = point;
    setFrameBoxDraft({ key: frameRegionMode, box: { x: point.x, y: point.y, width: 0, height: 0 } });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveFrameRegion = (event: PointerEvent<HTMLDivElement>) => {
    const start = frameBoxStartRef.current;
    const point = sourcePointFromEvent(event);
    if (!start || !point || !frameRegionMode) return;
    setFrameBoxDraft({ key: frameRegionMode, box: { x: Math.min(start.x, point.x), y: Math.min(start.y, point.y), width: Math.abs(point.x - start.x), height: Math.abs(point.y - start.y) } });
  };

  const finishFrameRegion = (event: PointerEvent<HTMLDivElement>) => {
    const start = frameBoxStartRef.current;
    const point = sourcePointFromEvent(event);
    const key = frameRegionMode;
    frameBoxStartRef.current = null;
    if (!start || !point || !key) {
      setFrameBoxDraft(null);
      return;
    }
    const box = { x: Math.min(start.x, point.x), y: Math.min(start.y, point.y), width: Math.abs(point.x - start.x), height: Math.abs(point.y - start.y) };
    setFrameBoxDraft(null);
    setFrameRegionMode(null);
    if (box.width < 0.04 || box.height < 0.04) {
      setPageError("Draw a larger frame region so it can be used in the export.");
      return;
    }
    setRenderOptions((options) => key === "gameplay_box"
      ? { ...options, gameplay_box: box }
      : { ...options, facecam_box: box });
    setPageError(null);
    setMessage(`${key === "gameplay_box" ? "Gameplay" : "Facecam"} region saved to the current clip style.`);
  };

  const clearFrameRegion = (key: FrameRegionKey) => {
    setRenderOptions((options) => {
      const nextLayout = (key === "gameplay_box" && options.layout === "gameplay_only")
        || (key === "facecam_box" && ["facecam_overlay", "facecam_circle", "camera_top", "camera_bottom", "side_by_side"].includes(options.layout))
        ? "blur"
        : options.layout;
      return key === "gameplay_box"
        ? { ...options, gameplay_box: null, layout: nextLayout as RenderOptions["layout"] }
        : { ...options, facecam_box: null, layout: nextLayout as RenderOptions["layout"] };
    });
  };

  const saveFramingPreset = () => {
    const name = framingPresetName.trim();
    if (!name) {
      setPageError("Name this framing preset before saving it.");
      return;
    }
    const preset: FramingPreset = {
      name: name.slice(0, 40),
      layout: renderOptions.layout,
      gameplay_box: renderOptions.gameplay_box,
      facecam_box: renderOptions.facecam_box,
      facecam_position: renderOptions.facecam_position,
      facecam_size_percent: renderOptions.facecam_size_percent,
    };
    const next = [...framingPresets.filter((item) => item.name.toLowerCase() !== preset.name.toLowerCase()), preset].slice(-20);
    window.localStorage.setItem("clipforge-framing-presets", JSON.stringify(next));
    setFramingPresets(next);
    setFramingPresetSelection(preset.name);
    setFramingPresetName("");
    setMessage(`Saved framing preset “${preset.name}” on this device.`);
    setPageError(null);
  };

  const loadFramingPreset = () => {
    const preset = framingPresets.find((item) => item.name === framingPresetSelection);
    if (!preset) return;
    setRenderOptions((options) => ({
      ...options,
      layout: preset.layout,
      gameplay_box: preset.gameplay_box,
      facecam_box: preset.facecam_box,
      facecam_position: preset.facecam_position,
      facecam_size_percent: preset.facecam_size_percent,
    }));
    setMessage(`Loaded framing preset “${preset.name}”.`);
    setPageError(null);
  };

  const editClip = (clip: Clip | RecordingAnalysis["candidates"][number]) => {
    setSelectedClipId(clip.id);
    setCaptionDraft(clip.subtitles.map((segment) => ({ ...segment })));
    setTrimDraft({ start_seconds: clip.start_seconds, end_seconds: clip.end_seconds });
    setRenderOptions({ ...defaultRenderOptions, ...clip.render_metadata.settings, format_preset: clip.render_metadata.settings?.format_preset ?? "custom" });
    setFrameRegionMode(null);
    setFrameBoxDraft(null);
    metadataDirty.current = false;
    setPageError(null);
    window.setTimeout(() => {
      if (sourcePreviewRef.current?.readyState && sourcePreviewRef.current.readyState >= 1) sourcePreviewRef.current.currentTime = clip.start_seconds;
    }, 0);
  };

  useEffect(() => {
    if (!focusClipId) return;
    const clip = clips.find((candidate) => candidate.id === focusClipId);
    if (!clip) return;
    if (analysis?.recording_id === clip.recording_id) {
      editClip(clip);
      onFocusHandled();
      window.setTimeout(() => document.getElementById("clip-editor")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
      return;
    }
    if (selectedAnalysisId !== clip.recording_id) {
      setSelectedAnalysisId(clip.recording_id);
      setAnalysis(null);
      setPageError(null);
      void api<RecordingAnalysis>(`/api/recordings/${encodeURIComponent(clip.recording_id)}/analysis`)
        .then(setAnalysis)
        .catch((reason) => setPageError(reason instanceof Error ? reason.message : "Clip analysis could not be loaded."));
    }
  }, [focusClipId, clips, analysis, selectedAnalysisId]);

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

  const saveTrim = async () => {
    if (!selectedClip) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const updated = await api<Clip>(`/api/clips/${encodeURIComponent(selectedClip.id)}/range`, {
        method: "PATCH",
        body: JSON.stringify(trimDraft),
      });
      setTrimDraft({ start_seconds: updated.start_seconds, end_seconds: updated.end_seconds });
      setCaptionDraft(updated.subtitles.map((segment) => ({ ...segment })));
      await refresh();
      onRefresh();
      setMessage("Trim saved. Captions were kept inside the new source range; render again to refresh the preview.");
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Clip timing could not be saved.");
    } finally {
      setClipBusy(false);
    }
  };

  const setTrimFromPlayhead = (edge: "in" | "out") => {
    if (!selectedClip || !sourcePreviewRef.current) return;
    const playhead = sourcePreviewRef.current.currentTime;
    const sourceDuration = selectedRecording?.duration_seconds ?? Number.POSITIVE_INFINITY;
    if (edge === "in") {
      setTrimDraft((range) => ({ ...range, start_seconds: Math.max(0, Math.min(playhead, range.end_seconds - 15)) }));
    } else {
      setTrimDraft((range) => ({ ...range, end_seconds: Math.min(sourceDuration, Math.max(range.start_seconds + 15, Math.min(playhead, range.start_seconds + 45))) }));
    }
  };

  useEffect(() => {
    if (!selectedClip) return;
    const handleEditorShortcut = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName))) return;
      const video = sourcePreviewRef.current;
      if (event.code === "Space" && video) {
        event.preventDefault();
        if (video.paused) void video.play();
        else video.pause();
      } else if (event.key.toLowerCase() === "i") {
        event.preventDefault();
        setTrimFromPlayhead("in");
      } else if (event.key.toLowerCase() === "o") {
        event.preventDefault();
        setTrimFromPlayhead("out");
      }
    };
    document.addEventListener("keydown", handleEditorShortcut);
    return () => document.removeEventListener("keydown", handleEditorShortcut);
  }, [selectedClip?.id, selectedClip?.status, selectedRecording?.duration_seconds]);

  const importCaptionFile = async (file: File | undefined) => {
    if (!file || !selectedClip) return;
    setPageError(null);
    try {
      const source = (await file.text()).replace(/\r/g, "").replace(/^\uFEFF/, "");
      const parseClock = (value: string) => {
        const parts = value.trim().split(/[,.]/)[0].split(":").map(Number);
        const fraction = Number(`0.${value.trim().split(/[,.]/)[1] ?? "0"}`);
        if (parts.some((part) => !Number.isFinite(part)) || !Number.isFinite(fraction) || parts.length < 2 || parts.length > 3) return NaN;
        const seconds = parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1];
        return seconds + fraction;
      };
      const isAss = file.name.toLowerCase().endsWith(".ass");
      const segments: SubtitleSegment[] = isAss
        ? source.split("\n").flatMap((line) => {
          if (!/^Dialogue:/i.test(line)) return [];
          const fields = line.split(",", 10);
          const start = parseClock(fields[1] ?? "");
          const end = parseClock(fields[2] ?? "");
          const text = (fields[9] ?? "").replace(/\{[^}]*\}/g, "").replace(/\\[Nn]/g, " ").replace(/<[^>]*>/g, "").trim();
          return Number.isFinite(start) && Number.isFinite(end) && text ? [{ start, end, text }] : [];
        })
        : source.split(/\n\s*\n/).flatMap((block) => {
          const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
          const timingIndex = lines.findIndex((line) => line.includes("-->"));
          if (timingIndex < 0) return [];
          const [inTime, outTime] = lines[timingIndex].split("-->");
          const start = parseClock(inTime);
          const end = parseClock(outTime);
          const text = lines.slice(timingIndex + 1).join(" ").replace(/<[^>]*>/g, "").trim();
          return Number.isFinite(start) && Number.isFinite(end) && text ? [{ start, end, text }] : [];
        });
      const clipDurationSeconds = selectedClip.end_seconds - selectedClip.start_seconds;
      if (!segments.length) throw new Error("No readable SRT, ASS, or WebVTT caption cues were found.");
      if (segments.length > 300 || segments.some((segment) => segment.start < 0 || segment.end <= segment.start || segment.end > clipDurationSeconds + 0.05)) {
        throw new Error("Caption times must fit inside this clip. Export captions trimmed to this clip's duration.");
      }
      setCaptionDraft(segments);
      setMessage(`${segments.length} caption lines imported. Save captions to apply them to this clip.`);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The caption file could not be imported.");
    } finally {
      if (captionFileRef.current) captionFileRef.current.value = "";
    }
  };

  const importMusicFile = async (file: File | undefined) => {
    if (!file) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const query = new URLSearchParams({ filename: file.name });
      const asset = await api<{ asset_id: string; display_name: string }>(`/api/music/upload?${query.toString()}`, {
        method: "POST",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      });
      setRenderOptions((options) => ({ ...options, music_asset_id: asset.asset_id, music_name: asset.display_name }));
      setMessage(`${asset.display_name} added as the clip music bed.`);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The music file could not be imported.");
    } finally {
      setClipBusy(false);
      if (musicFileRef.current) musicFileRef.current.value = "";
      if (creationMusicFileRef.current) creationMusicFileRef.current.value = "";
    }
  };

  const importImageFile = async (file: File | undefined) => {
    if (!file) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const query = new URLSearchParams({ filename: file.name });
      const asset = await api<{ asset_id: string; display_name: string }>(`/api/images/upload?${query.toString()}`, {
        method: "POST",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      });
      setRenderOptions((options) => imageUploadTarget === "logo"
        ? { ...options, logo_asset_id: asset.asset_id, logo_name: asset.display_name }
        : { ...options, background_asset_id: asset.asset_id, background_name: asset.display_name, background_mode: "image" });
      setMessage(`${asset.display_name} added as the ${imageUploadTarget === "logo" ? "logo" : "background image"}.`);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The image could not be imported.");
    } finally {
      setClipBusy(false);
      if (imageFileRef.current) imageFileRef.current.value = "";
    }
  };

  const renderClip = async () => {
    if (!selectedClip) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const job = await api<{ id: string | null; status: string; existing: boolean }>(`/api/clips/${encodeURIComponent(selectedClip.id)}/render`, {
        method: "POST",
        body: JSON.stringify(renderOptions),
      });
      setMessage(job.status === "rendered" ? "This clip already uses those render settings." : "Render queued. Your chosen frame, layout, and caption style will be applied.");
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The clip could not be queued for rendering.");
    } finally {
      setClipBusy(false);
    }
  };

  const renderSourceClips = async () => {
    if (!selectedClip) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const result = await api<{ jobs: Array<{ id: string | null; status: string; existing: boolean }>; queued: number }>(`/api/recordings/${encodeURIComponent(selectedClip.recording_id)}/clips/render`, {
        method: "POST",
        body: JSON.stringify(renderOptions),
      });
      setMessage(`${result.queued} clips from this recording queued with the selected style.`);
      await refresh();
      onRefresh();
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The recording's clips could not be queued.");
    } finally {
      setClipBusy(false);
    }
  };

  const createClipFromTranscript = async (startSeconds: number) => {
    if (!selectedAnalysisId) return;
    setClipBusy(true);
    setPageError(null);
    try {
      const clip = await api<Clip>(`/api/recordings/${encodeURIComponent(selectedAnalysisId)}/clips/from-transcript`, {
        method: "POST",
        body: JSON.stringify({ start_seconds: startSeconds, clip_duration_seconds: clipDuration }),
      });
      setSelectedClipId(clip.id);
      setCaptionDraft(clip.subtitles.map((segment) => ({ ...segment })));
      setTrimDraft({ start_seconds: clip.start_seconds, end_seconds: clip.end_seconds });
      setRenderOptions(defaultRenderOptions);
      await refresh();
      setMessage("Transcript passage added to your clip editor. Adjust captions or styling, then render it.");
      window.setTimeout(() => document.getElementById("clip-editor")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "A clip could not be created from this passage.");
    } finally {
      setClipBusy(false);
    }
  };

  const suggestAiParts = async () => {
    if (!selectedAnalysisId) return;
    setAiPartsBusy(true);
    setPageError(null);
    setAiPartsNote(null);
    try {
      const result = await api<{ parts: AIPartSuggestion[]; provider: string; model_name: string | null; note: string }>(
        `/api/recordings/${encodeURIComponent(selectedAnalysisId)}/ai-parts`,
        { method: "POST", body: JSON.stringify({ count: aiPartCount, focus_prompt: focusPrompt }) },
      );
      setAiParts(result.parts);
      setSelectedAiPartIds(result.parts.map((part) => part.id));
      setAiPartsProvider(result.model_name ? `${result.provider} · ${result.model_name}` : result.provider.replaceAll("_", " "));
      setAiPartsNote(result.note);
      if (!result.parts.length) setMessage("No 15–45 second parts were available. Run Find clips or check the local AI model in Settings.");
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "AI could not suggest transcript parts.");
    } finally {
      setAiPartsBusy(false);
    }
  };

  const createSelectedAiParts = async () => {
    if (!selectedAnalysisId) return;
    const selectedParts = aiParts.filter((part) => selectedAiPartIds.includes(part.id));
    if (!selectedParts.length) return;
    setClipBusy(true);
    setPageError(null);
    const created: Clip[] = [];
    try {
      for (let index = 0; index < selectedParts.length; index += 1) {
        const part = selectedParts[index];
        setMessage(`Creating selected parts · ${index + 1} of ${selectedParts.length}`);
        const clip = await api<Clip>(`/api/recordings/${encodeURIComponent(selectedAnalysisId)}/clips/from-range`, {
          method: "POST",
          body: JSON.stringify({ start_seconds: part.start_seconds, end_seconds: part.end_seconds }),
        });
        created.push(clip);
      }
      const last = created[created.length - 1];
      if (last) {
        setSelectedClipId(last.id);
        setCaptionDraft(last.subtitles.map((segment) => ({ ...segment })));
        setTrimDraft({ start_seconds: last.start_seconds, end_seconds: last.end_seconds });
        setRenderOptions(defaultRenderOptions);
      }
      await refresh();
      setMessage(`${created.length} selected ${created.length === 1 ? "part is" : "parts are"} ready in My clips. The last part is open in the editor.`);
      window.setTimeout(() => document.getElementById("clip-editor")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (reason) {
      await refresh();
      setPageError(reason instanceof Error ? reason.message : "The selected transcript parts could not be created.");
    } finally {
      setClipBusy(false);
    }
  };

  const visibleTranscriptSegments = (analysis?.transcript?.segments ?? []).map((segment, index) => ({ segment, index }))
    .filter(({ segment }) => !transcriptQuery.trim() || segment.text.toLowerCase().includes(transcriptQuery.trim().toLowerCase()));

  return (
    <>
      <section className="page-heading media-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> YOUR NEXT EDIT STARTS HERE</div><h1>Make clips<span className="heading-period">.</span></h1><p className="heading-subtitle">Add a recording. ClipForge finds the standout moments, adds captions, and prepares vertical videos.</p></div>
        <button className="secondary-button" onClick={() => void refresh()}><RefreshCw size={14} /> Refresh library</button>
      </section>

      {pageError && <div className="error-banner media-error"><AlertTriangle size={17} /><span>{pageError}</span></div>}
      {message && <div className="success-banner"><Check size={16} /><span>{message}</span><button aria-label="Dismiss message" onClick={() => setMessage(null)}>×</button></div>}

      <section className="surface-card import-card">
        <div className="import-card-header">
          <div className="import-icon"><Upload size={18} /></div>
          <div><div className="section-overline">01 &nbsp;·&nbsp; ADD A SOURCE</div><h3>Start with a video</h3><p>Upload a file or paste a direct video-file link. To use your own YouTube upload, download its MP4 from <a href="https://studio.youtube.com" target="_blank" rel="noreferrer">YouTube Studio</a> first.</p></div>
        </div>
        <form onSubmit={(event) => void importRecording(event)}>
          <div className="source-mode-tabs" role="group" aria-label="Choose a video source">
            <button type="button" aria-pressed={sourceMode === "upload"} className={sourceMode === "upload" ? "selected" : ""} onClick={() => setSourceMode("upload")}><Upload size={14} /> Upload video</button>
            <button type="button" aria-pressed={sourceMode === "link"} className={sourceMode === "link" ? "selected" : ""} onClick={() => setSourceMode("link")}><Link2 size={14} /> Paste a link</button>
            <button type="button" aria-pressed={sourceMode === "path"} className={sourceMode === "path" ? "selected" : ""} onClick={() => setSourceMode("path")}><HardDrive size={14} /> Local path</button>
          </div>
          {sourceMode === "upload" && <div className="upload-dropzone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const dropped = event.dataTransfer.files[0]; if (dropped) setSelectedFile(dropped); }}>
            <input ref={fileInputRef} id="source-video-file" className="sr-only" type="file" accept=".mp4,.m4v,.mkv,.mov,.avi,.webm,.mpeg,.mpg,video/*" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
            <div className="upload-drop-icon"><Upload size={18} /></div>
            <div className="upload-drop-copy"><strong>{selectedFile?.name ?? "Drop a video here"}</strong><span>{selectedFile ? `${formatBytes(selectedFile.size)} · ready to import` : "MP4, MKV, MOV, AVI, MPEG, or WebM"}</span></div>
            <button type="button" className="secondary-button" onClick={() => fileInputRef.current?.click()} disabled={busy}>{selectedFile ? "Choose another" : "Browse videos"}</button>
          </div>}
          {sourceMode === "link" && <div className="source-link-entry">
            <label className="sr-only" htmlFor="source-video-url">Direct video file URL</label>
            <Link2 size={17} />
            <input id="source-video-url" type="url" autoComplete="url" spellCheck={false} value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://example.com/gameplay.mp4" />
            <span className="source-link-hint">Direct video files only</span>
          </div>}
          {sourceMode === "path" && <div className="path-entry-row">
            <label className="sr-only" htmlFor="recording-path">Video file path</label>
            <input id="recording-path" type="text" autoComplete="off" spellCheck={false} value={path} onChange={(event) => setPath(event.target.value)} placeholder="D:\\Videos\\session.mp4" />
            <button type="button" className="secondary-button browse-button" onClick={() => void browse()} disabled={busy}><HardDrive size={14} /> Browse this PC</button>
          </div>}
          <div className="import-actions-row">
            <label className="authorization-check"><input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} /><span className="checkmark"><Check size={12} /></span><span>I own this recording or have permission to use it.</span></label>
            <button className="primary-button import-submit" type="submit" disabled={(sourceMode === "upload" ? !selectedFile : sourceMode === "link" ? !sourceUrl.trim() : !path.trim()) || !authorized || busy || clipBusy}>{busy || clipBusy ? <LoaderCircle className="spin" size={15} /> : <Sparkles size={15} />}{busy || clipBusy ? "Preparing clips…" : "Make clips"}<ArrowUpRight size={14} /></button>
          </div>
        </form>
        <div className="import-footnote"><ShieldCheck size={14} /><span>Video files are saved and processed on this PC. For links, use a direct media-file URL; platform watch pages aren’t file URLs.</span></div>
      </section>

      <div className="workflow-step-grid">
        <section className="surface-card clip-plan-card workflow-step-card">
          <div className="clip-plan-copy"><div className="section-overline">02 &nbsp;·&nbsp; MAKE IT YOUR FORMAT</div><h3>Choose the output</h3><p>Pick a platform shape and quality for every clip in this batch.</p></div>
          <div className="clip-plan-fields">
            <label>Number of clips<input type="number" min={1} max={100} value={clipCount} onChange={(event) => setClipCount(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /></label>
            <label>Minimum length (sec)<input type="number" min={15} max={45} value={clipMinDuration} onChange={(event) => { const next = Math.max(15, Math.min(45, Number(event.target.value) || 15)); setClipMinDuration(next); setClipMaxDuration((current) => Math.max(current, next)); }} /></label>
            <label>Maximum length (sec)<input type="number" min={clipMinDuration} max={45} value={clipMaxDuration} onChange={(event) => setClipMaxDuration(Math.max(clipMinDuration, Math.min(45, Number(event.target.value) || clipMinDuration)))} /></label>
            <label>Analysis mode<select value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value as "fast" | "deep")}><option value="fast">Fast · audio and transcript</option><option value="deep">Deep · include visual motion scan</option></select></label>
            <label>Platform format<select value={renderOptions.format_preset} onChange={(event) => { const preset = event.target.value as RenderOptions["format_preset"]; const ratios: Record<RenderOptions["format_preset"], RenderOptions["aspect_ratio"]> = { youtube_shorts: "9:16", tiktok: "9:16", instagram_reels: "9:16", instagram_portrait: "4:5", square: "1:1", landscape: "16:9", custom: renderOptions.aspect_ratio }; setRenderOptions((options) => ({ ...options, format_preset: preset, aspect_ratio: ratios[preset] })); }}><option value="youtube_shorts">YouTube Shorts · 9:16</option><option value="tiktok">TikTok · 9:16</option><option value="instagram_reels">Instagram Reels · 9:16</option><option value="instagram_portrait">Instagram portrait · 4:5</option><option value="square">Square · 1:1</option><option value="landscape">Landscape · 16:9</option><option value="custom">Custom frame</option></select></label>
            <label>Export resolution<select value={renderOptions.resolution} onChange={(event) => setRenderOptions((options) => ({ ...options, resolution: Number(event.target.value) as RenderOptions["resolution"] }))}><option value={720}>720p</option><option value={1080}>1080p</option><option value={2160}>4K</option></select></label>
            <label>Frame rate<select value={renderOptions.frame_rate} onChange={(event) => setRenderOptions((options) => ({ ...options, frame_rate: event.target.value === "source" ? "source" : Number(event.target.value) as 24 | 30 | 60 }))}><option value="source">Keep source</option><option value={24}>24 fps</option><option value={30}>30 fps</option><option value={60}>60 fps</option></select></label>
            <label className="focus-prompt-field">Focus topic or campaign<input maxLength={160} value={focusPrompt} onChange={(event) => setFocusPrompt(event.target.value)} placeholder="e.g. ranked comeback, boss fight, clutch" /><small>Transcript phrase matches receive a ranking boost.</small></label>
          </div>
        </section>

        <section className="surface-card clip-plan-card workflow-step-card">
          <div className="clip-plan-copy"><div className="section-overline">03 &nbsp;·&nbsp; FRAME YOUR MOMENT</div><h3>Set the visual treatment</h3><p>Choose which moments the AI should favor and how the source fills the frame.</p></div>
          <div className="clip-plan-fields">
            <label>Moment mix<select value={momentMix} onChange={(event) => setMomentMix(event.target.value as typeof momentMix)}><option value="balanced">Balanced</option><option value="action">Action</option><option value="dialogue">Dialogue</option></select></label>
            <label>Frame layout<select value={renderOptions.layout} onChange={(event) => setRenderOptions((options) => ({ ...options, layout: event.target.value as RenderOptions["layout"] }))}><option value="blur">Blurred fill</option><option value="blur_top">Blur fill · focus top</option><option value="blur_bottom">Blur fill · focus bottom</option><option value="fit">Fit with bars</option><option value="fill">Crop to fill · center</option><option value="fill_top">Crop to fill · top</option><option value="fill_bottom">Crop to fill · bottom</option></select></label>
          </div>
        </section>

        <section className="surface-card clip-plan-card workflow-step-card">
          <div className="clip-plan-copy"><div className="section-overline">04 &nbsp;·&nbsp; GIVE IT A VOICE</div><h3>Choose captions and language</h3><p>Set the speech language and a caption look before the batch starts rendering.</p></div>
          <div className="clip-plan-fields">
            <label>Speech language<select value={transcriptionLanguage} onChange={(event) => setTranscriptionLanguage(event.target.value as TranscriptionLanguage)}>{TRANSCRIPTION_LANGUAGE_OPTIONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
            <label>Caption style<select value={renderOptions.caption_style} onChange={(event) => { const style = event.target.value as RenderOptions["caption_style"]; setRenderOptions((options) => ({ ...options, caption_style: style, caption_font: style === "impact" ? "Impact" : "Arial" })); }}><option value="neon">Neon pop</option><option value="impact">Impact</option><option value="clean">Clean</option><option value="hormozi">Bold emphasis</option><option value="mrbeast">Creator punch</option></select></label>
            <label>Caption motion<select value={renderOptions.caption_animation} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_animation: event.target.value as RenderOptions["caption_animation"] }))}><option value="word_highlight">Word highlight</option><option value="pop_in">Pop-in words</option><option value="pop_in_line">Pop-in line</option><option value="one_by_one">One word at a time</option><option value="build_up">Build the line</option><option value="static">Full line</option></select></label>
          </div>
        </section>

        <section className="surface-card clip-plan-card workflow-step-card extras-step-card">
          <div className="clip-plan-copy"><div className="section-overline">05 &nbsp;·&nbsp; STYLE & EXTRAS · NEW</div><h3>Add your finishing touches</h3><p>Optional hook, outro, creator mark, and music bed. These choices will be applied to each clip in the batch.</p></div>
          <div className="clip-plan-fields extras-fields">
            <label>Opening hook<input maxLength={100} value={renderOptions.opening_hook} onChange={(event) => setRenderOptions((options) => ({ ...options, opening_hook: event.target.value }))} placeholder="Optional opening line" /></label>
            <label>Hook duration (sec)<input type="number" min={2} max={60} value={renderOptions.opening_hook_seconds} onChange={(event) => setRenderOptions((options) => ({ ...options, opening_hook_seconds: Math.max(2, Math.min(60, Number(event.target.value) || 2)) }))} /></label>
            <label>Outro ribbon<input maxLength={100} value={renderOptions.outro_text} onChange={(event) => setRenderOptions((options) => ({ ...options, outro_text: event.target.value }))} placeholder="Optional closing line" /></label>
            <label>Outro duration (sec)<input type="number" min={1.5} max={8} step={0.5} value={renderOptions.outro_seconds} onChange={(event) => setRenderOptions((options) => ({ ...options, outro_seconds: Math.max(1.5, Math.min(8, Number(event.target.value) || 1.5)) }))} /></label>
            <label>Creator watermark<input maxLength={60} value={renderOptions.watermark_text} onChange={(event) => setRenderOptions((options) => ({ ...options, watermark_text: event.target.value }))} placeholder="Name or @handle" /></label>
            <label>Social template<select value={renderOptions.template} onChange={(event) => setRenderOptions((options) => ({ ...options, template: event.target.value as RenderOptions["template"] }))}><option value="none">None</option><option value="x_light">Post card · light</option><option value="x_dark">Post card · dark</option><option value="tiktok_hook">Shorts hook card</option><option value="breaking_news">Breaking news</option></select></label>
            {renderOptions.template !== "none" && <><label>Card title<input maxLength={60} value={renderOptions.template_name} onChange={(event) => setRenderOptions((options) => ({ ...options, template_name: event.target.value }))} placeholder="Name or hook" /></label><label>Card handle<input maxLength={60} value={renderOptions.template_handle} onChange={(event) => setRenderOptions((options) => ({ ...options, template_handle: event.target.value }))} placeholder="@handle" /></label></>}
            <label>Background<select value={renderOptions.background_mode} onChange={(event) => setRenderOptions((options) => ({ ...options, background_mode: event.target.value as RenderOptions["background_mode"] }))}><option value="none">None</option><option value="blur">Blurred source</option><option value="color">Solid color</option><option value="gradient">Two-color gradient</option><option value="image" disabled={!renderOptions.background_asset_id}>My image</option></select></label>
            {["color", "gradient"].includes(renderOptions.background_mode) && <><label>Background color<input type="color" value={renderOptions.background_color} onChange={(event) => setRenderOptions((options) => ({ ...options, background_color: event.target.value.toUpperCase() }))} /></label>{renderOptions.background_mode === "gradient" && <label>Second color<input type="color" value={renderOptions.background_color2} onChange={(event) => setRenderOptions((options) => ({ ...options, background_color2: event.target.value.toUpperCase() }))} /></label>}</>}
            <label>Background image<div className="asset-choice"><span>{renderOptions.background_name || "No image selected"}</span><button type="button" className="row-action-button" disabled={clipBusy} onClick={() => { setImageUploadTarget("background"); imageFileRef.current?.click(); }}><Upload size={12} />Choose</button>{renderOptions.background_asset_id && <button type="button" className="icon-button" aria-label="Remove background image" onClick={() => setRenderOptions((options) => ({ ...options, background_asset_id: null, background_name: "", background_mode: options.background_mode === "image" ? "none" : options.background_mode }))}>×</button>}</div></label>
            <label>Background dim<input type="range" min={0} max={80} value={renderOptions.background_dim_percent} onChange={(event) => setRenderOptions((options) => ({ ...options, background_dim_percent: Number(event.target.value) }))} /><small>{renderOptions.background_dim_percent}%</small></label>
            <label>Card padding<input type="range" min={0} max={30} value={renderOptions.card_padding_percent} onChange={(event) => setRenderOptions((options) => ({ ...options, card_padding_percent: Number(event.target.value) }))} /><small>{renderOptions.card_padding_percent}%</small></label>
            <label>Logo / watermark image<div className="asset-choice"><span>{renderOptions.logo_name || "No image selected"}</span><button type="button" className="row-action-button" disabled={clipBusy} onClick={() => { setImageUploadTarget("logo"); imageFileRef.current?.click(); }}><Upload size={12} />Choose</button>{renderOptions.logo_asset_id && <button type="button" className="icon-button" aria-label="Remove logo image" onClick={() => setRenderOptions((options) => ({ ...options, logo_asset_id: null, logo_name: "" }))}>×</button>}</div></label>
            {renderOptions.logo_asset_id && <><label>Logo position<select value={renderOptions.logo_position} onChange={(event) => setRenderOptions((options) => ({ ...options, logo_position: event.target.value as RenderOptions["logo_position"] }))}><option value="top_left">Top left</option><option value="top_right">Top right</option><option value="bottom_left">Bottom left</option><option value="bottom_right">Bottom right</option></select></label><label>Logo size<input type="range" min={5} max={35} value={renderOptions.logo_size_percent} onChange={(event) => setRenderOptions((options) => ({ ...options, logo_size_percent: Number(event.target.value) }))} /><small>{renderOptions.logo_size_percent}% of frame width</small></label><label>Logo opacity<input type="range" min={10} max={100} value={renderOptions.logo_opacity} onChange={(event) => setRenderOptions((options) => ({ ...options, logo_opacity: Number(event.target.value) }))} /><small>{renderOptions.logo_opacity}%</small></label></>}
            <label>Credit line<input maxLength={100} value={renderOptions.credit_text} onChange={(event) => setRenderOptions((options) => ({ ...options, credit_text: event.target.value }))} placeholder="Optional credit" /></label>
          </div>
          <input ref={imageFileRef} className="sr-only" type="file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp" onChange={(event) => void importImageFile(event.target.files?.[0])} />
          <input ref={creationMusicFileRef} className="sr-only" type="file" accept="audio/*,.mp3,.m4a,.aac,.wav,.ogg,.flac,.opus" onChange={(event) => void importMusicFile(event.target.files?.[0])} />
          <div className="music-bed-controls">
            <div><strong>Music bed</strong><span>{renderOptions.music_name || "Optional local audio track"}</span></div>
            <button className="secondary-button" disabled={clipBusy} onClick={() => creationMusicFileRef.current?.click()}><Upload size={12} />Choose audio</button>
            {renderOptions.music_asset_id && <button className="icon-button" aria-label="Remove music bed" title="Remove music bed" onClick={() => setRenderOptions((options) => ({ ...options, music_asset_id: null, music_name: "" }))}>×</button>}
            <label>Volume<input type="range" min={0} max={100} value={renderOptions.music_volume} disabled={!renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_volume: Number(event.target.value) }))} /><small>{renderOptions.music_volume}%</small></label>
            <label>Peak volume<input type="range" min={0} max={100} value={renderOptions.music_peak_volume} disabled={!renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_peak_volume: Number(event.target.value) }))} /><small>{renderOptions.music_peak_volume}%</small></label>
            <label>Riser seconds<input type="number" min={1} max={15} value={renderOptions.music_riser_seconds} disabled={!renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_riser_seconds: Math.max(1, Math.min(15, Number(event.target.value) || 1)) }))} /><small>seconds</small></label>
            <label>Fade<input type="number" min={0} max={5} step={0.5} value={renderOptions.music_fade_seconds} disabled={!renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_fade_seconds: Math.max(0, Math.min(5, Number(event.target.value) || 0)) }))} /><small>sec</small></label>
          </div>
        </section>
      </div>

      <div className="media-columns">
        <section className="surface-card library-card">
          <div className="section-header">
            <div><div className="section-overline">YOUR FOOTAGE</div><h3>Recordings <span className="count-badge">{recordings.length}</span></h3></div>
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
                  : <button className="row-action-button analyze-action" disabled={analyzingId === recording.id || !["ready", "analyzed"].includes(recording.status) && !(recording.status === "failed" && Boolean(recording.metadata))} onClick={() => void startAnalysis(recording)}>{analyzingId === recording.id ? <LoaderCircle size={12} className="spin" /> : <Sparkles size={12} />}{recording.transcript_model ? "Find new clips" : "Find clips"}</button>}
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
          {selectedRecording && <section className="source-review-panel">
            <div className="source-review-heading"><div><div className="section-overline">FRAME YOUR MOMENT</div><h4>Review the actual scene</h4><p>Play the source and set clip in/out points from the video. The dotted box shows the centered 9:16 safe area.</p></div><span>{formatDuration(selectedRecording.duration_seconds)} source</span></div>
            <div className="source-preview-stage"><video ref={sourcePreviewRef} key={selectedRecording.id} controls preload="metadata" onLoadedMetadata={updateSourceViewport} src={`/api/recordings/${encodeURIComponent(selectedRecording.id)}/source-preview`} /><div className="source-safe-zone" aria-hidden="true"><span>9:16 safe area</span></div><div className={`source-region-overlay ${frameRegionMode ? "drawing" : ""}`} style={{ pointerEvents: frameRegionMode ? "auto" : "none" }} onPointerDown={beginFrameRegion} onPointerMove={moveFrameRegion} onPointerUp={finishFrameRegion} onPointerCancel={() => { frameBoxStartRef.current = null; setFrameBoxDraft(null); }}>{renderOptions.gameplay_box && <div className="source-region-box gameplay-region" style={frameRegionStyle(renderOptions.gameplay_box)}><span>Gameplay</span></div>}{renderOptions.facecam_box && <div className="source-region-box facecam-region" style={frameRegionStyle(renderOptions.facecam_box)}><span>Facecam</span></div>}{frameBoxDraft && <div className={`source-region-box region-draft ${frameBoxDraft.key === "gameplay_box" ? "gameplay-region" : "facecam-region"}`} style={frameRegionStyle(frameBoxDraft.box)} />}</div></div>
            {selectedClip && selectedClip.recording_id === selectedAnalysisId && <div className="source-box-controls"><button className={`row-action-button ${frameRegionMode === "gameplay_box" ? "selected" : ""}`} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !sourceViewport} onClick={() => { setFrameBoxDraft(null); setFrameRegionMode((mode) => mode === "gameplay_box" ? null : "gameplay_box"); }}>▧ {renderOptions.gameplay_box ? "Redraw gameplay area" : "Draw gameplay area"}</button>{renderOptions.gameplay_box && <button className="icon-button" aria-label="Clear gameplay area" title="Clear gameplay area" onClick={() => clearFrameRegion("gameplay_box")}>×</button>}<button className={`row-action-button ${frameRegionMode === "facecam_box" ? "selected" : ""}`} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !sourceViewport} onClick={() => { setFrameBoxDraft(null); setFrameRegionMode((mode) => mode === "facecam_box" ? null : "facecam_box"); }}>▧ {renderOptions.facecam_box ? "Redraw facecam area" : "Draw facecam area"}</button>{renderOptions.facecam_box && <button className="icon-button" aria-label="Clear facecam area" title="Clear facecam area" onClick={() => clearFrameRegion("facecam_box")}>×</button>}<span>{frameRegionMode ? `Drag across the video to mark the ${frameRegionMode === "gameplay_box" ? "gameplay" : "facecam"}.` : "Draw boxes to use gameplay-only or camera layouts."}</span></div>}
            {selectedClip && selectedClip.recording_id === selectedAnalysisId && <div className="source-review-controls"><button className="row-action-button" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => setTrimFromPlayhead("in")}>I · Set in</button><button className="row-action-button" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => setTrimFromPlayhead("out")}>O · Set out</button><span>Space plays/pauses · {trimDraft.start_seconds.toFixed(1)}s → {trimDraft.end_seconds.toFixed(1)}s</span></div>}
          </section>}
          {selectedClip && selectedClip.recording_id === selectedAnalysisId && <div className="framing-preset-controls"><label>Save framing<input maxLength={40} value={framingPresetName} onChange={(event) => setFramingPresetName(event.target.value)} placeholder="Preset name" /></label><button className="row-action-button" onClick={saveFramingPreset}>Save layout</button><label>Saved layouts<select value={framingPresetSelection} onChange={(event) => setFramingPresetSelection(event.target.value)}><option value="">Choose a saved layout</option>{framingPresets.map((preset) => <option key={preset.name} value={preset.name}>{preset.name}</option>)}</select></label><button className="row-action-button" disabled={!framingPresetSelection} onClick={loadFramingPreset}>Load layout</button></div>}
          <section className="ai-parts-panel">
            <div className="ai-parts-heading"><div><div className="section-overline">AI PARTS</div><h4>Find several strong moments</h4><p>Ask the configured local model to choose clear 15–45 second sections from this transcript. You can review and select the ranges before adding them to your clips.</p></div><span className="ai-parts-provider">{aiPartsProvider ?? "Local AI"}</span></div>
            <div className="ai-parts-controls"><label>How many parts?<input type="number" min={1} max={100} value={aiPartCount} disabled={aiPartsBusy || clipBusy} onChange={(event) => setAiPartCount(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /></label><label>Focus phrase<input maxLength={160} value={focusPrompt} disabled={aiPartsBusy || clipBusy} onChange={(event) => setFocusPrompt(event.target.value)} placeholder="Optional, e.g. clutch plays or funny reactions" /></label><button className="secondary-button" disabled={aiPartsBusy || clipBusy || !analysis.transcript} onClick={() => void suggestAiParts()}>{aiPartsBusy ? <LoaderCircle className="spin" size={14} /> : <Sparkles size={14} />}{aiPartsBusy ? "Finding parts…" : "Suggest parts"}</button></div>
            {aiPartsNote && <p className="ai-parts-note">{aiPartsNote}</p>}
            {aiParts.length > 0 && <>
              <div className="ai-parts-selection-bar"><span>{selectedAiPartIds.length} of {aiParts.length} selected</span><div><button type="button" className="row-action-button" onClick={() => setSelectedAiPartIds(aiParts.map((part) => part.id))}>Select all</button><button type="button" className="row-action-button" onClick={() => setSelectedAiPartIds([])}>Clear</button><button type="button" className="primary-button" disabled={!selectedAiPartIds.length || clipBusy} onClick={() => void createSelectedAiParts()}>{clipBusy ? <LoaderCircle className="spin" size={13} /> : <Film size={13} />} Create selected clips</button></div></div>
              <div className="ai-parts-list">{aiParts.map((part) => <label className="ai-part-row" key={part.id}><input type="checkbox" checked={selectedAiPartIds.includes(part.id)} disabled={clipBusy} onChange={(event) => setSelectedAiPartIds((current) => event.target.checked ? [...current, part.id] : current.filter((id) => id !== part.id))} /><span className="ai-part-time">{formatDuration(part.start_seconds)}–{formatDuration(part.end_seconds)}</span><span className="ai-part-copy"><strong>{part.title}</strong><small>{part.reason || "Transcript-selected moment"}</small></span><span className="ai-part-duration">{Math.round(part.end_seconds - part.start_seconds)} sec</span></label>)}</div>
            </>}
          </section>
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
            <div className="clip-editor-heading"><div><div className="section-overline">CLIP EDITOR</div><h4>{selectedClip.title}</h4><p>{formatDuration(selectedClip.end_seconds - selectedClip.start_seconds)} clip · Choose a frame, layout, and caption look · source remains unchanged</p></div><span className={`clip-state clip-state-${selectedClip.status}`}>{selectedClip.status.replaceAll("_", " ")}</span></div>
            <div className="clip-editor-grid">
              <div className="clip-preview-column">
                {selectedClip.preview_url ? <video className="clip-preview-video" controls preload="metadata" src={`${selectedClip.preview_url}?rendered=${encodeURIComponent(selectedClip.rendered_at ?? "latest")}`} /> : <div className="clip-preview-placeholder"><div className="empty-icon"><MonitorPlay size={19} /></div><strong>{selectedClip.status === "paused" ? "Render paused" : selectedClip.status === "rendering" || selectedClip.status === "queued" ? "Rendering your vertical clip" : "Preview appears after rendering"}</strong><p>FFmpeg fills the vertical frame with a blurred game backdrop and burns in the corrected captions.</p>{(selectedClip.status === "rendering" || selectedClip.status === "queued") && <LoaderCircle className="spin" size={16} />}</div>}
                {selectedClip.preview_url && <div className="clip-download-actions"><a className="secondary-button" href={`/api/clips/${encodeURIComponent(selectedClip.id)}/download`}><Upload size={13} /> Download MP4</a><a className="secondary-button" href={`/api/clips/${encodeURIComponent(selectedClip.id)}/subtitles`} download>Download clip SRT</a></div>}
                {jobs.find((job) => job.clip_id === selectedClip.id && job.status === "failed")?.error_message && <p className="clip-render-error"><AlertTriangle size={13} />{jobs.find((job) => job.clip_id === selectedClip.id && job.status === "failed")?.error_message}</p>}
              </div>
              <div className="clip-caption-editor">
                <div className="clip-trim-controls">
                  <div className="clip-trim-heading"><strong>Trim source range</strong><span>Set the in/out points from the original video. Keep the clip between 15 and 45 seconds.</span></div>
                  <div className="clip-trim-fields"><label>In · source seconds<input type="number" min="0" step="0.1" value={trimDraft.start_seconds} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setTrimDraft((range) => ({ ...range, start_seconds: Number(event.target.value) || 0 }))} /></label><label>Out · source seconds<input type="number" min="0" step="0.1" value={trimDraft.end_seconds} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setTrimDraft((range) => ({ ...range, end_seconds: Number(event.target.value) || 0 }))} /></label><button className="secondary-button" disabled={!trimDraftChanged || clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => void saveTrim()}>{clipBusy ? <LoaderCircle size={13} className="spin" /> : <Check size={13} />}Save trim</button></div>
                </div>
                <div className="caption-editor-heading"><div><strong>Caption correction</strong><span>Times are relative to this clip.</span></div><div className="caption-heading-actions"><input ref={captionFileRef} className="sr-only" type="file" accept=".srt,.ass,.vtt,text/vtt,application/x-subrip" onChange={(event) => void importCaptionFile(event.target.files?.[0])} /><button className="row-action-button" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => captionFileRef.current?.click()}><Upload size={12} /> Import captions</button><button className="row-action-button" disabled={captionDraft.length >= 300 || clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || (captionDraft.length > 0 && captionDraft[captionDraft.length - 1].end >= selectedClip.end_seconds - selectedClip.start_seconds)} onClick={() => { const clipDuration = selectedClip.end_seconds - selectedClip.start_seconds; const start = captionDraft.length ? captionDraft[captionDraft.length - 1].end : 0; setCaptionDraft((segments) => [...segments, { start, end: Math.min(clipDuration, start + 2), text: "" }]); }}>Add line</button></div></div>
                {captionDraft.length ? <div className="caption-edit-list">{captionDraft.map((segment, index) => <div className="caption-edit-row" key={`${index}-${segment.start}`}>
                  <div className="caption-time-fields"><label>In<input aria-label={`Caption ${index + 1} start time`} type="number" min="0" max={selectedClip.end_seconds - selectedClip.start_seconds} step="0.1" value={segment.start} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => updateCaption(index, "start", event.target.value)} /></label><label>Out<input aria-label={`Caption ${index + 1} end time`} type="number" min="0.1" max={selectedClip.end_seconds - selectedClip.start_seconds} step="0.1" value={segment.end} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => updateCaption(index, "end", event.target.value)} /></label><button className="icon-button caption-remove" aria-label={`Remove caption ${index + 1}`} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => setCaptionDraft((segments) => segments.filter((_item, current) => current !== index))}>×</button></div>
                  <label className="sr-only" htmlFor={`caption-text-${index}`}>Caption text {index + 1}</label><textarea id={`caption-text-${index}`} maxLength={500} rows={2} value={segment.text} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => updateCaption(index, "text", event.target.value)} />
                </div>)}</div> : <div className="caption-empty">No speech was detected in this highlight. Add caption lines if needed.</div>}
                <div className="render-controls">
                  <label>Frame<select value={renderOptions.aspect_ratio} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, aspect_ratio: event.target.value as RenderOptions["aspect_ratio"], format_preset: "custom" }))}><option value="9:16">9:16 · Shorts / Reels</option><option value="1:1">1:1 · Square</option><option value="4:5">4:5 · Portrait</option><option value="16:9">16:9 · Landscape</option></select></label>
                  <label>Resolution<select value={renderOptions.resolution} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, resolution: Number(event.target.value) as RenderOptions["resolution"] }))}><option value={720}>720p</option><option value={1080}>1080p</option><option value={2160}>4K</option></select></label>
                  <label>Frame rate<select value={renderOptions.frame_rate} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, frame_rate: event.target.value === "source" ? "source" : Number(event.target.value) as 24 | 30 | 60 }))}><option value="source">Keep source</option><option value={24}>24 fps</option><option value={30}>30 fps</option><option value={60}>60 fps</option></select></label>
                  <label>Layout<select value={renderOptions.layout} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, layout: event.target.value as RenderOptions["layout"] }))}><option value="blur">Blurred fill</option><option value="blur_top">Blur fill · focus top</option><option value="blur_bottom">Blur fill · focus bottom</option><option value="fit">Fit with bars</option><option value="fill">Crop to fill · center</option><option value="fill_top">Crop to fill · top</option><option value="fill_bottom">Crop to fill · bottom</option><option value="no_facecam">Full frame · no facecam</option><option value="gameplay_only" disabled={!renderOptions.gameplay_box}>Gameplay only · drawn area</option><option value="facecam_overlay" disabled={!renderOptions.facecam_box}>Gameplay + facecam overlay</option><option value="facecam_circle" disabled={!renderOptions.facecam_box}>Circular facecam overlay</option><option value="camera_top" disabled={!renderOptions.facecam_box}>Camera above gameplay</option><option value="camera_bottom" disabled={!renderOptions.facecam_box}>Camera below gameplay</option><option value="side_by_side" disabled={!renderOptions.facecam_box}>Side-by-side</option></select></label>
                  {["facecam_overlay", "facecam_circle"].includes(renderOptions.layout) && <><label>Facecam position<select value={renderOptions.facecam_position} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, facecam_position: event.target.value as RenderOptions["facecam_position"] }))}><option value="top_left">Top left</option><option value="top_right">Top right</option><option value="bottom_left">Bottom left</option><option value="bottom_right">Bottom right</option><option value="bottom_center">Bottom center</option></select></label><label>Facecam size<input type="range" min={16} max={50} value={renderOptions.facecam_size_percent} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, facecam_size_percent: Number(event.target.value) }))} /><small>{renderOptions.facecam_size_percent}% of frame</small></label></>}
                  <label>Captions<select value={renderOptions.caption_style} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => { const style = event.target.value as RenderOptions["caption_style"]; setRenderOptions((options) => ({ ...options, caption_style: style, caption_font: style === "impact" ? "Impact" : "Arial" })); }}><option value="neon">GTA Neon</option><option value="impact">Impact</option><option value="clean">Clean</option><option value="hormozi">Hormozi</option><option value="mrbeast">MrBeast</option></select></label>
                  <label>Caption motion<select value={renderOptions.caption_animation} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_animation: event.target.value as RenderOptions["caption_animation"] }))}><option value="word_highlight">Word highlight</option><option value="pop_in">Pop-in words</option><option value="pop_in_line">Pop-in line</option><option value="one_by_one">One word at a time</option><option value="build_up">Build the line</option><option value="static">Full line</option></select></label>
                  <label>Watermark<input maxLength={60} value={renderOptions.watermark_text} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, watermark_text: event.target.value }))} placeholder="Optional creator name" /></label>
                  <label>Opening hook<input maxLength={100} value={renderOptions.opening_hook} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, opening_hook: event.target.value }))} placeholder="Optional first seconds" /></label>
                  <label>Hook duration<input type="number" min={2} max={60} value={renderOptions.opening_hook_seconds} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, opening_hook_seconds: Math.max(2, Math.min(60, Number(event.target.value) || 2)) }))} /></label>
                  <label>Outro ribbon<input maxLength={100} value={renderOptions.outro_text} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, outro_text: event.target.value }))} placeholder="Optional closing line" /></label>
                  <label>Outro duration<input type="number" min={1.5} max={8} step={0.5} value={renderOptions.outro_seconds} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, outro_seconds: Math.max(1.5, Math.min(8, Number(event.target.value) || 1.5)) }))} /></label>
                  <label>Caption font<select value={renderOptions.caption_font} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_font: event.target.value as RenderOptions["caption_font"] }))}><option>Arial</option><option>Impact</option><option>Tahoma</option><option>Verdana</option></select></label>
                  <label>Font size<input type="number" min={24} max={100} value={renderOptions.caption_size} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_size: Math.max(24, Math.min(100, Number(event.target.value) || 24)) }))} /></label>
                  <label>Words per line<input type="number" min={2} max={12} value={renderOptions.caption_words_per_line} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_words_per_line: Math.max(2, Math.min(12, Number(event.target.value) || 2)) }))} /></label>
                  <label>Text color<input type="color" value={renderOptions.caption_text_color} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_text_color: event.target.value.toUpperCase() }))} /></label>
                  <label>Outline color<input type="color" value={renderOptions.caption_outline_color} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_outline_color: event.target.value.toUpperCase() }))} /></label>
                </div>
                <details className="render-style-advanced">
                  <summary>More visual styling · templates, backgrounds, logo & credits</summary>
                  <div className="render-controls">
                    <label>Social template<select value={renderOptions.template} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, template: event.target.value as RenderOptions["template"] }))}><option value="none">None</option><option value="x_light">Post card · light</option><option value="x_dark">Post card · dark</option><option value="tiktok_hook">Shorts hook card</option><option value="breaking_news">Breaking news</option></select></label>
                    {renderOptions.template !== "none" && <><label>Card title<input maxLength={60} value={renderOptions.template_name} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, template_name: event.target.value }))} placeholder="Name or hook" /></label><label>Card handle<input maxLength={60} value={renderOptions.template_handle} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, template_handle: event.target.value }))} placeholder="@handle" /></label></>}
                    <label>Background<select value={renderOptions.background_mode} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, background_mode: event.target.value as RenderOptions["background_mode"] }))}><option value="none">None</option><option value="blur">Blurred source</option><option value="color">Solid color</option><option value="gradient">Two-color gradient</option><option value="image" disabled={!renderOptions.background_asset_id}>My image</option></select></label>
                    {["color", "gradient"].includes(renderOptions.background_mode) && <><label>Background color<input type="color" value={renderOptions.background_color} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, background_color: event.target.value.toUpperCase() }))} /></label>{renderOptions.background_mode === "gradient" && <label>Second color<input type="color" value={renderOptions.background_color2} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, background_color2: event.target.value.toUpperCase() }))} /></label>}</>}
                    <label>Background image<div className="asset-choice"><span>{renderOptions.background_name || "No image selected"}</span><button type="button" className="row-action-button" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => { setImageUploadTarget("background"); imageFileRef.current?.click(); }}><Upload size={12} />Choose</button>{renderOptions.background_asset_id && <button type="button" className="icon-button" aria-label="Remove background image" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => setRenderOptions((options) => ({ ...options, background_asset_id: null, background_name: "", background_mode: options.background_mode === "image" ? "none" : options.background_mode }))}>×</button>}</div></label>
                    <label>Background dim<input type="range" min={0} max={80} value={renderOptions.background_dim_percent} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, background_dim_percent: Number(event.target.value) }))} /><small>{renderOptions.background_dim_percent}%</small></label>
                    <label>Frame padding<input type="range" min={0} max={28} value={renderOptions.card_padding_percent} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, card_padding_percent: Number(event.target.value) }))} /><small>{renderOptions.card_padding_percent}%</small></label>
                    <label>Creator watermark<input maxLength={60} value={renderOptions.watermark_text} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, watermark_text: event.target.value }))} placeholder="Name or @handle" /></label>
                    <label>Logo / watermark image<div className="asset-choice"><span>{renderOptions.logo_name || "No image selected"}</span><button type="button" className="row-action-button" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => { setImageUploadTarget("logo"); imageFileRef.current?.click(); }}><Upload size={12} />Choose</button>{renderOptions.logo_asset_id && <button type="button" className="icon-button" aria-label="Remove logo image" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => setRenderOptions((options) => ({ ...options, logo_asset_id: null, logo_name: "" }))}>×</button>}</div></label>
                    <label>Logo position<select value={renderOptions.logo_position} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, logo_position: event.target.value as RenderOptions["logo_position"] }))}><option value="top_left">Top left</option><option value="top_right">Top right</option><option value="bottom_left">Bottom left</option><option value="bottom_right">Bottom right</option></select></label>
                    <label>Logo size<input type="range" min={5} max={35} value={renderOptions.logo_size_percent} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !renderOptions.logo_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, logo_size_percent: Number(event.target.value) }))} /><small>{renderOptions.logo_size_percent}%</small></label>
                    <label>Logo opacity<input type="range" min={10} max={100} value={renderOptions.logo_opacity} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !renderOptions.logo_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, logo_opacity: Number(event.target.value) }))} /><small>{renderOptions.logo_opacity}%</small></label>
                    <label>Credit line<input maxLength={100} value={renderOptions.credit_text} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onChange={(event) => setRenderOptions((options) => ({ ...options, credit_text: event.target.value }))} placeholder="Optional attribution" /></label>
                  </div>
                </details>
                <div className="music-bed-controls">
                  <input ref={musicFileRef} className="sr-only" type="file" accept="audio/*,.mp3,.m4a,.aac,.wav,.ogg,.flac,.opus" onChange={(event) => void importMusicFile(event.target.files?.[0])} />
                  <div><strong>Music bed</strong><span>{renderOptions.music_name || "Add a local audio track"}</span></div>
                  <button className="secondary-button" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => musicFileRef.current?.click()}><Upload size={12} />Choose audio</button>
                  {renderOptions.music_asset_id && <button className="icon-button" aria-label="Remove music bed" title="Remove music bed" disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => setRenderOptions((options) => ({ ...options, music_asset_id: null, music_name: "" }))}>×</button>}
                  <label>Volume<input type="range" min={0} max={100} value={renderOptions.music_volume} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_volume: Number(event.target.value) }))} /><small>{renderOptions.music_volume}%</small></label>
                  <label>Music peak<input type="range" min={0} max={100} value={renderOptions.music_peak_volume} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_peak_volume: Number(event.target.value) }))} /><small>{renderOptions.music_peak_volume}%</small></label>
                  <label>Music riser<input type="number" min={1} max={15} value={renderOptions.music_riser_seconds} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_riser_seconds: Math.max(1, Math.min(15, Number(event.target.value) || 1)) }))} /><small>seconds</small></label>
                  <label>Fade<input type="number" min={0} max={5} step={0.5} value={renderOptions.music_fade_seconds} disabled={clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status) || !renderOptions.music_asset_id} onChange={(event) => setRenderOptions((options) => ({ ...options, music_fade_seconds: Math.max(0, Math.min(5, Number(event.target.value) || 0)) }))} /><small>seconds</small></label>
                </div>
                <div className="clip-editor-actions"><button className="secondary-button" disabled={!captionDraftChanged || clipBusy || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => void saveCaptions()}>{clipBusy ? <LoaderCircle size={13} className="spin" /> : <Check size={13} />}{captionDraftChanged ? "Save captions" : "Captions saved"}</button><button className="secondary-button apply-source-style" disabled={clipBusy || captionDraftChanged || trimDraftChanged || ["queued", "rendering", "paused"].includes(selectedClip.status)} onClick={() => void renderSourceClips()}><Layers3 size={13} /> Apply style to source clips</button><button className="primary-button" disabled={clipBusy || captionDraftChanged || trimDraftChanged || ["queued", "rendering", "paused"].includes(selectedClip.status) || (selectedClip.status === "rendered" && !renderSettingsChanged)} onClick={() => void renderClip()}>{clipBusy ? <LoaderCircle size={13} className="spin" /> : selectedClip.status === "rendered" && !renderSettingsChanged ? <Check size={13} /> : <Play size={13} />}{selectedClip.status === "rendered" ? renderSettingsChanged ? "Re-render clip" : "Rendered" : selectedClip.status === "paused" ? "Render paused" : selectedClip.status === "queued" || selectedClip.status === "rendering" ? "Rendering…" : "Render clip"}</button></div>
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
          <details className="full-transcript"><summary>Transcript explorer <span>{analysis.transcript?.segments.length ?? 0} segments</span></summary>{analysis.transcript?.segments.length ? <><div className="transcript-explorer-toolbar"><label className="clip-search"><Search size={14} /><input value={transcriptQuery} onChange={(event) => setTranscriptQuery(event.target.value)} placeholder="Find a line or phrase" /></label><span>Choose a line to build a clip around that moment.</span></div><div className="transcript-list">{visibleTranscriptSegments.map(({ segment, index }) => <div className="transcript-line" key={`${segment.start}-${index}`}><time>{formatDuration(segment.start)}</time><span>{segment.text}</span><button className="row-action-button" disabled={clipBusy} onClick={() => void createClipFromTranscript(segment.start)}><Clapperboard size={12} /> Clip here</button></div>)}</div>{!visibleTranscriptSegments.length && <p className="transcript-empty">No transcript lines match that phrase.</p>}</> : <p className="transcript-empty">No speech was recognized in this recording.</p>}</details>
        </>}
      </section>}
    </>
  );
}

function MyClipsPage({ onNavigate, onEditClip }: { onNavigate: (page: Page) => void; onEditClip: (clipId: string) => void }) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "ready" | "processing">("all");
  const [search, setSearch] = useState("");
  const [pageError, setPageError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setClips(await api<Clip[]>("/api/clips"));
      setPageError(null);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Your clip library could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const rendered = clips.filter((clip) => clip.status === "rendered" && clip.preview_url);
  const processing = clips.filter((clip) => ["candidate", "queued", "rendering", "paused"].includes(clip.status));
  const matchingClips = clips.filter((clip) => {
    const matchesFilter = filter === "all" || (filter === "ready" ? clip.status === "rendered" : clip.status !== "rendered");
    const query = search.trim().toLowerCase();
    return matchesFilter && (!query || `${clip.upload_title} ${clip.title} ${clip.recording_name}`.toLowerCase().includes(query));
  });

  const downloadAll = async () => {
    if (!rendered.length) return;
    setWorking("download-all");
    setPageError(null);
    try {
      const response = await fetch("/api/clips/download-all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clip_ids: rendered.map((clip) => clip.id) }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? `Download failed (${response.status})`);
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = "clipforge-clips.zip";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setMessage(`${rendered.length} clips downloaded as a ZIP.`);
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "The clip bundle could not be downloaded.");
    } finally {
      setWorking(null);
    }
  };

  const rateClip = async (clipId: string, rating: number) => {
    try {
      await api(`/api/clips/${encodeURIComponent(clipId)}/rating`, { method: "PATCH", body: JSON.stringify({ rating }) });
      setClips((current) => current.map((clip) => clip.id === clipId ? { ...clip, user_rating: rating } : clip));
    } catch (reason) {
      setPageError(reason instanceof Error ? reason.message : "Your clip rating could not be saved.");
    }
  };

  return <>
    <section className="page-heading clips-heading">
      <div><div className="eyebrow"><span className="eyebrow-line" /> YOUR BEST MOMENTS</div><h1>Your clips<span className="heading-period">.</span></h1><p className="heading-subtitle">Finished edits and clips still moving through the render queue.</p></div>
      <div className="clips-heading-actions"><button className="secondary-button" onClick={() => void refresh()}><RefreshCw size={14} /> Refresh</button><button className="primary-button" onClick={() => onNavigate("media")}><Clapperboard size={15} /> Create clips</button></div>
    </section>
    {pageError && <div className="error-banner"><AlertTriangle size={15} /><span>{pageError}</span><button onClick={() => void refresh()}>Retry</button></div>}
    {message && <div className="success-banner"><Check size={15} /><span>{message}</span><button aria-label="Dismiss message" onClick={() => setMessage(null)}>×</button></div>}

    <section className="clip-library-summary">
      <div className="clip-library-stat"><span>IN YOUR LIBRARY</span><strong>{loading ? "—" : clips.length}</strong></div>
      <div className="clip-library-stat"><span>READY TO DOWNLOAD</span><strong>{loading ? "—" : rendered.length}</strong></div>
      <div className="clip-library-stat"><span>IN PROGRESS</span><strong>{loading ? "—" : processing.length}</strong></div>
      <button className="secondary-button" disabled={!rendered.length || working !== null} onClick={() => void downloadAll()}>{working === "download-all" ? <LoaderCircle size={14} className="spin" /> : <Download size={14} />} Download all</button>
    </section>

    <section className="clip-library-panel surface-card">
      <div className="clip-library-toolbar">
        <div className="clip-filter-tabs" role="group" aria-label="Filter clips">
          {([ ["all", "All clips", clips.length], ["ready", "Ready", rendered.length], ["processing", "In progress", processing.length] ] as const).map(([value, label, count]) => <button key={value} aria-pressed={filter === value} className={filter === value ? "selected" : ""} onClick={() => setFilter(value)}>{label}<span>{count}</span></button>)}
        </div>
        <label className="clip-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search clips or recordings" /></label>
      </div>
      {loading ? <div className="loading-state"><LoaderCircle className="spin" size={19} /> Loading your clips…</div> : matchingClips.length ? <div className="saved-clips-grid">
        {matchingClips.map((clip) => <article className="saved-clip-card" key={clip.id}>
          {clip.preview_url ? <video className="saved-clip-video" controls preload="metadata" src={`${clip.preview_url}?rendered=${encodeURIComponent(clip.rendered_at ?? "latest")}`} /> : <div className={`saved-clip-placeholder placeholder-${clip.status}`}><Film size={24} /><strong>{clip.status === "rendering" || clip.status === "queued" ? "Rendering" : clip.status === "failed" ? "Needs attention" : "Ready to render"}</strong><span>{clip.status.replaceAll("_", " ")}</span></div>}
          <div className="saved-clip-body">
            <div className="saved-clip-topline"><span className="saved-clip-score"><Sparkles size={12} /> {Math.round(clip.score)} score</span><span className={`clip-state clip-state-${clip.status}`}>{clip.status.replaceAll("_", " ")}</span></div>
            <h3>{clip.upload_title || clip.title}</h3>
            <p className="saved-clip-source">{clip.recording_name} · {formatDuration(clip.render_metadata.duration_seconds ?? clip.end_seconds - clip.start_seconds)}</p>
            <div className="clip-rating" aria-label={`Rate clip, currently ${clip.user_rating ?? 0} out of 5 stars`}>{[1, 2, 3, 4, 5].map((rating) => <button key={rating} className={rating <= (clip.user_rating ?? 0) ? "rated" : ""} aria-label={`Rate ${rating} out of 5`} title={`Rate ${rating} out of 5`} onClick={() => void rateClip(clip.id, rating)}><Star size={13} fill={rating <= (clip.user_rating ?? 0) ? "currentColor" : "none"} /></button>)}<span>{clip.user_rating ? "Your rating" : "Rate this clip"}</span></div>
            {clip.upload_description && <p className="saved-clip-description">{clip.upload_description}</p>}
            <div className="saved-clip-tags">{clip.upload_hashtags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}</div>
            <div className="saved-clip-actions">
              {clip.preview_url && <a className="secondary-button" href={`/api/clips/${encodeURIComponent(clip.id)}/download`}><Download size={13} /> Download</a>}
              <button className="secondary-button" onClick={() => onEditClip(clip.id)}><Film size={13} /> Edit clip</button>
              <button className="clip-publish-action" onClick={() => onNavigate("youtube")}><Upload size={13} /> YouTube</button>
            </div>
          </div>
        </article>)}
      </div> : <div className="clips-library-empty"><div className="clips-empty-mark"><Film size={20} /></div><strong>{search ? "No clips match that search" : filter === "ready" ? "No finished clips yet" : "Your next favorite clip goes here"}</strong><p>{search ? "Try another title or source recording." : "Add a video in Create clips. Finished edits will appear here with a preview and download."}</p>{!search && <button className="primary-button" onClick={() => onNavigate("media")}><Clapperboard size={14} /> Start a clip batch</button>}</div>}
    </section>
  </>;
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

  const uploadAllPrivately = async () => {
    if (!publishableClips.length) return;
    setWorking("upload-all");
    setPageError(null);
    setMessage(null);
    let queued = 0;
    let alreadyQueued = 0;
    const failures: string[] = [];
    try {
      for (const clip of publishableClips) {
        try {
          const result = await api<{ id: string | null; status: string; existing: boolean }>(`/api/clips/${encodeURIComponent(clip.id)}/youtube-upload`, { method: "POST" });
          if (result.existing) alreadyQueued += 1;
          else queued += 1;
          setMessage(`Queueing private uploads · ${queued + alreadyQueued} of ${publishableClips.length}`);
        } catch {
          failures.push(clip.upload_title || clip.title);
        }
      }
      setMessage(`${queued} private ${queued === 1 ? "upload" : "uploads"} queued${alreadyQueued ? ` · ${alreadyQueued} already had a publication` : ""}${failures.length ? ` · ${failures.length} could not be queued` : ""}.`);
      if (failures.length) setPageError(`Could not queue: ${failures.slice(0, 3).join(", ")}${failures.length > 3 ? `, and ${failures.length - 3} more` : ""}.`);
      await refresh();
      onRefresh();
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
          <button className="secondary-button upload-all-button" disabled={!isConnected || working !== null || publishableClips.length === 0} onClick={() => void uploadAllPrivately()}>{working === "upload-all" ? <LoaderCircle size={13} className="spin" /> : <Upload size={13} />}Upload all privately</button>
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

function LivePage({ onRefresh }: { onRefresh: () => void }) {
  const [status, setStatus] = useState<LiveCaptureStatus | null>(null);
  const [sourceUrl, setSourceUrl] = useState("rtmp://127.0.0.1:1935/live/clipforge");
  const [duration, setDuration] = useState<15 | 30 | 45>(30);
  const [language, setLanguage] = useState<TranscriptionLanguage>("auto");
  const [renderOptions, setRenderOptions] = useState<RenderOptions>(defaultRenderOptions);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api<LiveCaptureStatus>("/api/live/status"));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Live capture status could not be loaded.");
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
    const timer = window.setInterval(() => void refreshStatus(), 2000);
    return () => window.clearInterval(timer);
  }, [refreshStatus]);

  const start = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const next = await api<LiveCaptureStatus>("/api/live/start", { method: "POST", body: JSON.stringify({ source_url: sourceUrl }) });
      setStatus(next);
      setNotice("Live capture started. Recent footage will appear here as it arrives.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Live capture could not be started.");
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await api<LiveCaptureStatus>("/api/live/stop", { method: "POST" }));
      setNotice("Capture stopped. You can still make a clip from the buffered moments.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Live capture could not be stopped.");
    } finally {
      setBusy(false);
    }
  };

  const createClip = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api<{ display_name: string }>("/api/live/clip", {
        method: "POST",
        body: JSON.stringify({ duration_seconds: duration, transcription_language: language, render_options: renderOptions }),
      });
      setNotice(`${result.display_name} added to the AI analysis queue. Captions and format settings will be applied automatically.`);
      onRefresh();
      await refreshStatus();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "A clip could not be created from the capture.");
    } finally {
      setBusy(false);
    }
  };

  const canClip = Boolean(status?.session_id && status.available_seconds >= duration);

  return (
    <>
      <section className="page-heading live-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> ⚡ LIVE CLIPPING · NEW</div><h1>Catch it while it happens<span className="heading-period">.</span></h1><p className="heading-subtitle">Keep a rolling buffer of your local stream and send the latest moment into ClipForge’s caption and editing workflow.</p></div>
        <span className={`live-session-pill ${status?.running ? "on-air" : "off-air"}`}><i />{status?.running ? "Capturing now" : "Capture idle"}</span>
      </section>

      {error && <div className="error-banner"><AlertTriangle size={17} /><span>{error}</span><button onClick={() => void refreshStatus()}>Retry</button></div>}
      {notice && <div className="success-banner"><Check size={16} /><span>{notice}</span><button aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button></div>}

      <section className="live-console-card surface-card">
        <div className="live-console-copy"><div className="live-console-icon"><Activity size={20} /></div><div><div className="section-overline">LOCAL STREAM INPUT</div><h3>Connect a live source</h3><p>Enter the loopback RTMP, SRT, or UDP address your local streaming setup publishes to. ClipForge only accepts localhost sources.</p></div></div>
        <label className="live-source-label">Stream address<input type="url" value={sourceUrl} disabled={Boolean(status?.running) || busy} onChange={(event) => setSourceUrl(event.target.value)} placeholder="rtmp://127.0.0.1:1935/live/clipforge" /></label>
        <div className="live-console-actions">
          {status?.running ? <button className="live-stop-button" onClick={() => void stop()} disabled={busy}><SquareStop size={15} />{busy ? "Stopping…" : "Stop capture"}</button> : <button className="primary-button live-start-button" onClick={() => void start()} disabled={busy || !sourceUrl.trim()}>{busy ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}{busy ? "Connecting…" : "Start capture"}<ArrowUpRight size={14} /></button>}
          <div className="live-meter"><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /><span className={status?.running ? "meter-running" : ""} /></div>
        </div>
        <div className="live-stats-row"><div><strong>{formatDuration(status?.available_seconds)}</strong><span>buffered footage</span></div><div><strong>{status?.segment_count ?? 0}</strong><span>ready segments</span></div><div><strong>{status?.started_at ? formatDate(status.started_at) : "—"}</strong><span>session started</span></div></div>
        {status?.error && <div className="live-runtime-error">{status.error}</div>}
      </section>

      <div className="live-workflow-grid">
        <section className="surface-card live-workflow-card">
          <div className="section-overline">01 · CHOOSE YOUR MOMENT</div><h3>Clip from the rolling buffer</h3><p>Select the latest window to send to the highlight detector.</p>
          <div className="live-form-grid">
            <label>Recent footage<select value={duration} onChange={(event) => setDuration(Number(event.target.value) as 15 | 30 | 45)}><option value={15}>Last 15 seconds</option><option value={30}>Last 30 seconds</option><option value={45}>Last 45 seconds</option></select></label>
            <label>Speech language<select value={language} onChange={(event) => setLanguage(event.target.value as TranscriptionLanguage)}>{TRANSCRIPTION_LANGUAGE_OPTIONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
            <label>Platform format<select value={renderOptions.format_preset} onChange={(event) => { const preset = event.target.value as RenderOptions["format_preset"]; const ratios: Record<RenderOptions["format_preset"], RenderOptions["aspect_ratio"]> = { youtube_shorts: "9:16", tiktok: "9:16", instagram_reels: "9:16", instagram_portrait: "4:5", square: "1:1", landscape: "16:9", custom: renderOptions.aspect_ratio }; setRenderOptions((options) => ({ ...options, format_preset: preset, aspect_ratio: ratios[preset] })); }}><option value="youtube_shorts">YouTube Shorts · 9:16</option><option value="tiktok">TikTok · 9:16</option><option value="instagram_reels">Instagram Reels · 9:16</option><option value="instagram_portrait">Instagram portrait · 4:5</option><option value="square">Square · 1:1</option><option value="landscape">Landscape · 16:9</option><option value="custom">Custom frame</option></select></label>
            <label>Caption style<select value={renderOptions.caption_style} onChange={(event) => setRenderOptions((options) => ({ ...options, caption_style: event.target.value as RenderOptions["caption_style"] }))}><option value="neon">Neon pop</option><option value="impact">Impact</option><option value="clean">Clean</option><option value="hormozi">Bold emphasis</option><option value="mrbeast">Creator punch</option></select></label>
          </div>
          <button className="primary-button live-clip-button" disabled={!canClip || busy} onClick={() => void createClip()}>{busy ? <LoaderCircle className="spin" size={14} /> : <Clapperboard size={14} />}{busy ? "Preparing clip…" : `Clip last ${duration} seconds`}</button>
          {!canClip && <span className="live-buffer-hint">Capture at least {duration} seconds to enable clipping.</span>}
        </section>

        <section className="surface-card live-setup-card">
          <div className="section-overline">SETUP NOTES</div><h3>How local capture works</h3>
          <ol><li>Start an RTMP/SRT/UDP ingest service on this PC.</li><li>Set your encoder or OBS to publish to the address above.</li><li>Start capture, wait for the buffer, then clip the last 15–45 seconds.</li></ol>
          <div className="live-setup-note"><ShieldCheck size={15} /><span>Capture stays on this PC. Public platform watch links are not accepted as live sources.</span></div>
        </section>
      </div>
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
