import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { LabListItem } from "../api/types";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";
import { useScrollRestoration } from "../lib/usePageMemory";

export default function LabsPage() {
  const { topic, api } = useTopicContext();
  const [labs, setLabs] = useState<LabListItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.listLabs().then(setLabs).catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api]);
  useScrollRestoration(labs !== null);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("es");
    if (!needle) return labs ?? [];
    return (labs ?? []).filter((lab) =>
      [
        lab.title,
        lab.objective_code,
        lab.objective_title,
        lab.scenario_markdown,
        lab.task_markdown,
        ...lab.self_check_markdown,
      ]
        .join(" ")
        .toLocaleLowerCase("es")
        .includes(needle),
    );
  }, [labs, query]);
  return (
    <main className="shell">
      <TitleBlock
        title="Prácticas"
        lede="Aplicá cada objetivo con una comprobación guiada."
        backTo={`/t/${topic.slug}`}
        backLabel="Panel"
      />
      <label className="search-box">
        <span className="mono">Buscar</span>
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Pipeline, assertion, fixture…"
        />
      </label>
      {error && <p className="banner banner--error">{error}</p>}
      {labs === null && !error && <p>Cargando prácticas…</p>}
      {query.trim() && labs && filtered.length === 0 && (
        <p>No hay prácticas que coincidan con “{query}”.</p>
      )}
      <div className="card-list">
        {filtered.map((lab) => (
          <Link className="panel card-link" to={lab.slug} key={lab.id}>
            <span className="card-link__title">
              {lab.passed ? "✓ " : ""}{lab.objective_code} · {lab.title}
            </span>
            <span className="card-link__meta">{lab.objective_title}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
