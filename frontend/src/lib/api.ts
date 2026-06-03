type ApiBody = Record<string, unknown> | unknown[] | null;

export class ApiError<T = unknown> extends Error {
  status: number;
  body: T;

  constructor(status: number, body: T) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function readJson(response: Response) {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function apiPath(path: string) {
  return path.startsWith("/api/") ? path : `/api/${path.replace(/^\/+/, "")}`;
}

async function apiRequest<TResponse>(
  method: string,
  path: string,
  body?: ApiBody,
): Promise<TResponse> {
  const response = await fetch(apiPath(path), {
    method,
    headers:
      body === undefined
        ? undefined
        : {
            "Content-Type": "application/json",
          },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const parsedBody = await readJson(response);

  if (!response.ok) {
    throw new ApiError(response.status, parsedBody);
  }

  return parsedBody as TResponse;
}

export function apiGet<TResponse>(path: string) {
  return apiRequest<TResponse>("GET", path);
}

export function apiPost<TResponse>(path: string, body?: ApiBody) {
  return apiRequest<TResponse>("POST", path, body);
}

export function apiPatch<TResponse>(path: string, body?: ApiBody) {
  return apiRequest<TResponse>("PATCH", path, body);
}

export function apiDelete<TResponse>(path: string) {
  return apiRequest<TResponse>("DELETE", path);
}
