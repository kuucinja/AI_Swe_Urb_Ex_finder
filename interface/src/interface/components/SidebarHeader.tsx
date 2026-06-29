import { Filter, MapPinned, Sparkles } from "lucide-react";
import { useAppStore } from "../../retrieval/store/useAppStore";
import type { LocationCategory } from "../../retrieval/types";

const categoryLabels: Record<LocationCategory, string> = {
  factory: "factory",
  hospital: "hospital",
  bunker: "bunker",
  military: "military",
  tunnel: "tunnel",
  warehouse: "warehouse",
};

const categorySwatches: Record<LocationCategory, string> = {
  factory: "bg-cyan-400",
  hospital: "bg-emerald-400",
  bunker: "bg-amber-400",
  military: "bg-rose-400",
  tunnel: "bg-violet-400",
  warehouse: "bg-sky-400",
};

export function SidebarHeader() {
  const activeCategories = useAppStore((state) => state.activeCategories);
  const toggleCategory = useAppStore((state) => state.toggleCategory);
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

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-slate-400">
          <Filter className="h-3.5 w-3.5" />
          categories
        </span>
        {Object.keys(categoryLabels).map((category) => {
          const value = category as LocationCategory;
          const active = activeCategories.includes(value);

          return (
            <button
              key={value}
              type="button"
              onClick={() => toggleCategory(value)}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition ${
                active
                  ? "border-cyan-400/30 bg-cyan-400/15 text-cyan-50"
                  : "border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10"
              }`}
            >
              <span className={`h-2.5 w-2.5 rounded-full ${categorySwatches[value]}`} />
              {categoryLabels[value]}
            </button>
          );
        })}
      </div>

      <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
        <Sparkles className="h-3.5 w-3.5 text-cyan-200" />
        {activeCategories.length
          ? `${activeCategories.length} category filter${activeCategories.length === 1 ? "" : "s"} active`
          : "All categories visible"}
      </div>
    </div>
  );
}
