import { useEffect, useRef } from "react";

const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface TurnstileApi {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
    },
  ) => string;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let scriptPromise: Promise<TurnstileApi> | undefined;

function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  scriptPromise ??= new Promise<TurnstileApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () =>
      window.turnstile ? resolve(window.turnstile) : reject(new Error("Turnstile did not initialize"));
    script.onerror = () => {
      scriptPromise = undefined;
      script.remove();
      reject(new Error("Could not load Turnstile"));
    };
    document.head.append(script);
  });
  return scriptPromise;
}

interface TurnstileWidgetProps {
  /** Public site key from the submission availability response. */
  siteKey: string;
  /**
   * Receives a fresh single-use token, or `null` when the token expires or the challenge errors.
   * Submit only with a non-null token and reset the widget (remount it) after each attempt.
   */
  onToken: (token: string | null) => void;
}

/**
 * Renders a Cloudflare Turnstile challenge. The token proves nothing on its own:
 * the server verifies it and fails closed.
 */
export function TurnstileWidget({ siteKey, onToken }: TurnstileWidgetProps) {
  const container = useRef<HTMLDivElement>(null);
  const onTokenRef = useRef(onToken);
  useEffect(() => {
    onTokenRef.current = onToken;
  });

  useEffect(() => {
    let widgetId: string | undefined;
    let api: TurnstileApi | undefined;
    let cancelled = false;
    loadTurnstile()
      .then((loaded) => {
        if (cancelled || !container.current) return;
        api = loaded;
        widgetId = loaded.render(container.current, {
          sitekey: siteKey,
          callback: (token) => onTokenRef.current(token),
          "expired-callback": () => onTokenRef.current(null),
          "error-callback": () => onTokenRef.current(null),
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("Turnstile failed to load", error);
        onTokenRef.current(null);
      });
    return () => {
      cancelled = true;
      if (api && widgetId !== undefined) api.remove(widgetId);
    };
  }, [siteKey]);

  return <div ref={container} className="turnstile" />;
}
