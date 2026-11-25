import { apiGet } from "./client";

/**
 * Checks backend liveness via `GET /api/healthz`. Any 2xx response counts as
 * healthy; the response body is intentionally not interpreted.
 *
 * @throws {ApiError} when the backend is unreachable or unhealthy.
 */
export async function checkHealth(signal?: AbortSignal): Promise<void> {
  await apiGet("/api/healthz", signal);
}
