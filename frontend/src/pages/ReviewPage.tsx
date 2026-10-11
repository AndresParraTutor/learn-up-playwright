import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

import type { FinishResult, Review } from "../api/types";
import BadgeToast from "../components/BadgeToast";
import Markdown from "../components/Markdown";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";
import { stripCorrectPrefix } from "../lib/grading";

export default function ReviewPage() {
  const { topic, api } = useTopicContext();
  const { attemptId = "" } = useParams();
  const location = useLocation();
  const finishResult = (
    location.state as { finishResult?: FinishResult } | null
  )?.finishResult;
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.getReview(Number(attemptId)).then(setReview).catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api, attemptId]);
  if (error) return <main className="shell"><p className="banner banner--error">{error}</p></main>;
  if (!review) return <main className="shell"><p>Cargando revisión…</p></main>;
  const raw = review.score_raw ?? 0;
  const percentage =
    review.total_questions > 0
      ? ((raw / review.total_questions) * 100).toFixed(1)
      : "0.0";
  return (
    <main className="shell">
      <TitleBlock
        title="Revisión del intento"
        backTo={`/t/${topic.slug}`}
        backLabel="Panel"
        chips={[
          `${raw}/${review.total_questions} (${percentage}%)`,
          review.passed === null
            ? "Práctica"
            : review.passed
              ? "Aprobado"
              : "No aprobado",
          ...(review.content_version && review.content_version !== topic.syllabus_version
            ? [`Contenido ${review.content_version}`]
            : []),
        ]}
      />
      {review.questions.map((question, index) => (
        <article className="panel" key={question.question_id}>
          <p className="mono">
            Pregunta {index + 1} · {question.is_correct ? "Correcta" : "Incorrecta"}
          </p>
          <Markdown>{question.stem_markdown}</Markdown>
          {question.choices.map((choice) => {
            const selected = question.selected_choice_ids.includes(choice.id);
            return (
              <div className="choice-feedback" key={choice.id}>
                <strong>
                  {choice.is_correct ? "✓" : "×"} {choice.text_markdown}
                  {selected ? " · tu selección" : ""}
                </strong>
                <Markdown>
                  {stripCorrectPrefix(
                    choice.explanation_markdown,
                    choice.is_correct,
                    selected,
                  )}
                </Markdown>
              </div>
            );
          })}
          <Markdown>{question.explanation_markdown}</Markdown>
        </article>
      ))}
      <BadgeToast badges={finishResult?.badges_earned ?? []} />
    </main>
  );
}
