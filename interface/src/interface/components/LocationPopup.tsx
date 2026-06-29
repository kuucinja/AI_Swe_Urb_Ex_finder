import type { Location } from "../../retrieval/types";
import { AlertTriangle, Link2, MapPin, Route } from "lucide-react";

type LocationPopupProps = {
  location: Location;
  isHighlighted: boolean;
};

function RiskBadge({ risk }: { risk: Location["risk"] }) {
  const styles: Record<Location["risk"], string> = {
    low: "bg-emerald-500/15 text-emerald-200 border-emerald-400/30",
    medium: "bg-amber-500/15 text-amber-200 border-amber-400/30",
    high: "bg-rose-500/15 text-rose-200 border-rose-400/30",
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] ${styles[risk]}`}>
      <AlertTriangle className="mr-1 h-3 w-3" />
      {risk} risk
    </span>
  );
}

export function LocationPopup({ location, isHighlighted }: LocationPopupProps) {
  return (
    <div className="w-[280px] rounded-2xl border border-white/10 bg-slate-950/95 p-4 text-slate-100 shadow-2xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-cyan-200/80">
            <MapPin className="h-3.5 w-3.5" />
            {location.category}
          </div>
          <h3 className="mt-1 text-base font-semibold text-white">{location.name}</h3>
        </div>
        {isHighlighted ? (
          <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-[11px] text-cyan-100">
            highlighted
          </span>
        ) : null}
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-300">{location.description}</p>

      <div className="mt-4 flex items-center justify-between gap-2">
        <RiskBadge risk={location.risk} />
        <span className="text-xs text-slate-400">
          {location.coordinates[1].toFixed(4)}, {location.coordinates[0].toFixed(4)}
        </span>
      </div>

      {(location.sourceUrl || location.threadUrl) && (
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          {location.sourceUrl ? (
            <a
              href={location.sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-slate-200 transition hover:border-cyan-400/30 hover:bg-cyan-400/10"
            >
              <Link2 className="h-3.5 w-3.5" />
              source
            </a>
          ) : null}
          {location.threadUrl ? (
            <a
              href={location.threadUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-slate-200 transition hover:border-cyan-400/30 hover:bg-cyan-400/10"
            >
              <Route className="h-3.5 w-3.5" />
              thread
            </a>
          ) : null}
        </div>
      )}

      {location.comments?.length ? (
        <div className="mt-4 space-y-2 border-t border-white/10 pt-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
            confirming comments
          </p>
          {location.comments.slice(0, 3).map((comment) => (
            <p key={comment} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs leading-5 text-slate-300">
              {comment}
            </p>
          ))}
        </div>
      ) : (
        <p className="mt-4 border-t border-white/10 pt-4 text-xs leading-5 text-slate-400">
          No extra source comments are attached to this pin yet.
        </p>
      )}
    </div>
  );
}
