import { useEffect, useRef } from "react";

export function useAutoScroll<T>(value: T) {
  const anchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    anchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [value]);

  return anchorRef;
}
