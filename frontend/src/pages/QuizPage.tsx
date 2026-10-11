import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { Attempt } from "../api/types";
import QuizRunner from "../components/QuizRunner";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";

export default function QuizPage() {
  const { topic, api } = useTopicContext();
  const { attemptId = "" } = useParams();
  const navigate = useNavigate();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const id = Number(attemptId);
    if (!Number.isInteger(id)) {
      setError("Identificador de intento inválido.");
      return;
    }
    api.getAttempt(id).then((value) => {
      if (value.finished_at) {
        navigate(`/t/${topic.slug}/review/${value.id}`, { replace: true });
      } else {
        setAttempt(value);
      }
    }).catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api, attemptId, navigate, topic.slug]);
  if (error) return <main className="shell"><p className="banner banner--error">{error}</p></main>;
  if (!attempt) return <main className="shell"><p>Cargando intento…</p></main>;
  return (
    <main className="shell">
      <TitleBlock
        title={attempt.label}
        backTo={`/t/${topic.slug}`}
        backLabel="Panel"
        chips={attempt.minutes_allowed ? [`${attempt.minutes_allowed} minutos`] : []}
      />
      <QuizRunner
        initialAttempt={attempt}
        api={api}
        onFinished={(finishResult) =>
          navigate(`/t/${topic.slug}/review/${attempt.id}`, {
            state: { finishResult },
          })
        }
      />
    </main>
  );
}
