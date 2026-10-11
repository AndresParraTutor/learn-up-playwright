import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

import type { FaqEntry, Lesson } from "../api/types";
import TeachingArticle from "../components/TeachingArticle";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";
import { resolveBackNav } from "../lib/backNav";
import { IS_HOSTED } from "../config/runtime";

export default function LessonDetailPage() {
  const { topic, api } = useTopicContext();
  const { slug, objectiveCode } = useParams();
  const location = useLocation();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fallback = {
    from: `/t/${topic.slug}/lessons`,
    label: "Lecciones",
  };
  const back = resolveBackNav(location.state, fallback);

  async function loadLesson() {
    if (slug) return api.getLessonBySlug(slug);
    if (objectiveCode) {
      const matches = await api.listLessonsForObjective(objectiveCode);
      if (matches.length === 0) throw new Error("No hay una lección para este objetivo.");
      return api.getLessonBySlug(matches[0].slug);
    }
    throw new Error("Falta identificar la lección.");
  }

  useEffect(() => {
    loadLesson().then(setLesson).catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api, slug, objectiveCode]);

  if (error) return <main className="shell"><p className="banner banner--error">{error}</p></main>;
  if (!lesson) return <main className="shell"><p>Cargando lección…</p></main>;
  const videoPending = lesson.body_markdown.includes("[placeholder]");
  return (
    <main className="shell">
      <TitleBlock
        title={lesson.title}
        eyebrow={`${lesson.domain_code} · ${lesson.objective_code} · ${lesson.objective_title}`}
        backTo={back.from}
        backLabel={back.label}
      />
      <TeachingArticle
        bodyMarkdown={lesson.body_markdown}
        whyItMattersMarkdown={lesson.why_it_matters_markdown}
        faq={lesson.faq}
        onAsk={(selected, question, onDelta, full) =>
          api.askLesson(lesson.slug, selected, question, onDelta, full)
        }
        onAnswered={(entry: FaqEntry) =>
          setLesson((current) =>
            current ? { ...current, faq: [...current.faq, entry] } : current,
          )
        }
        onDeleteFaq={async (index) => {
          await api.deleteLessonFaq(lesson.slug, index);
          setLesson(await api.getLessonBySlug(lesson.slug));
        }}
        getQuotaStatus={IS_HOSTED ? api.getQuotaStatus : undefined}
        video={
          videoPending && !IS_HOSTED
            ? {
                onGenerate: () => api.generateLessonVideo(lesson.slug),
                onPollStatus: () => api.getLessonVideoStatus(lesson.slug),
                onReady: async () => setLesson(await api.getLessonBySlug(lesson.slug)),
              }
            : undefined
        }
      />
    </main>
  );
}
