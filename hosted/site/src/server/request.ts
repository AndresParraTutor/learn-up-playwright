import { ApiError } from "./http";

const JSON_CONTENT_TYPE = /^application\/json(?:\s*;|$)/i;
const IDEMPOTENCY_KEY = /^[A-Za-z0-9._:-]{16,128}$/;

export function requireSameOriginMutation(request: Request): void {
  const site = request.headers.get("Sec-Fetch-Site")?.toLowerCase();
  if (site === "cross-site") {
    throw new ApiError(403, "cross_site_denied", "La solicitud no proviene de este sitio.");
  }
  const origin = request.headers.get("Origin");
  if (origin && origin !== new URL(request.url).origin) {
    throw new ApiError(403, "origin_denied", "La solicitud no proviene de este sitio.");
  }
}

async function readBoundedText(request: Request, maximumBytes: number): Promise<string> {
  const declared = request.headers.get("Content-Length");
  if (declared) {
    const size = Number(declared);
    if (!Number.isSafeInteger(size) || size < 0 || size > maximumBytes) {
      throw new ApiError(413, "request_too_large", "La solicitud supera el tamaño permitido.");
    }
  }
  if (!request.body) return "";
  const reader = request.body.getReader();
  const decoder = new TextDecoder();
  let bytes = 0;
  let value = "";
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    bytes += chunk.value.byteLength;
    if (bytes > maximumBytes) {
      await reader.cancel();
      throw new ApiError(413, "request_too_large", "La solicitud supera el tamaño permitido.");
    }
    value += decoder.decode(chunk.value, { stream: true });
  }
  return value + decoder.decode();
}

export async function readJsonObject(
  request: Request,
  maximumBytes = 16_384,
): Promise<Record<string, unknown>> {
  requireSameOriginMutation(request);
  const contentType = request.headers.get("Content-Type") ?? "";
  if (!JSON_CONTENT_TYPE.test(contentType)) {
    throw new ApiError(415, "json_required", "La solicitud debe usar JSON.");
  }
  const text = await readBoundedText(request, maximumBytes);
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new ApiError(400, "json_invalid", "El cuerpo JSON no es válido.");
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ApiError(400, "json_invalid", "El cuerpo JSON debe ser un objeto.");
  }
  return value as Record<string, unknown>;
}

export function requireIdempotencyKey(request: Request): string {
  const value = request.headers.get("Idempotency-Key")?.trim() ?? "";
  if (!IDEMPOTENCY_KEY.test(value)) {
    throw new ApiError(
      400,
      "idempotency_key_invalid",
      "La solicitud necesita un identificador de reintento válido.",
    );
  }
  return value;
}

export function requiredString(
  object: Record<string, unknown>,
  name: string,
  maximumLength: number,
): string {
  const value = object[name];
  if (typeof value !== "string") {
    throw new ApiError(400, "request_invalid", `El campo ${name} no es válido.`);
  }
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > maximumLength) {
    throw new ApiError(400, "request_invalid", `El campo ${name} no es válido.`);
  }
  return trimmed;
}

export function optionalString(
  object: Record<string, unknown>,
  name: string,
  maximumLength: number,
): string | undefined {
  const value = object[name];
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string") {
    throw new ApiError(400, "request_invalid", `El campo ${name} no es válido.`);
  }
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > maximumLength) {
    throw new ApiError(400, "request_invalid", `El campo ${name} no es válido.`);
  }
  return trimmed;
}

export function optionalPositiveInteger(
  object: Record<string, unknown>,
  name: string,
  maximum: number,
): number | undefined {
  const value = object[name];
  if (value === undefined || value === null) return undefined;
  if (!Number.isInteger(value) || (value as number) < 1 || (value as number) > maximum) {
    throw new ApiError(400, "request_invalid", `El campo ${name} no es válido.`);
  }
  return value as number;
}

export function requiredStringArray(
  object: Record<string, unknown>,
  name: string,
  maximumItems: number,
): string[] {
  const value = object[name];
  if (
    !Array.isArray(value) ||
    value.length > maximumItems ||
    value.some((item) => typeof item !== "string" || item.length > 512)
  ) {
    throw new ApiError(400, "request_invalid", `El campo ${name} no es válido.`);
  }
  return value as string[];
}

export function optionalBoolean(object: Record<string, unknown>, name: string): boolean {
  const value = object[name];
  if (value === undefined) return false;
  if (typeof value !== "boolean") {
    throw new ApiError(400, "request_invalid", `El campo ${name} no es válido.`);
  }
  return value;
}
