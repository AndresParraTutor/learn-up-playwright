import type { AuthorizedUser } from "./auth";
import { first, requireDatabase, requireExpectedContentDigest } from "./db";
import { ApiError, empty } from "./http";
import type { Env, R2Object } from "./platform";

interface MediaRow {
  object_key: string;
  content_type: string;
  byte_size: number;
  sha256: string;
}

interface ByteRange {
  offset: number;
  length: number;
}

export function parseByteRange(value: string | null, size: number): ByteRange | null {
  if (!value) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(value.trim());
  if (!match || value.includes(",")) {
    throw new ApiError(416, "range_invalid", "El rango solicitado no es válido.");
  }
  const [, rawStart, rawEnd] = match;
  if (!rawStart && !rawEnd) {
    throw new ApiError(416, "range_invalid", "El rango solicitado no es válido.");
  }
  if (!rawStart) {
    const suffix = Number(rawEnd);
    if (!Number.isSafeInteger(suffix) || suffix <= 0) {
      throw new ApiError(416, "range_invalid", "El rango solicitado no es válido.");
    }
    const length = Math.min(suffix, size);
    return { offset: size - length, length };
  }
  const start = Number(rawStart);
  const requestedEnd = rawEnd ? Number(rawEnd) : size - 1;
  if (
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(requestedEnd) ||
    start < 0 ||
    start >= size ||
    requestedEnd < start
  ) {
    throw new ApiError(416, "range_invalid", "El rango solicitado no es válido.");
  }
  const end = Math.min(requestedEnd, size - 1);
  return { offset: start, length: end - start + 1 };
}

function mediaHeaders(object: R2Object, row: MediaRow): Headers {
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", row.content_type || "video/mp4");
  headers.set("Accept-Ranges", "bytes");
  headers.set("Cache-Control", "private, no-store");
  headers.set("ETag", object.httpEtag || `\"${object.etag}\"`);
  headers.set("X-Content-Type-Options", "nosniff");
  return headers;
}

export async function serveMedia(
  request: Request,
  env: Env,
  _user: AuthorizedUser,
): Promise<Response> {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return empty(405, { Allow: "GET, HEAD" });
  }
  if (!env.BUCKET) {
    throw new ApiError(503, "media_unavailable", "El almacenamiento multimedia no está disponible.");
  }
  const url = new URL(request.url);
  const pathMatch = /^\/media\/([a-z0-9-]+)\/([a-z0-9-]+\.mp4)$/.exec(url.pathname);
  if (!pathMatch) throw new ApiError(404, "media_not_found", "El video no está disponible.");
  const [, topicSlug, filename] = pathMatch;
  const objectKey = `media/${topicSlug}/${filename}`;
  const db = requireDatabase(env.DB);
  const expectedDigest = requireExpectedContentDigest(env);
  const row = await first<MediaRow>(
    db,
    `SELECT m.object_key, m.content_type, m.byte_size, m.sha256
     FROM media_objects m
     JOIN content_releases r ON r.id = m.release_id
     WHERE r.topic_slug = ?1 AND r.status = 'active'
       AND m.object_key = ?2 AND m.available = 1 AND r.source_digest = ?3`,
    topicSlug,
    objectKey,
    expectedDigest,
  );
  if (!row) throw new ApiError(404, "media_not_found", "El video no está disponible.");
  const metadata = await env.BUCKET.head(objectKey);
  if (!metadata || metadata.size !== row.byte_size) {
    throw new ApiError(503, "media_unavailable", "El video todavía no está disponible.");
  }
  const headers = mediaHeaders(metadata, row);
  if (request.method === "HEAD") {
    headers.set("Content-Length", String(metadata.size));
    return new Response(null, { status: 200, headers });
  }
  let range: ByteRange | null;
  try {
    range = parseByteRange(request.headers.get("Range"), metadata.size);
  } catch (error) {
    if (error instanceof ApiError && error.status === 416) {
      headers.set("Content-Range", `bytes */${metadata.size}`);
      return new Response(null, {
        status: 416,
        headers,
      });
    }
    throw error;
  }
  const object = await env.BUCKET.get(objectKey, range ? { range } : undefined);
  if (!object) throw new ApiError(503, "media_unavailable", "El video todavía no está disponible.");
  if (range) {
    const end = range.offset + range.length - 1;
    headers.set("Content-Range", `bytes ${range.offset}-${end}/${metadata.size}`);
    headers.set("Content-Length", String(range.length));
    return new Response(object.body, { status: 206, headers });
  }
  headers.set("Content-Length", String(metadata.size));
  return new Response(object.body, { status: 200, headers });
}
