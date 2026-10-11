import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import type {
  Dashboard,
  Domain,
  LabListItem,
  ReviewQueueItem,
} from "../api/types";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";
import {
  usePersistedState,
  useScrollRestoration,
} from "../lib/usePageMemory";

export default function DashboardPage() {
  const { topic, api } = useTopicContext();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [domains, setDomains] = useState<Domain[] | null>(null);
  const [labs, setLabs] = useState<LabListItem[] | null>(
    topic.labs_enabled ? null : [],
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = usePersistedState<Record<string, boolean>>(
    `expanded:/t/${topic.slug}`,
    {},
  );

  async function load() {
    const [dashboardValue, domainValue] = await Promise.all([
      api.getDashboard(),
      api.listDomains(),
    ]);
    setDashboard(dashboardValue);
    setDomains(domainValue);
  }
  useEffect(() => {
    load().catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api]);
  useEffect(() => {
    if (topic.labs_enabled) {
      api.listLabs().then(setLabs).catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : String(reason)),
      );
    }
  }, [api, topic.labs_enabled]);
  const ready = Boolean(
    dashboard && domains && (!topic.labs_enabled || labs !== null),
  );
  useScrollRestoration(ready);

  const queueMap = useMemo(
    () =>
      new Map(
        dashboard?.review_queue.map((item) => [
          item.objective_code,
          item.status,
        ]) ?? [],
      ),
    [dashboard],
  );
  const planByWeek = useMemo(() => {
    const result = new Map<number, Dashboard["study_plan"]>();
    dashboard?.study_plan.forEach((item) => {
      result.set(item.estimated_week, [
        ...(result.get(item.estimated_week) ?? []),
        item,
      ]);
    });
    return result;
  }, [dashboard]);

  async function startAttempt(request: {
    attempt_type: string;
    domain_code?: string;
    objective_code?: string;
  }) {
    setBusy(true);
    setError(null);
    try {
      const attempt = await api.createAttempt(request);
      const segment = attempt.attempt_type === "mock" ? "mock" : "quiz";
      navigate(`/t/${topic.slug}/${segment}/${attempt.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  if (error && !dashboard) {
    return <main className="shell"><p className="banner banner--error">{error}</p></main>;
  }
  if (!dashboard || !domains) {
    return <main className="shell"><p>Cargando panel…</p></main>;
  }
  return (
    <main className="shell shell--wide">
      <TitleBlock
        title={dashboard.exam_ready ? "Listo para avanzar" : "Tu panel de estudio"}
        eyebrow={`Syllabus ${topic.syllabus_version}`}
        lede="Dominio, práctica y repaso en un solo recorrido."
        chips={[
          `${dashboard.overall_ready_pct}% integral`,
          `${dashboard.xp} XP`,
        ]}
      />
      {error && <p className="banner banner--error">{error}</p>}
      <section className={`panel ${dashboard.exam_ready ? "panel--highlight" : ""}`}>
        <div className="row row--between">
          <div>
            <h2>{dashboard.exam_ready ? "GO" : "Seguí avanzando"}</h2>
            <p>Preparación integral: {dashboard.overall_ready_pct}%.</p>
          </div>
          <button
            className="btn btn--ghost"
            disabled={busy}
            onClick={() => void startAttempt({ attempt_type: "quick_drill" })}
          >
            Repaso rápido
          </button>
        </div>
        <div className="progress"><span style={{ width: `${dashboard.overall_ready_pct}%` }} /></div>
        {topic.assessment_enabled && (
          <button
            className="btn btn--primary"
            disabled={busy}
            onClick={() => void startAttempt({ attempt_type: "mock" })}
          >
            Iniciar evaluación final · {topic.assessment_question_count} preguntas ·{" "}
            {topic.assessment_minutes} min
          </button>
        )}
      </section>

      <section>
        <h2>Dominio por módulo</h2>
        {domains.map((domain) => {
          const readiness = dashboard.domain_readiness.find(
            (item) => item.code === domain.code,
          );
          return (
            <article className="panel" key={domain.code}>
              <button
                className="row row--between accordion-trigger"
                aria-expanded={Boolean(expanded[domain.code])}
                onClick={() =>
                  setExpanded((current) => ({
                    ...current,
                    [domain.code]: !current[domain.code],
                  }))
                }
              >
                <strong>{domain.code} · {domain.name}</strong>
                <span>{readiness?.ready_pct ?? 0}%</span>
              </button>
              <div className="progress">
                <span style={{ width: `${readiness?.ready_pct ?? 0}%` }} />
              </div>
              <button
                className="btn btn--ghost btn--small"
                disabled={busy}
                onClick={() =>
                  void startAttempt({
                    attempt_type: "domain_drill",
                    domain_code: domain.code,
                  })
                }
              >
                Practicar módulo
              </button>
              {expanded[domain.code] && (
                <ul>
                  {domain.objectives.map((objective) => {
                    const status = queueMap.get(objective.code);
                    const mastered = status === undefined || status === "due";
                    const week = dashboard.study_plan.find(
                      (item) => item.objective_code === objective.code,
                    )?.estimated_week;
                    return (
                      <li key={objective.code}>
                        <span>{mastered ? "✓" : "○"} {objective.code} · {objective.title} · semana {week}</span>{" "}
                        <button
                          className="btn btn--ghost btn--small"
                          disabled={busy}
                          onClick={() =>
                            void startAttempt({
                              attempt_type: "practice",
                              objective_code: objective.code,
                            })
                          }
                        >
                          Preguntas
                        </button>{" "}
                        <Link
                          to={`/t/${topic.slug}/lessons/objective/${objective.code}`}
                          state={{ from: `/t/${topic.slug}`, label: "Panel" }}
                        >
                          Lección
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </article>
          );
        })}
      </section>

      <section>
        <h2>Para repasar</h2>
        {dashboard.review_queue.length === 0 ? (
          <p>No hay objetivos pendientes.</p>
        ) : (
          <ul>
            {dashboard.review_queue.map((item: ReviewQueueItem) => (
              <li key={item.objective_code}>
                <Link
                  to={`/t/${topic.slug}/lessons/objective/${item.objective_code}`}
                  state={{ from: `/t/${topic.slug}`, label: "Panel" }}
                >
                  {item.objective_code} · {item.objective_title}
                </Link>{" "}
                <span className="chip">
                  {item.status === "weak"
                    ? "débil"
                    : item.status === "due"
                      ? "vence hoy"
                      : "nuevo"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {topic.labs_enabled && (
        <section>
          <h2>Prácticas · {labs?.filter((lab) => lab.passed).length ?? 0} de {labs?.length ?? 0}</h2>
          {labs?.length === 0 && <p>Todavía no hay prácticas.</p>}
          <div className="card-list">
            {labs?.map((lab) => (
              <Link
                className="card-link panel"
                to={`/t/${topic.slug}/labs/${lab.slug}`}
                state={{ from: `/t/${topic.slug}`, label: "Panel" }}
                key={lab.id}
              >
                <span className="card-link__title">{lab.passed ? "✓ " : ""}{lab.title}</span>
                <span className="card-link__meta">{lab.objective_code}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2>Plan sugerido</h2>
        {[...planByWeek.entries()].map(([week, items]) => (
          <details key={week}>
            <summary>Semana {week} · {items.length} objetivos</summary>
            <ul>
              {items.map((item) => (
                <li key={item.objective_code}>
                  <Link
                    to={`/t/${topic.slug}/lessons/objective/${item.objective_code}`}
                    state={{ from: `/t/${topic.slug}`, label: "Panel" }}
                  >
                    {item.objective_code} · {item.objective_title}
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </section>

      <section>
        <h2>Historial de intentos</h2>
        {dashboard.attempt_history.length === 0 ? (
          <p>Todavía no hay intentos.</p>
        ) : (
          <table className="table">
            <thead><tr><th>Tipo</th><th>Resultado</th><th>Acción</th></tr></thead>
            <tbody>
              {dashboard.attempt_history.map((attempt) => (
                <tr key={attempt.id}>
                  <td>{attempt.attempt_type}</td>
                  <td>{attempt.score_raw ?? "—"}/{attempt.total_questions}</td>
                  <td>
                    {attempt.finished_at ? (
                      <Link to={`/t/${topic.slug}/review/${attempt.id}`}>
                        Revisar{attempt.release_active === false ? " versión anterior" : ""}
                      </Link>
                    ) : attempt.release_active === false ? (
                      <span className="muted">Versión retirada</span>
                    ) : (
                      <Link to={`/t/${topic.slug}/${attempt.attempt_type === "mock" ? "mock" : "quiz"}/${attempt.id}`}>
                        Continuar
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
