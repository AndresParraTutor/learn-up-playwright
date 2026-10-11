import { ApiRequestError, apiFetch, apiJson } from "./client";
import type {
  About,
  AskOutcome,
  Attempt,
  Badge,
  ContentId,
  Dashboard,
  Domain,
  FinishResult,
  FaqEntry,
  Lab,
  LabCheckResult,
  LabListItem,
  Lesson,
  LessonListItem,
  QuotaStatus,
  ResponseResult,
  Review,
  StreamEvent,
  Topic,
  TopicSummary,
  VideoStatus,
} from "./types";

export const listTopics = () => apiJson<TopicSummary[]>("/api/topics");
export const getTopic = (slug: string) =>
  apiJson<Topic>(`/api/topics/${encodeURIComponent(slug)}`);

async function askStream(
  url: string,
  selectedText: string,
  question: string,
  onDelta: (text: string) => void,
  useFullSources: boolean,
  idempotencyKey: string = crypto.randomUUID(),
): Promise<AskOutcome> {
  const response = await apiFetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify({
      selected_text: selectedText,
      question,
      use_full_sources: useFullSources,
    }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
      code?: string;
    } | null;
    throw new ApiRequestError(body?.detail ?? `Error HTTP ${response.status}`, body?.code);
  }
  if (!response.body) throw new Error("La respuesta no contiene un stream.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const lines = frame.split("\n");
      const eventName =
        lines.find((line) => line.startsWith("event: "))?.slice(7) ?? "message";
      const data = lines.find((line) => line.startsWith("data: "))?.slice(6);
      if (!data) continue;
      const event = JSON.parse(data) as StreamEvent | { error: string };
      if (eventName === "error" || "error" in event) {
        throw new Error("error" in event ? event.error : "Falló la respuesta.");
      }
      if (event.type === "delta") onDelta(event.delta);
      if (event.type === "insufficient") return { type: "insufficient" };
      if (event.type === "result") {
        const entry: FaqEntry = {
          index: event.index,
          question: event.question,
          selected_text: event.selected_text,
          answer_markdown: event.answer_markdown,
        };
        return { type: "answered", entry };
      }
    }
    if (done) break;
  }
  throw new Error("El stream terminó sin una respuesta final.");
}

export function createTopicApi(topicSlug: string) {
  const encoded = encodeURIComponent(topicSlug);
  const base = `/api/t/${encoded}`;
  return {
    getTopic: () => getTopic(topicSlug),
    listDomains: () => apiJson<Domain[]>(`${base}/domains`),
    getDashboard: () => apiJson<Dashboard>(`${base}/progress/dashboard`),
    getQuotaStatus: () => apiJson<QuotaStatus>(`${base}/quota`),
    listLessons: () => apiJson<LessonListItem[]>(`${base}/lessons`),
    listLessonsForObjective: (code: string) =>
      apiJson<LessonListItem[]>(
        `${base}/lessons/objective/${encodeURIComponent(code)}`,
      ),
    getLessonBySlug: (slug: string) =>
      apiJson<Lesson>(`${base}/lessons/${encodeURIComponent(slug)}`),
    askLesson: (
      slug: string,
      selected: string,
      question: string,
      onDelta: (text: string) => void,
      useFullSources: boolean,
      idempotencyKey?: string,
    ) =>
      askStream(
        `${base}/lessons/${encodeURIComponent(slug)}/questions`,
        selected,
        question,
        onDelta,
        useFullSources,
        idempotencyKey,
      ),
    deleteLessonFaq: (slug: string, index: number) =>
      apiJson<void>(
        `${base}/lessons/${encodeURIComponent(slug)}/faq/${index}`,
        { method: "DELETE" },
      ),
    generateLessonVideo: (slug: string) =>
      apiJson<VideoStatus>(
        `${base}/lessons/${encodeURIComponent(slug)}/video/generate`,
        { method: "POST" },
      ),
    getLessonVideoStatus: (slug: string) =>
      apiJson<VideoStatus>(
        `${base}/lessons/${encodeURIComponent(slug)}/video/status`,
      ),
    createAttempt: (request: {
      attempt_type: string;
      domain_code?: string;
      objective_code?: string;
      question_count?: number;
    }) =>
      apiJson<Attempt>(`${base}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }),
    getAttempt: (id: number) =>
      apiJson<Attempt>(`${base}/attempts/${id}`),
    submitResponse: (
      id: number,
      questionId: ContentId,
      selectedChoiceIds: ContentId[],
    ) =>
      apiJson<ResponseResult>(`${base}/attempts/${id}/responses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: questionId,
          selected_choice_ids: selectedChoiceIds,
        }),
      }),
    finishAttempt: (id: number) =>
      apiJson<FinishResult>(`${base}/attempts/${id}/finish`, {
        method: "POST",
      }),
    getReview: (id: number) =>
      apiJson<Review>(`${base}/attempts/${id}/review`),
    listLabs: () => apiJson<LabListItem[]>(`${base}/labs`),
    getLab: (slug: string) =>
      apiJson<Lab>(`${base}/labs/${encodeURIComponent(slug)}`),
    checkLab: (slug: string, answers: string[]) =>
      apiJson<LabCheckResult>(
        `${base}/labs/${encodeURIComponent(slug)}/check`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answers }),
        },
      ),
    getLabHint: (slug: string, position: number) =>
      apiJson<{ position: number; hint: string }>(
        `${base}/labs/${encodeURIComponent(slug)}/self-check/${position}/hint`,
      ),
    getLabAnswer: (slug: string, position: number) =>
      apiJson<{ position: number; answer: string }>(
        `${base}/labs/${encodeURIComponent(slug)}/self-check/${position}/answer`,
      ),
    askLab: (
      slug: string,
      selected: string,
      question: string,
      onDelta: (text: string) => void,
      useFullSources: boolean,
      idempotencyKey?: string,
    ) =>
      askStream(
        `${base}/labs/${encodeURIComponent(slug)}/questions`,
        selected,
        question,
        onDelta,
        useFullSources,
        idempotencyKey,
      ),
    deleteLabFaq: (slug: string, index: number) =>
      apiJson<void>(`${base}/labs/${encodeURIComponent(slug)}/faq/${index}`, {
        method: "DELETE",
      }),
    listBadges: () => apiJson<Badge[]>(`${base}/progress/badges`),
    getAbout: () => apiJson<About>(`${base}/about`),
  };
}

export type TopicApi = ReturnType<typeof createTopicApi>;
