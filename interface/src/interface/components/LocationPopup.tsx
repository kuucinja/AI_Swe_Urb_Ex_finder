import { useState } from "react";
import type { GeocodeCandidate, Location } from "../../retrieval/types";
import { CheckCircle2, Crosshair, Gauge, Link2, MapPin, Pencil, Route, Sparkles } from "lucide-react";
import { useAppStore } from "../../retrieval/store/useAppStore";

type LocationPopupProps = {
  location: Location;
  isHighlighted: boolean;
};

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const style =
    confidence >= 0.7
      ? "bg-emerald-500/15 text-emerald-200 border-emerald-400/30"
      : confidence >= 0.4
        ? "bg-amber-500/15 text-amber-200 border-amber-400/30"
        : "bg-rose-500/15 text-rose-200 border-rose-400/30";

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] ${style}`}>
      <Gauge className="mr-1 h-3 w-3" />
      {Math.round(confidence * 100)}% confidence
    </span>
  );
}

export function LocationPopup({ location, isHighlighted }: LocationPopupProps) {
  const correctLocationEntity = useAppStore((state) => state.correctLocationEntity);
  const searchGeocode = useAppStore((state) => state.searchGeocode);
  const correctLocationGeocode = useAppStore((state) => state.correctLocationGeocode);

  const [entity, setEntity] = useState(location.entity);
  const [verified, setVerified] = useState(location.verified ?? false);
  const [confidence, setConfidence] = useState(location.confidence ?? 0);
  const [lat, setLat] = useState(location.lat);
  const [lon, setLon] = useState(location.lon);
  const [displayName, setDisplayName] = useState(location.display_name);

  const [isEditing, setIsEditing] = useState(false);
  const [draftEntity, setDraftEntity] = useState(location.entity);
  const [isSaving, setIsSaving] = useState(false);

  const [isGeocoding, setIsGeocoding] = useState(false);
  const [geocodeQuery, setGeocodeQuery] = useState("");
  const [candidates, setCandidates] = useState<GeocodeCandidate[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isPicking, setIsPicking] = useState(false);

  const evidence = location.evidence ?? [];

  async function handleSave() {
    const trimmed = draftEntity.trim();
    if (!trimmed || trimmed === entity) {
      setIsEditing(false);
      setDraftEntity(entity);
      return;
    }
    setIsSaving(true);
    const success = await correctLocationEntity(location.id, trimmed);
    setIsSaving(false);
    if (success) {
      setEntity(trimmed);
      setVerified(true);
      setIsEditing(false);
    }
  }

  async function handleGeocodeSearch() {
    const trimmed = geocodeQuery.trim();
    if (!trimmed) return;
    setIsSearching(true);
    const results = await searchGeocode(location.id, trimmed);
    setIsSearching(false);
    setCandidates(results);
  }

  async function handlePickCandidate(candidate: GeocodeCandidate) {
    setIsPicking(true);
    const success = await correctLocationGeocode(location.id, candidate);
    setIsPicking(false);
    if (success) {
      setLat(candidate.lat);
      setLon(candidate.lon);
      setDisplayName(candidate.display_name);
      setVerified(true);
      setConfidence(1);
      setCandidates([]);
      setGeocodeQuery("");
      setIsGeocoding(false);
    }
  }

  return (
    <div className="w-[280px] rounded-2xl border border-white/10 bg-slate-950/95 p-4 text-slate-100 shadow-2xl">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {displayName ? (
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-cyan-200/80">
              <MapPin className="h-3.5 w-3.5" />
              <span className="normal-case tracking-normal">{displayName}</span>
            </div>
          ) : null}

          {isEditing ? (
            <div className="mt-1 flex items-center gap-2">
              <input
                autoFocus
                value={draftEntity}
                onChange={(event) => setDraftEntity(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") handleSave();
                  if (event.key === "Escape") {
                    setIsEditing(false);
                    setDraftEntity(entity);
                  }
                }}
                className="w-full rounded-lg border border-cyan-400/30 bg-slate-900 px-2 py-1 text-sm text-white outline-none focus:border-cyan-400"
              />
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving}
                className="shrink-0 rounded-lg bg-cyan-500/20 px-2 py-1 text-xs text-cyan-100 transition hover:bg-cyan-500/30 disabled:opacity-50"
              >
                {isSaving ? "…" : "Save"}
              </button>
            </div>
          ) : (
            <div className="mt-1 flex items-center gap-2">
              <h3 className="truncate text-base font-semibold text-white">{entity}</h3>
              <button
                type="button"
                onClick={() => {
                  setDraftEntity(entity);
                  setIsEditing(true);
                }}
                className="shrink-0 text-slate-500 transition hover:text-cyan-300"
                aria-label="Correct this place's name"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          {isHighlighted ? (
            <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-[11px] text-cyan-100">
              highlighted
            </span>
          ) : null}
          {verified ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-200">
              <CheckCircle2 className="h-3 w-3" />
              verified
            </span>
          ) : null}
        </div>
      </div>

      {location.comment ? (
        <p className="mt-3 text-sm leading-6 text-slate-300">{location.comment}</p>
      ) : null}

      {location.reasoning ? (
        <p className="mt-2 flex items-start gap-1.5 text-xs leading-5 text-cyan-200/70">
          <Sparkles className="mt-0.5 h-3 w-3 shrink-0" />
          <span>{location.reasoning}</span>
        </p>
      ) : null}

      <div className="mt-4 flex items-center justify-between gap-2">
        <ConfidenceBadge confidence={confidence} />
        <button
          type="button"
          onClick={() => setIsGeocoding((value) => !value)}
          className="inline-flex items-center gap-1 text-xs text-slate-400 transition hover:text-cyan-300"
          aria-label="Fix this pin's location"
        >
          {lat.toFixed(4)}, {lon.toFixed(4)}
          <Crosshair className="h-3 w-3" />
        </button>
      </div>

      {isGeocoding ? (
        <div className="mt-3 space-y-2 rounded-xl border border-white/10 bg-white/5 p-2.5">
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={geocodeQuery}
              onChange={(event) => setGeocodeQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleGeocodeSearch();
              }}
              placeholder="Search a better address…"
              className="w-full rounded-lg border border-cyan-400/30 bg-slate-900 px-2 py-1 text-xs text-white outline-none focus:border-cyan-400"
            />
            <button
              type="button"
              onClick={handleGeocodeSearch}
              disabled={isSearching}
              className="shrink-0 rounded-lg bg-cyan-500/20 px-2 py-1 text-xs text-cyan-100 transition hover:bg-cyan-500/30 disabled:opacity-50"
            >
              {isSearching ? "…" : "Search"}
            </button>
          </div>

          {candidates.length ? (
            <div className="max-h-40 space-y-1 overflow-y-auto">
              {candidates.map((candidate, index) => (
                <button
                  key={`${candidate.lat}-${candidate.lon}-${index}`}
                  type="button"
                  disabled={isPicking}
                  onClick={() => handlePickCandidate(candidate)}
                  className="block w-full rounded-lg border border-white/10 bg-slate-900/60 px-2 py-1.5 text-left text-[11px] leading-4 text-slate-300 transition hover:border-cyan-400/30 hover:bg-cyan-400/10 disabled:opacity-50"
                >
                  {candidate.display_name ?? `${candidate.lat.toFixed(4)}, ${candidate.lon.toFixed(4)}`}
                </button>
              ))}
            </div>
          ) : (
            !isSearching && (
              <p className="text-[11px] text-slate-500">
                Search an address or landmark to re-pin this location.
              </p>
            )
          )}
        </div>
      ) : null}

      {location.thread_url ? (
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <a
            href={location.thread_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-slate-200 transition hover:border-cyan-400/30 hover:bg-cyan-400/10"
          >
            <Route className="h-3.5 w-3.5" />
            thread
          </a>
        </div>
      ) : null}

      {evidence.length ? (
        <div className="mt-4 space-y-2 border-t border-white/10 pt-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
            confirming posts ({evidence.length})
          </p>
          {evidence.slice(0, 3).map((entry, index) => (
            <div key={`${entry.post_id ?? index}`} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs leading-5 text-slate-300">
              {entry.comment ? <p>{entry.comment}</p> : null}
              {(entry.username || entry.time_raw || entry.source) && (
                <p className="mt-1 flex items-center gap-1 text-[11px] text-slate-500">
                  {entry.username ? <span>{entry.username}</span> : null}
                  {entry.time_raw ? <span>· {entry.time_raw}</span> : null}
                  {entry.source ? (
                    <a
                      href={entry.source}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-auto inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200"
                    >
                      <Link2 className="h-3 w-3" />
                      source
                    </a>
                  ) : null}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 border-t border-white/10 pt-4 text-xs leading-5 text-slate-400">
          No confirming posts are attached to this pin yet.
        </p>
      )}
    </div>
  );
}