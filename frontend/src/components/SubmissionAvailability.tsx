import { type ReactNode, useEffect, useState } from "react";
import { fetchSubmissionAvailability } from "../api/submissions";

type State = { status: "checking" | "paused" | "unavailable" } | { status: "open"; siteKey: string };

const messages = {
  checking: "Checking whether recipe submissions are open…",
  paused: "Recipe submissions are paused right now. Browsing and searching recipes still work.",
  unavailable:
    "We couldn't check whether recipe submissions are open. Browsing and searching recipes still work; please try again later.",
} as const;

interface SubmissionAvailabilityProps {
  /**
   * Renders the submission UI once the server reports submissions as open,
   * receiving the Turnstile site key to pass to `TurnstileWidget`.
   */
  children: (turnstileSiteKey: string) => ReactNode;
}

/**
 * Checks submission availability once on mount and explains when submissions are paused
 * or the check fails. Only renders `children` while open; the server still enforces the switch.
 */
export function SubmissionAvailability({ children }: SubmissionAvailabilityProps) {
  const [state, setState] = useState<State>({ status: "checking" });

  useEffect(() => {
    const controller = new AbortController();
    fetchSubmissionAvailability(controller.signal)
      .then((availability) =>
        setState(
          availability.enabled && availability.turnstileSiteKey
            ? { status: "open", siteKey: availability.turnstileSiteKey }
            : { status: "paused" },
        ),
      )
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error("Submission availability check failed", error);
          setState({ status: "unavailable" });
        }
      });
    return () => controller.abort();
  }, []);

  if (state.status === "open") return <>{children(state.siteKey)}</>;
  return (
    <p>
      <output className={`submission-status submission-status--${state.status}`}>{messages[state.status]}</output>
    </p>
  );
}
