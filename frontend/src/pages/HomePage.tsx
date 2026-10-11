import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listTopics } from "../api/http";
import type { TopicSummary } from "../api/types";
import { IS_HOSTED } from "../config/runtime";

const TopicTransferPanel = !__LEARNUP_HOSTED__
  ? lazy(() =>
      import("../components/TopicTransferPanel").then((module) => ({
        default: module.TopicTransferPanel,
      })),
    )
  : null;

export default function HomePage() {
  const [topics, setTopics] = useState<TopicSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function refresh() {
    const values = await listTopics();
    setTopics(values);
    return values;
  }

  useEffect(() => {
    refresh()
      .then((values) => {
        if (values.length === 1) navigate(`/t/${values[0].slug}`, { replace: true });
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : String(reason)),
      );
  }, [navigate]);

  return (
    <main className="shell">
      <img className="home-logo" src="/learn-up-logo.webp" alt="learn-up" />
      <h1>Elegí un tema</h1>
      {error && <p className="banner banner--error">{error}</p>}
      {topics === null && <p>Cargando…</p>}
      <div className="card-list">
        {topics?.map((topic) => (
          <Link className="panel card-link" to={`/t/${topic.slug}`} key={topic.slug}>
            <span className="card-link__title">{topic.name}</span>
            <span>{topic.description}</span>
            <span className="card-link__meta">
              {topic.domain_count} módulos · {topic.objective_count} objetivos ·{" "}
              {topic.overall_ready_pct}% de preparación
            </span>
          </Link>
        ))}
      </div>
      {!IS_HOSTED && (
        <>
          <p className="muted">
            ＋ Para agregar un tema, invocá <span className="mono">$learn-up &lt;tema&gt;</span>{" "}
            en Codex. El contenido y el progreso permanecen separados.
          </p>
          {TopicTransferPanel && (
            <Suspense fallback={null}>
              <TopicTransferPanel
                onImported={async (slug) => {
                  await refresh();
                  navigate(`/t/${slug}`);
                }}
              />
            </Suspense>
          )}
        </>
      )}
    </main>
  );
}
