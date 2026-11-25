/**
 * Error raised when the API cannot be reached or answers with a non-2xx status.
 * `status` is `undefined` for network failures (no HTTP response).
 */
export class ApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number, options?: ErrorOptions) {
    super(message, options);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Sends a GET request to a same-origin API path such as `/api/healthz`.
 *
 * The browser always talks to `/api` on its own origin: Vite proxies it in
 * development and the ingress routes it in production, so no API host is configured here.
 *
 * @throws {ApiError} on network failure or a non-2xx response.
 */
export async function apiGet(path: `/api/${string}`, signal?: AbortSignal): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal: signal ?? null });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(`Could not reach ${path}`, undefined, { cause: error });
  }
  if (!response.ok) {
    throw new ApiError(`${path} returned HTTP ${response.status}`, response.status);
  }
  return response;
}
