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

/** Recipe fields sent to `POST /api/submissions`; the server derives the slug and file path. */
export interface SubmissionRecipe {
  title: string;
  source?: string;
  ingredients: string[];
  instructions: string[];
  notes?: string[];
}

/** Result of a submission attempt. Errors carry the server's public code and message. */
export type SubmissionResult =
  | { status: "submitted"; pullRequestUrl: string }
  | {
      status: "error";
      /** Server error code such as `invalid_recipe`, or `network_error`/`unexpected_response` from the client. */
      code: string;
      message: string;
      /** Field-level problems for `invalid_recipe` and `invalid_request`. */
      errors: string[];
      /** Whether the same recipe can be retried unchanged later. */
      retryable: boolean;
      /** Seconds from `Retry-After` on `rate_limited`, when present. */
      retryAfterSeconds: number | null;
      /** HTTP status, or `null` when the server could not be reached. */
      httpStatus: number | null;
    };

const PULL_REQUEST_URL = /^https:\/\/github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9._-]+\/pull\/[1-9][0-9]*$/;

function clientError(code: string, message: string, httpStatus: number | null, retryable: boolean): SubmissionResult {
  return { status: "error", code, message, errors: [], retryable, retryAfterSeconds: null, httpStatus };
}

/**
 * Submits a recipe for review. Never throws for HTTP or network failures: the result says whether a
 * pull request was opened (or an identical open one reused) and otherwise explains why not.
 * A success is accepted only with a `https://github.com/<owner>/<repo>/pull/<n>` URL.
 */
export async function postSubmission(recipe: SubmissionRecipe, turnstileToken: string): Promise<SubmissionResult> {
  let response: Response;
  try {
    response = await fetch("/api/submissions", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ recipe, turnstile_token: turnstileToken }),
    });
  } catch (error) {
    console.error("Recipe submission request failed", error);
    return clientError("network_error", "We couldn't reach the server. Check your connection and try again.", null, true);
  }
  const body: unknown = await response.json().catch(() => null);
  const record = typeof body === "object" && body !== null ? (body as Record<string, unknown>) : {};

  if (response.status === 201) {
    const url = record.pull_request_url;
    if (record.status === "submitted" && typeof url === "string" && PULL_REQUEST_URL.test(url)) {
      return { status: "submitted", pullRequestUrl: url };
    }
    return clientError(
      "unexpected_response",
      "The server answered unexpectedly. Your recipe may have been submitted; please check before trying again.",
      response.status,
      false,
    );
  }

  const detail = typeof record.detail === "object" && record.detail !== null ? (record.detail as Record<string, unknown>) : {};
  const code = typeof detail.code === "string" ? detail.code : "unexpected_response";
  const message =
    typeof detail.message === "string" && detail.message !== ""
      ? detail.message
      : `The server answered with HTTP ${response.status}. Please try again later.`;
  const errors = Array.isArray(detail.errors) ? detail.errors.filter((e): e is string => typeof e === "string") : [];
  const retryAfter = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
  return {
    status: "error",
    code,
    message,
    errors,
    retryable: detail.retryable === true || response.status === 429 || response.status === 503,
    retryAfterSeconds: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : null,
    httpStatus: response.status,
  };
}