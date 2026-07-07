const defaultApiBaseUrl = "http://localhost:8000";

const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_LUMEN_API_BASE_URL ??
  defaultApiBaseUrl;

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

type ApiClientConfig = {
  getAccessToken: () => string | null;
  onUnauthorized: () => void;
};

type RequestOptions = {
  auth?: boolean;
  body?: unknown;
  headers?: HeadersInit;
  method?: string;
};

let getAccessToken = () => null as string | null;
let onUnauthorized: () => void = () => undefined;

export function configureApiClient(config: ApiClientConfig) {
  getAccessToken = config.getAccessToken;
  onUnauthorized = config.onUnauthorized;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const useAuth = options.auth ?? true;

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  if (useAuth) {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const hasBody = options.body !== undefined;
  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: hasBody ? JSON.stringify(options.body) : undefined,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    if (response.status === 401 && useAuth) {
      onUnauthorized();
    }

    const message =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : `API request failed with status ${response.status}.`;

    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export { apiBaseUrl };
