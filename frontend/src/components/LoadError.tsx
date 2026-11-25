import { ApiError } from "../api/client";

/** Turns a failed API read into a readable sentence, keeping the HTTP status visible. */
export function describeLoadError(error: unknown, subject: string): string {
  if (error instanceof ApiError) {
    if (error.status === undefined) return `We couldn't reach the recipe service to load ${subject}. Check your connection.`;
    if (error.status === 503) return `The recipe service is unavailable right now, so ${subject} can't be shown.`;
    return `Something went wrong loading ${subject} (HTTP ${error.status}).`;
  }
  return `Something went wrong loading ${subject}.`;
}

interface LoadErrorProps {
  error: unknown;
  /** What failed to load, e.g. "recipes"; used in the message. */
  subject: string;
  onRetry: () => void;
}

/** Announced error message with a retry button for a failed recipe read. */
export function LoadError({ error, subject, onRetry }: LoadErrorProps) {
  return (
    <div className="load-error" role="alert">
      <p>{describeLoadError(error, subject)}</p>
      <button type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
