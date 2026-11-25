import { ApiError, apiGet } from "./client";

/** Public submission availability, from `GET /api/submissions/availability`. */
export interface SubmissionAvailability {
  /** Whether the server currently accepts new submissions. The server enforces this on submit too. */
  enabled: boolean;
  /** Cloudflare Turnstile site key to render; present only while submissions are enabled. */
  turnstileSiteKey: string | null;
}

/**
 * Reads whether recipe submissions are open. Hiding the form is only a courtesy:
 * the server refuses submissions on its own when they are disabled.
 *
 * @throws {ApiError} when the backend is unreachable, errors or returns an unexpected shape.
 */
export async function fetchSubmissionAvailability(signal?: AbortSignal): Promise<SubmissionAvailability> {
  const response = await apiGet("/api/submissions/availability", signal);
  const body: unknown = await response.json().catch(() => null);
  if (typeof body === "object" && body !== null) {
    const { enabled, turnstile_site_key: siteKey } = body as Record<string, unknown>;
    if (enabled === false) return { enabled: false, turnstileSiteKey: null };
    if (enabled === true && typeof siteKey === "string" && siteKey !== "") {
      return { enabled: true, turnstileSiteKey: siteKey };
    }
  }
  throw new ApiError("Unexpected submission availability response", response.status);
}
