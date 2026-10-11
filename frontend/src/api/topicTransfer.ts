export type TopicImportReport = {
  topic_slug: string;
  archive_format: string;
  source_app_version: string;
  destination_app_version: string;
  mode: "new" | "update";
  status: "validated" | "installed";
  installed: string[];
  replaced: string[];
  merged_q_and_a: number;
  skipped_q_and_a: string[];
  ignored: string[];
  backup: string | null;
  trust_warning: string;
};

let apiToken: string | null = null;

export function setApiToken(token: string | null): void {
  apiToken = token;
}

export function getApiToken(): string | null {
  return apiToken;
}

function authHeaders(
  extra: Record<string, string> = {},
): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (apiToken) {
    headers["X-LearnUp-Token"] = apiToken;
  }
  return headers;
}

async function responseError(response: Response): Promise<Error> {
  const body = (await response.json().catch(() => null)) as {
    detail?: string;
  } | null;
  return new Error(
    body?.detail ?? `La transferencia del tema falló con HTTP ${response.status}`,
  );
}

export async function downloadTopic(
  topicSlug: string,
  token?: string,
): Promise<void> {
  const headers = authHeaders();
  if (token) {
    headers["X-LearnUp-Token"] = token;
  }
  const response = await fetch(
    `/api/t/${encodeURIComponent(topicSlug)}/export`,
    { headers },
  );
  if (!response.ok) throw await responseError(response);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${topicSlug}.learnup.zip`;
  link.click();
  URL.revokeObjectURL(url);
}

async function sendArchive(
  file: File,
  confirm: boolean,
  token?: string,
): Promise<TopicImportReport> {
  const params = new URLSearchParams({
    dry_run: String(!confirm),
    confirm: String(confirm),
  });
  const headers = authHeaders({ "Content-Type": "application/zip" });
  if (token) {
    headers["X-LearnUp-Token"] = token;
  }
  const response = await fetch(`/api/topics/import?${params}`, {
    method: "POST",
    headers,
    body: file,
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as TopicImportReport;
}

export function validateTopicArchive(
  file: File,
  token?: string,
): Promise<TopicImportReport> {
  return sendArchive(file, false, token);
}

export function importTopicArchive(
  file: File,
  token?: string,
): Promise<TopicImportReport> {
  return sendArchive(file, true, token);
}
