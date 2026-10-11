import assert from "node:assert/strict";
import test from "node:test";

import {
  handleRequest,
  normalizeEmail,
  parseByteRange,
} from "../dist/server/index.js";

class FakeStatement {
  constructor(db, query) {
    this.db = db;
    this.query = query.replace(/\s+/g, " ").trim();
    this.values = [];
  }

  bind(...values) {
    this.values = values;
    return this;
  }

  async first() {
    if (this.db.fail) throw new Error("simulated D1 failure");
    if (this.query.includes("FROM allowlist_entries")) {
      const role = this.db.allowlist.get(this.values[0]);
      return role ? { role } : null;
    }
    if (this.query.includes("SELECT id FROM users")) {
      const id = this.db.users.get(this.values[0]);
      return id ? { id } : null;
    }
    if (this.query.includes("FROM media_objects")) return this.db.media;
    return null;
  }

  async all() {
    if (this.db.fail) throw new Error("simulated D1 failure");
    return { success: true, results: [] };
  }

  async run() {
    if (this.db.fail) throw new Error("simulated D1 failure");
    if (this.query.startsWith("INSERT INTO users")) {
      if (!this.db.users.has(this.values[0])) {
        this.db.users.set(this.values[0], this.db.users.size + 1);
      }
    }
    return { success: true };
  }
}

class FakeD1 {
  constructor({ allowlist = {}, media = null, fail = false } = {}) {
    this.allowlist = new Map(Object.entries(allowlist));
    this.users = new Map();
    this.media = media;
    this.fail = fail;
  }

  prepare(query) {
    return new FakeStatement(this, query);
  }

  async batch() {
    return [];
  }
}

function request(path, { email, name, method = "GET", accept = "application/json", headers = {} } = {}) {
  const values = new Headers(headers);
  values.set("Accept", accept);
  if (email) values.set("oai-authenticated-user-email", email);
  if (name) values.set("oai-authenticated-user-full-name", name);
  return new Request(`https://learn-up.example${path}`, { method, headers: values });
}

test("normalizes authenticated email and rejects invalid identity", () => {
  assert.equal(normalizeEmail(" Partner@Example.COM "), "partner@example.com");
  assert.throws(() => normalizeEmail("invalid"), /identidad autenticada/i);
});

test("parses bounded, open-ended, and suffix byte ranges", () => {
  assert.deepEqual(parseByteRange("bytes=10-19", 100), { offset: 10, length: 10 });
  assert.deepEqual(parseByteRange("bytes=90-", 100), { offset: 90, length: 10 });
  assert.deepEqual(parseByteRange("bytes=-7", 100), { offset: 93, length: 7 });
  assert.throws(() => parseByteRange("bytes=100-101", 100), /rango solicitado/i);
  assert.throws(() => parseByteRange("bytes=0-1,4-5", 100), /rango solicitado/i);
});

test("keeps health generic and public", async () => {
  const response = await handleRequest(request("/api/health"), {});
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: "ok" });
});

test("redirects unsigned navigation to Sign in with ChatGPT", async () => {
  const response = await handleRequest(
    request("/t/playwright", { accept: "text/html" }),
    { DB: new FakeD1() },
  );
  assert.equal(response.status, 302);
  assert.equal(response.headers.get("location"), "https://learn-up.example/signin-with-chatgpt");
});

test("rejects unsigned and non-allowlisted API access", async () => {
  const unsigned = await handleRequest(request("/api/session"), { DB: new FakeD1() });
  assert.equal(unsigned.status, 401);
  assert.equal((await unsigned.json()).code, "sign_in_required");

  const denied = await handleRequest(
    request("/api/session", { email: "stranger@example.com" }),
    { DB: new FakeD1() },
  );
  assert.equal(denied.status, 403);
  assert.equal((await denied.json()).code, "access_denied");
});

test("uses only platform identity and returns an allowlisted session", async () => {
  const db = new FakeD1({ allowlist: { "partner@example.com": "learner" } });
  const response = await handleRequest(
    request("/api/session", {
      email: "Partner@Example.com",
      name: "Socio%20de%20confianza",
    }),
    { DB: db },
  );
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    email: "partner@example.com",
    display_name: "Socio de confianza",
    role: "learner",
  });
  assert.equal(db.users.get("partner@example.com"), 1);
});

test("fails closed when authorization storage fails", async () => {
  const response = await handleRequest(
    request("/api/session", { email: "owner@example.com" }),
    { DB: new FakeD1({ fail: true }) },
  );
  assert.equal(response.status, 503);
  assert.equal((await response.json()).code, "authorization_unavailable");
});

test("fails closed when the expected content release is not configured", async () => {
  const response = await handleRequest(
    request("/api/topics", { email: "owner@example.com" }),
    { DB: new FakeD1({ allowlist: { "owner@example.com": "owner" } }) },
  );
  assert.equal(response.status, 503);
  assert.equal((await response.json()).code, "content_configuration_invalid");
});

test("does not touch R2 before authorization", async () => {
  let touched = false;
  const bucket = {
    async head() { touched = true; return null; },
    async get() { touched = true; return null; },
  };
  const response = await handleRequest(request("/media/playwright/demo.mp4"), {
    DB: new FakeD1(),
    BUCKET: bucket,
  });
  assert.equal(response.status, 401);
  assert.equal(touched, false);
});

test("serves an authorized R2 byte range privately", async () => {
  const bytes = new TextEncoder().encode("0123456789");
  const object = {
    key: "media/playwright/demo.mp4",
    size: bytes.length,
    etag: "etag",
    httpEtag: '"etag"',
    writeHttpMetadata(headers) { headers.set("Content-Type", "video/mp4"); },
  };
  const bucket = {
    async head() { return object; },
    async get(_key, options) {
      const range = options?.range ?? { offset: 0, length: bytes.length };
      const body = bytes.slice(range.offset, range.offset + range.length);
      return { ...object, range, body: new Blob([body]).stream() };
    },
  };
  const db = new FakeD1({
    allowlist: { "partner@example.com": "learner" },
    media: {
      object_key: object.key,
      content_type: "video/mp4",
      byte_size: bytes.length,
      sha256: "ignored-in-delivery-test",
    },
  });
  const response = await handleRequest(
    request("/media/playwright/demo.mp4", {
      email: "partner@example.com",
      headers: { Range: "bytes=2-5" },
    }),
    { DB: db, BUCKET: bucket, LEARNUP_EXPECTED_CONTENT_DIGEST: "a".repeat(64) },
  );
  assert.equal(response.status, 206);
  assert.equal(response.headers.get("content-range"), "bytes 2-5/10");
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.equal(await response.text(), "2345");
});

test("serves only generic static assets without authentication", async () => {
  const assets = { async fetch(req) { return new Response(new URL(req.url).pathname); } };
  const response = await handleRequest(request("/assets/app.js"), { ASSETS: assets });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "/assets/app.js");
});
