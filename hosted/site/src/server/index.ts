import { authorize, requireOwner, type AuthorizedUser } from "./auth";
import {
  getAbout,
  getDashboard,
  getLab,
  getLesson,
  getTopic,
  listDomains,
  listLabs,
  listLessons,
  listTopics,
} from "./catalog";
import {
  checkLab,
  createAttempt,
  deleteFaq,
  finishAttempt,
  getAttempt,
  getLabAnswer,
  getLabHint,
  listBadges,
  recordLessonOpened,
  reviewAttempt,
  submitAttemptResponse,
} from "./learning";
import {
  ApiError,
  empty,
  htmlProblem,
  isNavigationRequest,
  json,
  methodNotAllowed,
  problem,
} from "./http";
import { serveMedia } from "./media";
import type { Env, ExecutionContext } from "./platform";
import {
  askQuestion,
  getQuotaStatus,
  listAmbiguousRequests,
  reconcileAmbiguousRequest,
} from "./qa";

const staticAssetPattern = /\.(?:css|gif|ico|jpe?g|js|png|svg|webp|woff2?)$/i;

async function apiRoute(
  request: Request,
  env: Env,
  user: AuthorizedUser,
): Promise<Response> {
  const url = new URL(request.url);
  const { pathname } = url;
  if (pathname === "/api/session") {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json({ email: user.email, display_name: user.displayName, role: user.role });
  }
  if (pathname === "/api/admin/seed-status") {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    requireOwner(user);
    if (!env.DB) throw new ApiError(503, "database_unavailable", "La base alojada no está disponible.");
    const release = await env.DB.prepare(
      "SELECT topic_slug, content_version, source_digest, status, activated_at FROM content_releases ORDER BY created_at DESC LIMIT 1",
    ).first();
    return json({ release, seed_enabled: env.LEARNUP_SEED_ENABLED === "true" });
  }
  if (pathname === "/api/admin/qa/ambiguous") {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    requireOwner(user);
    return json(await listAmbiguousRequests(env));
  }
  const reconciliationMatch = /^\/api\/admin\/qa\/ambiguous\/([0-9a-f-]+)\/reconcile$/i.exec(pathname);
  if (reconciliationMatch) {
    if (request.method !== "POST") return methodNotAllowed(["POST"]);
    requireOwner(user);
    return json(await reconcileAmbiguousRequest(request, env, user, reconciliationMatch[1]));
  }
  if (pathname === "/api/topics") {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await listTopics(env, user));
  }
  const topicMatch = /^\/api\/topics\/([a-z0-9-]+)$/.exec(pathname);
  if (topicMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await getTopic(env, topicMatch[1]));
  }
  const domainsMatch = /^\/api\/t\/([a-z0-9-]+)\/domains$/.exec(pathname);
  if (domainsMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await listDomains(env, domainsMatch[1]));
  }
  const dashboardMatch = /^\/api\/t\/([a-z0-9-]+)\/progress\/dashboard$/.exec(pathname);
  if (dashboardMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await getDashboard(env, user, dashboardMatch[1]));
  }
  const badgesMatch = /^\/api\/t\/([a-z0-9-]+)\/progress\/badges$/.exec(pathname);
  if (badgesMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    await getTopic(env, badgesMatch[1]);
    return json(await listBadges(env, user));
  }

  const quotaMatch = /^\/api\/t\/([a-z0-9-]+)\/quota$/.exec(pathname);
  if (quotaMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    await getTopic(env, quotaMatch[1]);
    return json(await getQuotaStatus(env, user));
  }
  const lessonsMatch = /^\/api\/t\/([a-z0-9-]+)\/lessons$/.exec(pathname);
  if (lessonsMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await listLessons(env, lessonsMatch[1]));
  }
  const objectiveLessonsMatch = /^\/api\/t\/([a-z0-9-]+)\/lessons\/objective\/([0-9.]+)$/.exec(pathname);
  if (objectiveLessonsMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await listLessons(env, objectiveLessonsMatch[1], objectiveLessonsMatch[2]));
  }
  const lessonMatch = /^\/api\/t\/([a-z0-9-]+)\/lessons\/([a-z0-9-]+)$/.exec(pathname);
  if (lessonMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    await recordLessonOpened(env, user, lessonMatch[1], lessonMatch[2]);
    return json(await getLesson(env, user, lessonMatch[1], lessonMatch[2]));
  }
  const lessonQuestionMatch = /^\/api\/t\/([a-z0-9-]+)\/lessons\/([a-z0-9-]+)\/questions$/.exec(pathname);
  if (lessonQuestionMatch) {
    if (request.method !== "POST") return methodNotAllowed(["POST"]);
    return askQuestion(request, env, user, lessonQuestionMatch[1], "lesson", lessonQuestionMatch[2]);
  }
  const lessonFaqMatch = /^\/api\/t\/([a-z0-9-]+)\/lessons\/([a-z0-9-]+)\/faq\/(\d+)$/.exec(pathname);
  if (lessonFaqMatch) {
    if (request.method !== "DELETE") return methodNotAllowed(["DELETE"]);
    await deleteFaq(request, env, user, lessonFaqMatch[1], "lesson", lessonFaqMatch[2], lessonFaqMatch[3]);
    return empty();
  }
  const labsMatch = /^\/api\/t\/([a-z0-9-]+)\/labs$/.exec(pathname);
  if (labsMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await listLabs(env, user, labsMatch[1]));
  }
  const labMatch = /^\/api\/t\/([a-z0-9-]+)\/labs\/([a-z0-9-]+)$/.exec(pathname);
  if (labMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await getLab(env, user, labMatch[1], labMatch[2]));
  }
  const labCheckMatch = /^\/api\/t\/([a-z0-9-]+)\/labs\/([a-z0-9-]+)\/check$/.exec(pathname);
  if (labCheckMatch) {
    if (request.method !== "POST") return methodNotAllowed(["POST"]);
    return json(await checkLab(request, env, user, labCheckMatch[1], labCheckMatch[2]));
  }
  const labHintMatch = /^\/api\/t\/([a-z0-9-]+)\/labs\/([a-z0-9-]+)\/self-check\/(\d+)\/hint$/.exec(pathname);
  if (labHintMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await getLabHint(env, labHintMatch[1], labHintMatch[2], labHintMatch[3]));
  }
  const labAnswerMatch = /^\/api\/t\/([a-z0-9-]+)\/labs\/([a-z0-9-]+)\/self-check\/(\d+)\/answer$/.exec(pathname);
  if (labAnswerMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await getLabAnswer(env, labAnswerMatch[1], labAnswerMatch[2], labAnswerMatch[3]));
  }
  const labQuestionMatch = /^\/api\/t\/([a-z0-9-]+)\/labs\/([a-z0-9-]+)\/questions$/.exec(pathname);
  if (labQuestionMatch) {
    if (request.method !== "POST") return methodNotAllowed(["POST"]);
    return askQuestion(request, env, user, labQuestionMatch[1], "lab", labQuestionMatch[2]);
  }
  const labFaqMatch = /^\/api\/t\/([a-z0-9-]+)\/labs\/([a-z0-9-]+)\/faq\/(\d+)$/.exec(pathname);
  if (labFaqMatch) {
    if (request.method !== "DELETE") return methodNotAllowed(["DELETE"]);
    await deleteFaq(request, env, user, labFaqMatch[1], "lab", labFaqMatch[2], labFaqMatch[3]);
    return empty();
  }
  const attemptsMatch = /^\/api\/t\/([a-z0-9-]+)\/attempts$/.exec(pathname);
  if (attemptsMatch) {
    if (request.method !== "POST") return methodNotAllowed(["POST"]);
    return json(await createAttempt(request, env, user, attemptsMatch[1]), { status: 201 });
  }
  const attemptMatch = /^\/api\/t\/([a-z0-9-]+)\/attempts\/(\d+)$/.exec(pathname);
  if (attemptMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await getAttempt(env, user, attemptMatch[1], attemptMatch[2]));
  }
  const responseMatch = /^\/api\/t\/([a-z0-9-]+)\/attempts\/(\d+)\/responses$/.exec(pathname);
  if (responseMatch) {
    if (request.method !== "POST") return methodNotAllowed(["POST"]);
    return json(await submitAttemptResponse(request, env, user, responseMatch[1], responseMatch[2]));
  }
  const finishMatch = /^\/api\/t\/([a-z0-9-]+)\/attempts\/(\d+)\/finish$/.exec(pathname);
  if (finishMatch) {
    if (request.method !== "POST") return methodNotAllowed(["POST"]);
    return json(await finishAttempt(request, env, user, finishMatch[1], finishMatch[2]));
  }
  const reviewMatch = /^\/api\/t\/([a-z0-9-]+)\/attempts\/(\d+)\/review$/.exec(pathname);
  if (reviewMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await reviewAttempt(env, user, reviewMatch[1], reviewMatch[2]));
  }
  const aboutMatch = /^\/api\/t\/([a-z0-9-]+)\/about$/.exec(pathname);
  if (aboutMatch) {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json(await getAbout(env, aboutMatch[1]));
  }
  throw new ApiError(404, "api_not_found", "No se encontró la función solicitada.");
}

async function serveApp(request: Request, env: Env): Promise<Response> {
  if (!env.ASSETS) {
    throw new ApiError(503, "assets_unavailable", "La aplicación alojada no está disponible.");
  }
  const url = new URL(request.url);
  url.pathname = "/index.html";
  url.search = "";
  return env.ASSETS.fetch(new Request(url, { method: "GET", headers: request.headers }));
}

export async function handleRequest(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  if (url.pathname === "/api/health") {
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return json({ status: "ok" });
  }
  if (staticAssetPattern.test(url.pathname) && env.ASSETS && (request.method === "GET" || request.method === "HEAD")) {
    return env.ASSETS.fetch(request);
  }
  try {
    const user = await authorize(request, env);
    if (url.pathname.startsWith("/media/")) return await serveMedia(request, env, user);
    if (url.pathname.startsWith("/api/")) return await apiRoute(request, env, user);
    if (request.method !== "GET") return methodNotAllowed(["GET"]);
    return await serveApp(request, env);
  } catch (error) {
    const apiError =
      error instanceof ApiError
        ? error
        : new ApiError(500, "internal_error", "Ocurrió un error inesperado.");
    if (apiError.status === 401 && isNavigationRequest(request)) {
      return Response.redirect(new URL("/signin-with-chatgpt", request.url), 302);
    }
    if (isNavigationRequest(request)) return htmlProblem(apiError);
    return problem(apiError);
  }
}

export default {
  fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    return handleRequest(request, env);
  },
};

export { normalizeEmail } from "./auth";
export { parseByteRange } from "./media";
export { quotaWindows } from "./qa";
