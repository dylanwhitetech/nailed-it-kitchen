import { useEffect, useState } from "react";
import { checkHealth } from "../api/health";

type Status = "checking" | "available" | "unavailable";

const messages: Record<Status, string> = {
  checking: "Checking the recipe service…",
  available: "Recipe service is available.",
  unavailable: "Recipe service is unavailable right now. Please try again later.",
};

/** Announces whether the backend health check succeeds; checked once on mount. */
export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal)
      .then(() => setStatus("available"))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error("Health check failed", error);
          setStatus("unavailable");
        }
      });
    return () => controller.abort();
  }, []);

  return (
    <p>
      <output className={`api-status api-status--${status}`}>{messages[status]}</output>
    </p>
  );
}
