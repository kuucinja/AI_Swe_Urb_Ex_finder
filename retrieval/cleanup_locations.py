"""
Reviews existing `locations` rows and removes/renames the ones that
don't hold up - mainly leftovers from the old regex-based entity
extractor, which had no way to tell a real place name from an ordinary
capitalized word.

Only ever touches `locations` (never `posts` - the raw scraped comments
are never modified). Rows already marked `verified` (a human has
confirmed/corrected them) are always skipped.

Run manually, e.g.:

    python -m retrieval.cleanup_locations
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import database.repository as repo

# Windows consoles/redirected-output default to a codepage (e.g. cp1251)
# that can't encode Swedish characters (ö/ä/å) in scraped entity names -
# without this, print() crashes mid-run the moment it hits one.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
from backend.call_llm import call_llm_json


def review_location(entity: str, comment: str | None, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Ask the LLM whether this location's name/evidence holds up, and how
    confidently. This tool is a helper for a human annotator, not a final
    filter: even a low-confidence clue (a real town used only as a
    proximity reference, with the actual site left unnamed) is worth
    keeping, since a human can act on it. Only delete entries with no
    real place-related signal at all. Returns
    {keep: bool, corrected_name: str | None, confidence: float, reasoning: str}."""
    evidence_text = "\n".join(
        f"- {entry.get('comment') or ''}" for entry in (evidence or []) if entry.get("comment")
    ) or (comment or "")

    messages = [
        {
            "role": "system",
            "content": """
You are reviewing an entry in a database of urban-exploration (urbex)
locations scraped from a Swedish forum. Some entries were produced by an
older, unreliable heuristic that sometimes mistook ordinary words for
place names.

You are given the entry's current name and the original forum comment(s)
it was derived from. This database is a helper for a human annotator, not
a final filter - the goal is to surface every real place-related clue,
however uncertain, and let a calibrated confidence score carry the
uncertainty rather than discarding it. Decide:

- "keep": true if the comment(s) contain ANY real place-related signal -
  a specific named site, or even just a real town/area used as a
  proximity reference for an unnamed site. false ONLY if there is no
  place-related signal at all (the current name is a pronoun, generic
  word, or unrelated topic with no place mentioned anywhere in the text).
- "corrected_name": if the comment(s) clearly support a different, more
  accurate real place than the current name (including cases where the
  current name is wrong but a real place IS mentioned elsewhere in the
  text), provide it here. Otherwise null.
- "confidence": a number from 0.0 to 1.0:
    - 0.8-1.0: a specific named building/ruin/facility - a real pin.
    - 0.4-0.7: a real place used as a fairly tight proximity reference
      for an unnamed site.
    - 0.1-0.3: only a broad area/town/region is mentioned, with little
      specificity about the actual site.
- "reasoning": one short sentence explaining the decision and the
  confidence score.

Return ONLY strict JSON:
{"keep": bool, "corrected_name": string|null, "confidence": number, "reasoning": string}
"""
        },
        {
            "role": "user",
            "content": f"Current name: {entity}\n\nOriginal comment(s):\n{evidence_text}"
        }
    ]

    try:
        result = call_llm_json(messages)
    except Exception as exc:
        print(f"review_location failed for {entity!r}: {exc}")
        return {"keep": True, "corrected_name": None, "confidence": None, "reasoning": "review failed, kept as-is"}

    try:
        confidence = float(result.get("confidence"))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = None

    return {
        "keep": bool(result.get("keep", True)),
        "corrected_name": (result.get("corrected_name") or "").strip() or None,
        "confidence": confidence,
        "reasoning": (result.get("reasoning") or "").strip() or None,
    }


def cleanup_locations(dry_run: bool = False) -> dict[str, int]:
    stats = {"reviewed": 0, "kept": 0, "renamed": 0, "low_confidence_kept": 0, "deleted": 0, "skipped_verified": 0}

    for row in repo.get_locations():
        if row.get("verified"):
            stats["skipped_verified"] += 1
            continue

        stats["reviewed"] += 1
        result = review_location(row["entity"], row.get("comment"), row.get("evidence") or [])

        if not result["keep"]:
            print(f"DELETE  {row['id']}  {row['entity']!r}  -  {result['reasoning']}")
            stats["deleted"] += 1
            if not dry_run:
                repo.delete_location(row["id"])
            continue

        renamed = bool(result["corrected_name"] and result["corrected_name"] != row["entity"])
        confidence = result["confidence"]
        if confidence is not None and confidence < 0.4:
            stats["low_confidence_kept"] += 1
        if renamed:
            stats["renamed"] += 1
        else:
            stats["kept"] += 1

        label = "RENAME" if renamed else "KEEP  "
        arrow = f" -> {result['corrected_name']!r}" if renamed else ""
        conf_display = f"{confidence:.2f}" if confidence is not None else "?"
        print(f"{label}  {row['id']}  {row['entity']!r}{arrow}  (confidence {conf_display})  -  {result['reasoning']}")

        if not dry_run:
            fields: dict[str, Any] = {"reasoning": result["reasoning"]}
            if renamed:
                fields["entity"] = result["corrected_name"]
            if confidence is not None:
                fields["confidence"] = confidence
            repo.update_location(row["id"], **fields)

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review and clean up existing locations using the LLM.")
    parser.add_argument("--dry-run", action="store_true", help="Print decisions without writing them.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = cleanup_locations(dry_run=args.dry_run)
    print()
    print("Cleanup stats:", stats)


if __name__ == "__main__":
    main()