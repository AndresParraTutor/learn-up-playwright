import { useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

import type { FaqEntry, Lab, LabCheckResult } from "../api/types";
import BadgeToast from "../components/BadgeToast";
import FaqSection from "../components/FaqSection";
import Markdown from "../components/Markdown";
import SelectionAsk from "../components/SelectionAsk";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";
import { IS_HOSTED } from "../config/runtime";
import { resolveBackNav } from "../lib/backNav";

export default function LabDetailPage() {
  const { topic, api } = useTopicContext();
  const { slug = "" } = useParams();
  const location = useLocation();
  const articleRef = useRef<HTMLElement>(null);
  const [lab, setLab] = useState<Lab | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [result, setResult] = useState<LabCheckResult | null>(null);
  const [reveals, setReveals] = useState<
    Record<number, { hint?: string; answer?: string }>
  >({});
  const [error, setError] = useState<string | null>(null);
  const back = resolveBackNav(location.state, {
    from: `/t/${topic.slug}/labs`,
    label: "Prácticas",
  });

  async function reload() {
    const value = await api.getLab(slug);
    setLab(value);
    setAnswers((current) =>
      current.length === value.self_check.length
        ? current
        : value.self_check.map(() => ""),
    );
  }
  useEffect(() => {
    reload().catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api, slug]);
  if (error) return <main className="shell"><p className="banner banner--error">{error}</p></main>;
  if (!lab) return <main className="shell"><p>Cargando práctica…</p></main>;
  const faqHighlights = lab.faq
    .filter((entry): entry is FaqEntry & { selected_text: string } =>
      Boolean(entry.selected_text),
    )
    .map((entry) => ({ index: entry.index, text: entry.selected_text }));
  return (
    <main className="shell">
      <TitleBlock
        title={lab.title}
        eyebrow={`${lab.domain_code} · ${lab.objective_code} · ${lab.objective_title}`}
        backTo={back.from}
        backLabel={back.label}
      />
      <article ref={articleRef}>
        <section className="panel">
          <h2>Escenario</h2>
          <Markdown faqHighlights={faqHighlights}>{lab.scenario_markdown}</Markdown>
          <h2>Preparación</h2>
          <pre><code>{lab.setup_sql}</code></pre>
          <h2>Tarea</h2>
          <Markdown faqHighlights={faqHighlights}>{lab.task_markdown}</Markdown>
        </section>
        <section className="panel">
          <h2>Autocomprobación</h2>
          {lab.self_check.map((check, index) => (
            <div className="self-check" key={check.position}>
              <Markdown>{check.prompt_markdown}</Markdown>
              <input
                type="text"
                value={answers[index] ?? ""}
                onChange={(event) =>
                  setAnswers((current) =>
                    current.map((value, answerIndex) =>
                      answerIndex === index ? event.target.value : value,
                    ),
                  )
                }
              />
              <div className="self-check__reveal-actions">
                <button
                  type="button"
                  className="btn btn--ghost btn--small"
                  disabled={!check.hint_available}
                  onClick={() =>
                    void (async () => {
                      if (reveals[check.position]?.hint) return;
                      const value = await api.getLabHint(lab.slug, check.position);
                      setReveals((current) => ({
                        ...current,
                        [check.position]: {
                          ...current[check.position],
                          hint: value.hint,
                        },
                      }));
                    })()
                  }
                >
                  Pista
                </button>
                <button
                  type="button"
                  className="btn btn--ghost btn--small"
                  onClick={() =>
                    void (async () => {
                      if (reveals[check.position]?.answer) return;
                      const value = await api.getLabAnswer(lab.slug, check.position);
                      setReveals((current) => ({
                        ...current,
                        [check.position]: {
                          ...current[check.position],
                          answer: value.answer,
                        },
                      }));
                    })()
                  }
                >
                  Mostrar respuesta
                </button>
              </div>
              {reveals[check.position]?.hint && (
                <p className="self-check__reveal">Pista: {reveals[check.position].hint}</p>
              )}
              {reveals[check.position]?.answer && (
                <p className="self-check__reveal">
                  Respuesta: {reveals[check.position].answer}
                </p>
              )}
              {result && (
                <p className={result.results[index]?.passed ? "success" : "error"}>
                  {result.results[index]?.passed ? "Correcto" : "Revisá esta respuesta"}
                </p>
              )}
            </div>
          ))}
          <button
            type="button"
            className="btn btn--primary"
            onClick={() =>
              void api.checkLab(lab.slug, answers).then((value) => {
                setResult(value);
                if (value.passed) void reload();
              })
            }
          >
            Comprobar
          </button>
          {result?.passed && (
            <div className="panel panel--highlight">
              <strong>Práctica completada.</strong>
              <p>{lab.expected_result}</p>
            </div>
          )}
        </section>
        <FaqSection
          entries={lab.faq}
          onDelete={async (index) => {
            await api.deleteLabFaq(lab.slug, index);
            await reload();
          }}
        />
        <p className="disclaimer">
          Este texto fue generado automáticamente por un modelo de lenguaje y
          puede contener errores. Leelo con criterio y verificá por otra vía
          cualquier tema sensible.
        </p>
      </article>
      <SelectionAsk
        containerRef={articleRef}
        onAsk={(selected, question, onDelta, full) =>
          api.askLab(lab.slug, selected, question, onDelta, full)
        }
        onAnswered={(entry) =>
          setLab((current) =>
            current ? { ...current, faq: [...current.faq, entry] } : current,
          )
        }
        getQuotaStatus={IS_HOSTED ? api.getQuotaStatus : undefined}
      />
      <BadgeToast badges={result?.badges_earned ?? []} />
    </main>
  );
}
