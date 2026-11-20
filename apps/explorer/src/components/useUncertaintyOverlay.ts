import type { SourceUncertaintyOverlay } from "../api/client";
import { useResource } from "./Common";
import { validateOverlay } from "./headColor";

/**
 * Uncertainty overlay hook: fetches a per-source scalar + interval for a head and
 * rejects anything that does not line up with that head's source space. Today the
 * server only returns a MOCK fixture; the M34 result will use the same contract.
 */
export function useUncertaintyOverlay(
  headId: string | null,
  nSources: number,
  enabled: boolean,
): {
  overlay: SourceUncertaintyOverlay | null;
  loading: boolean;
  error: string;
} {
  const r = useResource<SourceUncertaintyOverlay>(
    enabled && headId
      ? `/head-scenes/${encodeURIComponent(headId)}/uncertainty`
      : null,
  );
  if (!r.data) return { overlay: null, loading: r.loading, error: r.error };
  const problem =
    r.data.head_id !== headId
      ? "Uncertainty overlay belongs to a different head"
      : validateOverlay(r.data, nSources);
  return problem
    ? { overlay: null, loading: false, error: problem }
    : { overlay: r.data, loading: false, error: "" };
}
