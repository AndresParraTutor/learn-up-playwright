export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly publicMessage: string,
  ) {
    super(publicMessage);
  }
}

const baseHeaders = {
  "Cache-Control": "private, no-store",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
} as const;

export function json(value: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json; charset=utf-8");
  for (const [name, headerValue] of Object.entries(baseHeaders)) {
    if (!headers.has(name)) headers.set(name, headerValue);
  }
  return new Response(JSON.stringify(value), { ...init, headers });
}

export function empty(status = 204, headers?: HeadersInit): Response {
  const values = new Headers(headers);
  for (const [name, headerValue] of Object.entries(baseHeaders)) {
    if (!values.has(name)) values.set(name, headerValue);
  }
  return new Response(null, { status, headers: values });
}

export function problem(error: ApiError): Response {
  return json(
    { code: error.code, detail: error.publicMessage },
    { status: error.status },
  );
}

export function methodNotAllowed(allowed: string[]): Response {
  return json(
    { code: "method_not_allowed", detail: "Método no permitido." },
    { status: 405, headers: { Allow: allowed.join(", ") } },
  );
}

export function htmlProblem(error: ApiError): Response {
  const safe = error.publicMessage
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  return new Response(
    `<!doctype html><html lang="es-419"><meta charset="utf-8"><title>Learn-Up</title><body><main><h1>Acceso no disponible</h1><p>${safe}</p><p><a href="/signout-with-chatgpt">Cerrar sesión</a></p></main></body></html>`,
    {
      status: error.status,
      headers: {
        ...baseHeaders,
        "Content-Type": "text/html; charset=utf-8",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
      },
    },
  );
}

export function isNavigationRequest(request: Request): boolean {
  if (request.method !== "GET") return false;
  const path = new URL(request.url).pathname;
  if (path.startsWith("/api/") || path.startsWith("/media/")) return false;
  return request.headers.get("Accept")?.includes("text/html") ?? false;
}
