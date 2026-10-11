import { useEffect, useMemo, useRef, useState } from "react";

import type {
  Attempt,
  Badge,
  ContentId,
  FinishResult,
  ResponseResult,
} from "../api/types";
import type { TopicApi } from "../api/http";
import { stripCorrectPrefix } from "../lib/grading";
import BadgeToast from "./BadgeToast";
import Markdown from "./Markdown";

type Props = {
  initialAttempt: Attempt;
  api: TopicApi;
  onFinished: (result: FinishResult) => void;
};

export default function QuizRunner({ initialAttempt, api, onFinished }: Props) {
  const [attempt, setAttempt] = useState(initialAttempt);
  const questions = useMemo(
    () => [...attempt.questions].sort((a, b) => a.position - b.position),
    [attempt.questions],
  );
  const firstUnanswered = Math.max(
    0,
    questions.findIndex((question) => !question.answered),
  );
  const [currentIndex, setCurrentIndex] = useState(firstUnanswered);
  const [selections, setSelections] = useState<Record<ContentId, ContentId[]>>({});
  const [results, setResults] = useState<Record<ContentId, ResponseResult>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [badges, setBadges] = useState<Badge[]>([]);
  const [remaining, setRemaining] = useState<number | null>(() => {
    if (initialAttempt.minutes_allowed === null) return null;
    const elapsed = Math.floor(
      (Date.now() - new Date(initialAttempt.started_at).getTime()) / 1000,
    );
    return Math.max(0, initialAttempt.minutes_allowed * 60 - elapsed);
  });
  const finishing = useRef(false);

  async function finish() {
    if (finishing.current) return;
    finishing.current = true;
    setBusy(true);
    try {
      const value = await api.finishAttempt(attempt.id);
      onFinished(value);
    } catch (reason) {
      finishing.current = false;
      setError(reason instanceof Error ? reason.message : String(reason));
      setBusy(false);
    }
  }

  useEffect(() => {
    if (remaining === null) return;
    if (remaining <= 0) {
      void finish();
      return;
    }
    const handle = window.setInterval(
      () => setRemaining((value) => (value === null ? null : Math.max(0, value - 1))),
      1000,
    );
    return () => window.clearInterval(handle);
  }, [remaining]);

  const question = questions[currentIndex];
  if (!question) return <p>Este intento no contiene preguntas.</p>;
  const selected = selections[question.question_id] ?? [];
  const result = results[question.question_id];
  const answered = question.answered || Boolean(result);
  const allAnswered = questions.every(
    (item) => item.answered || Boolean(results[item.question_id]),
  );

  function toggleChoice(choiceId: ContentId) {
    if (answered) return;
    setSelections((current) => {
      const existing = current[question.question_id] ?? [];
      const next =
        question.question_type === "single"
          ? [choiceId]
          : existing.includes(choiceId)
            ? existing.filter((id) => id !== choiceId)
            : [...existing, choiceId];
      return { ...current, [question.question_id]: next };
    });
  }

  async function submit() {
    if (selected.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const value = await api.submitResponse(
        attempt.id,
        question.question_id,
        selected,
      );
      setResults((current) => ({ ...current, [question.question_id]: value }));
      setBadges(value.badges_earned);
      setAttempt((current) => ({
        ...current,
        questions: current.questions.map((item) =>
          item.question_id === question.question_id
            ? { ...item, answered: true, is_correct: value.is_correct }
            : item,
        ),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <div className="row row--between">
        <p className="mono">Pregunta {currentIndex + 1} de {questions.length}</p>
        {remaining !== null && (
          <p className="chip" aria-live="polite">
            {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}
          </p>
        )}
      </div>
      <nav className="progress-nav" aria-label="Preguntas">
        {questions.map((item, index) => {
          const correctness =
            results[item.question_id]?.is_correct ?? item.is_correct;
          const classes = [
            "progress-nav__item",
            index === currentIndex ? "is-current" : "",
            item.answered || results[item.question_id] ? "is-answered" : "",
            correctness === true ? "is-correct-nav" : "",
            correctness === false ? "is-incorrect-nav" : "",
          ].filter(Boolean).join(" ");
          return (
            <button
              className={classes}
              aria-label={`Pregunta ${index + 1}`}
              onClick={() => setCurrentIndex(index)}
              key={item.question_id}
            >
              {index + 1}
            </button>
          );
        })}
      </nav>
      <article className="panel">
        <Markdown>{question.stem_markdown}</Markdown>
        {question.question_type === "multi" && (
          <p className="muted">Seleccioná todas las respuestas correctas.</p>
        )}
        <div className="choice-list">
          {question.choices.map((choice) => (
            <label className="choice" key={choice.id}>
              <input
                type={question.question_type === "single" ? "radio" : "checkbox"}
                name={`question-${question.question_id}`}
                checked={selected.includes(choice.id)}
                disabled={answered}
                onChange={() => toggleChoice(choice.id)}
              />
              <Markdown>{choice.text_markdown}</Markdown>
            </label>
          ))}
        </div>
        {!answered && (
          <button
            className="btn btn--primary"
            disabled={busy || selected.length === 0}
            onClick={() => void submit()}
          >
            Enviar respuesta
          </button>
        )}
        {result && attempt.attempt_type === "mock" && (
          <div className="panel panel--highlight" role="status">
            <h3>Respuesta registrada</h3>
            <p>La corrección estará disponible cuando finalices la evaluación.</p>
          </div>
        )}
        {result && attempt.attempt_type !== "mock" && (
          <div className={result.is_correct ? "panel panel--highlight" : "banner banner--error"}>
            <h3>{result.is_correct ? "Correcto" : "Incorrecto"}</h3>
            <Markdown>{result.explanation_markdown ?? ""}</Markdown>
            {result.choices.map((choice) => {
              const wasSelected = selected.includes(choice.id);
              return (
                <div className="choice-feedback" key={choice.id}>
                  <strong>
                    {choice.is_correct ? "✓" : "×"} {choice.text_markdown}
                    {wasSelected ? " · tu selección" : ""}
                  </strong>
                  <Markdown>
                    {stripCorrectPrefix(
                      choice.explanation_markdown,
                      choice.is_correct,
                      wasSelected,
                    )}
                  </Markdown>
                </div>
              );
            })}
          </div>
        )}
      </article>
      <div className="row row--between">
        <button
          className="btn btn--ghost"
          disabled={currentIndex === 0}
          onClick={() => setCurrentIndex((value) => value - 1)}
        >
          Anterior
        </button>
        {currentIndex < questions.length - 1 && (
          <button
            className="btn btn--ghost"
            onClick={() => setCurrentIndex((value) => value + 1)}
          >
            Siguiente
          </button>
        )}
        {allAnswered && (
          <button className="btn btn--primary" disabled={busy} onClick={() => void finish()}>
            Finalizar intento
          </button>
        )}
      </div>
      {error && <p className="banner banner--error">{error}</p>}
      <BadgeToast badges={badges} />
    </section>
  );
}
