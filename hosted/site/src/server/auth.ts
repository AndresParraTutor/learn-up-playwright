import { ApiError } from "./http";
import type { Env } from "./platform";

const EMAIL_HEADER = "oai-authenticated-user-email";
const FULL_NAME_HEADER = "oai-authenticated-user-full-name";

export type AllowlistRole = "owner" | "learner";

export interface AuthorizedUser {
  id: number;
  email: string;
  displayName: string;
  role: AllowlistRole;
}

interface AllowlistRow {
  role: AllowlistRole;
}

interface UserRow {
  id: number;
}

export function normalizeEmail(value: string): string {
  const email = value.trim().toLowerCase();
  if (!email || email.length > 320 || !email.includes("@")) {
    throw new ApiError(401, "identity_invalid", "La identidad autenticada no es válida.");
  }
  return email;
}

function displayName(request: Request, email: string): string {
  const raw = request.headers.get(FULL_NAME_HEADER)?.trim();
  if (!raw) return email;
  try {
    return decodeURIComponent(raw).trim() || email;
  } catch {
    return raw;
  }
}

export async function authorize(request: Request, env: Env): Promise<AuthorizedUser> {
  if (!env.DB) {
    throw new ApiError(503, "authorization_unavailable", "No se pudo verificar el acceso.");
  }
  const rawEmail = request.headers.get(EMAIL_HEADER);
  if (!rawEmail) {
    throw new ApiError(401, "sign_in_required", "Iniciá sesión con ChatGPT para continuar.");
  }
  const email = normalizeEmail(rawEmail);
  try {
    const allowed = await env.DB.prepare(
      `SELECT role FROM allowlist_entries
       WHERE normalized_email = ?1 AND active = 1`,
    )
      .bind(email)
      .first<AllowlistRow>();
    if (!allowed) {
      throw new ApiError(403, "access_denied", "Tu cuenta no tiene acceso a este curso.");
    }
    const name = displayName(request, email);
    await env.DB.prepare(
      `INSERT INTO users (normalized_email, display_name)
       VALUES (?1, ?2)
       ON CONFLICT(normalized_email) DO UPDATE SET
         display_name = excluded.display_name,
         updated_at = CURRENT_TIMESTAMP`,
    )
      .bind(email, name)
      .run();
    const user = await env.DB.prepare(
      "SELECT id FROM users WHERE normalized_email = ?1",
    )
      .bind(email)
      .first<UserRow>();
    if (!user) throw new Error("User upsert returned no row.");
    return { id: user.id, email, displayName: name, role: allowed.role };
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(503, "authorization_unavailable", "No se pudo verificar el acceso.");
  }
}

export function requireOwner(user: AuthorizedUser): void {
  if (user.role !== "owner") {
    throw new ApiError(403, "owner_required", "Esta operación requiere acceso de propietario.");
  }
}
