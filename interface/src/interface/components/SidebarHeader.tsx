import { useState } from "react";
import { ChevronDown, ChevronUp, MapPinned, Pause, Play, Radar } from "lucide-react";
import { useAppStore } from "../../retrieval/store/useAppStore";

function formatStartedAt(iso: string | null): string {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

function CrawlerStatusWidget() {
  const status = useAppStore((state) => state.crawlerStatus);
  const startCrawling = useAppStore((state) => state.startCrawling);
  const stopCrawling = useAppStore((state) => state.stopCrawling);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const running = status?.running ?? false;
  const known = status?.threads_known ?? 0;
  const scraped = status?.threads_scraped ?? 0;
  const pct = known > 0 ? Math.round((scraped / known) * 100) : 0;

  async function handleToggle() {
    setIsToggling(true);
    if (running) {
      await stopCrawling();
    } else {
      await startCrawling();
    }
    setIsToggling(false);
  }

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5">
      <button
        type="button"
        onClick={() => setIsExpanded((value) => !value)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left"
      >
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          {running ? (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          ) : null}
          <span
            className={`relative inline-flex h-2.5 w-2.5 rounded-full ${running ? "bg-emerald-400" : "bg-slate-600"}`}
          />
        </span>

        <span className="min-w-0 flex-1">
          <span className="block text-xs font-medium text-slate-200">
            {running ? "Crawler running" : "Crawler idle"}
          </span>
          <span className="block text-[11px] text-slate-500">
            {scraped}/{known} urbex threads scraped ({pct}%)
          </span>
        </span>

        {isExpanded ? (
          <ChevronUp className="h-3.5 w-3.5 shrink-0 text-slate-500" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-500" />
        )}
      </button>

      {isExpanded ? (
        <div className="space-y-2 border-t border-white/10 px-3 py-2.5">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-emerald-400/80 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Radar className="h-3 w-3 shrink-0" />
            {status?.current_activity ?? "not running"}
          </p>
          {status?.started_at ? (
            <p className="text-[11px] text-slate-500">Started at {formatStartedAt(status.started_at)}</p>
          ) : null}
          <button
            type="button"
            onClick={handleToggle}
            disabled={isToggling}
            className={`mt-1 flex w-full items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition disabled:opacity-50 ${
              running
                ? "border-rose-400/30 bg-rose-400/10 text-rose-200 hover:bg-rose-400/20"
                : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200 hover:bg-emerald-400/20"
            }`}
          >
            {running ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
            {isToggling ? "…" : running ? "Stop crawler" : "Start crawler"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function SidebarHeader() {
  const locations = useAppStore((state) => state.locations);
  const highlightedLocationIds = useAppStore((state) => state.highlightedLocationIds);

  return (
    <div className="border-b border-white/10 bg-slate-950/90 px-5 py-5 backdrop-blur-xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.25em] text-cyan-100">
            <MapPinned className="h-3.5 w-3.5" />
            Urbex AI Agent
          </div>
          <h1 className="mt-3 text-xl font-semibold text-white">
            map intelligence
          </h1>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Search, validate, and highlight exploration targets from the map and chat.
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-right">
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
            pins
          </div>
          <div className="mt-1 text-lg font-semibold text-white">
            {locations.length}
          </div>
          <div className="text-[11px] text-cyan-200">
            {highlightedLocationIds.length} highlighted
          </div>
        </div>
      </div>

      <CrawlerStatusWidget />
    </div>
  );
}
