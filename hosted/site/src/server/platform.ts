export interface D1Result<T = unknown> {
  results?: T[];
  success: boolean;
  meta?: Record<string, unknown>;
}

export interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  first<T = Record<string, unknown>>(columnName?: string): Promise<T | null>;
  all<T = Record<string, unknown>>(): Promise<D1Result<T>>;
  run<T = Record<string, unknown>>(): Promise<D1Result<T>>;
}

export interface D1Database {
  prepare(query: string): D1PreparedStatement;
  batch<T = unknown>(statements: D1PreparedStatement[]): Promise<D1Result<T>[]>;
}

export interface R2HTTPMetadata {
  contentType?: string;
  cacheControl?: string;
}

export interface R2Object {
  key: string;
  size: number;
  etag: string;
  httpEtag: string;
  httpMetadata?: R2HTTPMetadata;
  writeHttpMetadata(headers: Headers): void;
}

export interface R2ObjectBody extends R2Object {
  body: ReadableStream<Uint8Array>;
  range?: { offset: number; length: number };
}

export interface R2Bucket {
  head(key: string): Promise<R2Object | null>;
  get(
    key: string,
    options?: { range?: { offset: number; length: number } },
  ): Promise<R2ObjectBody | null>;
}

export interface AssetBinding {
  fetch(request: Request): Promise<Response>;
}

export interface Env {
  DB?: D1Database;
  BUCKET?: R2Bucket;
  ASSETS?: AssetBinding;
  OPENAI_API_KEY?: string;
  OPENAI_MODEL?: string;
  OPENAI_VECTOR_STORE_ID?: string;
  LEARNUP_QA_ENABLED?: string;
  LEARNUP_QA_CURRENT_CREDITS?: string;
  LEARNUP_QA_FULL_SOURCE_CREDITS?: string;
  LEARNUP_QA_USER_DAILY_CREDITS?: string;
  LEARNUP_QA_USER_MONTHLY_CREDITS?: string;
  LEARNUP_QA_GLOBAL_MONTHLY_CREDITS?: string;
  LEARNUP_QA_USER_REQUESTS_PER_MINUTE?: string;
  LEARNUP_QA_USER_MAX_CONCURRENCY?: string;
  LEARNUP_QA_SELECTION_MAX_CHARS?: string;
  LEARNUP_QA_QUESTION_MAX_CHARS?: string;
  LEARNUP_QA_MAX_OUTPUT_TOKENS?: string;
  LEARNUP_QA_MAX_RETRIEVAL_RESULTS?: string;
  LEARNUP_QA_MAX_TOOL_CALLS?: string;
  LEARNUP_QA_TIMEOUT_MS?: string;
  LEARNUP_SEED_ENABLED?: string;
  LEARNUP_EXPECTED_CONTENT_DIGEST?: string;
  LEARNUP_SAFETY_IDENTIFIER_SALT?: string;
}

export interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException?(): void;
}
