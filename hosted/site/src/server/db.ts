import { ApiError } from "./http";
import type { D1Database, Env } from "./platform";

export async function first<T>(
  db: D1Database,
  sql: string,
  ...values: unknown[]
): Promise<T | null> {
  try {
    return await db.prepare(sql).bind(...values).first<T>();
  } catch {
    throw new ApiError(503, "database_unavailable", "Los datos del curso no están disponibles.");
  }
}

export async function all<T>(
  db: D1Database,
  sql: string,
  ...values: unknown[]
): Promise<T[]> {
  try {
    const result = await db.prepare(sql).bind(...values).all<T>();
    if (!result.success) throw new Error("D1 query failed.");
    return result.results ?? [];
  } catch {
    throw new ApiError(503, "database_unavailable", "Los datos del curso no están disponibles.");
  }
}

export function requireDatabase(db: D1Database | undefined): D1Database {
  if (!db) {
    throw new ApiError(503, "database_unavailable", "Los datos del curso no están disponibles.");
  }
  return db;
}

export function requireExpectedContentDigest(env: Env): string {
  const digest = env.LEARNUP_EXPECTED_CONTENT_DIGEST?.trim().toLowerCase();
  if (!digest || !/^[a-f0-9]{64}$/.test(digest)) {
    throw new ApiError(
      503,
      "content_configuration_invalid",
      "La versión esperada del curso no está configurada.",
    );
  }
  return digest;
}
