import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { LessonListItem, VideoJobStatus } from "../api/types";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";
import { useScrollRestoration } from "../lib/usePageMemory";

const videoMarkers: Partial<
  Record<VideoJobStatus, { icon: string; label: string }>
> = {
  done: { icon: "▶️", label: "Video disponible" },
  running: { icon: "⏳", label: "Video solicitado" },
  error: { icon: "⚠️", label: "Falló la generación del video" },
};

export default function LessonsPage() {
  const { topic, api } = useTopicContext();
  const [lessons, setLessons] = useState<LessonListItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.listLessons().then(setLessons).catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api]);
  useScrollRestoration(lessons !== null);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("es");
    if (!needle) return lessons ?? [];
    return (lessons ?? []).filter((lesson) =>
      [
        lesson.title,
        lesson.objective_code,
        lesson.objective_title,
        lesson.domain_name,
        lesson.body_markdown,
        lesson.why_it_matters_markdown,
      ]
        .join(" ")
        .toLocaleLowerCase("es")
        .includes(needle),
    );
  }, [lessons, query]);
  const groups = useMemo(() => {
    const result = new Map<string, LessonListItem[]>();
    filtered.forEach((lesson) => {
      const key = `${lesson.domain_code} · ${lesson.domain_name}`;
      result.set(key, [...(result.get(key) ?? []), lesson]);
    });
    return result;
  }, [filtered]);

  return (
    <main className="shell shell--wide">
      <TitleBlock
        title="Lecciones"
        lede="Recorré el programa o buscá un concepto en todo el contenido."
        backTo={`/t/${topic.slug}`}
        backLabel="Panel"
      />
      <label className="search-box">
        <span className="mono">Buscar</span>
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Localizadores, CI, límites…"
        />
      </label>
      {error && <p className="banner banner--error">{error}</p>}
      {lessons === null && !error && <p>Cargando lecciones…</p>}
      {query.trim() && lessons && filtered.length === 0 && (
        <p>No hay lecciones que coincidan con “{query}”.</p>
      )}
      {[...groups.entries()].map(([domain, items]) => (
        <section key={domain}>
          <h2>{domain}</h2>
          <div className="card-list">
            {items.map((lesson) => {
              const marker = videoMarkers[lesson.video_status];
              return (
                <Link className="panel card-link" to={lesson.slug} key={lesson.id}>
                  <span className="card-link__title">
                    {marker && <span title={marker.label}>{marker.icon} </span>}
                    {lesson.objective_code} · {lesson.title}
                  </span>
                  <span className="card-link__meta">{lesson.objective_title}</span>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
      {lessons?.length === 0 && <p>Todavía no hay lecciones.</p>}
    </main>
  );
}
