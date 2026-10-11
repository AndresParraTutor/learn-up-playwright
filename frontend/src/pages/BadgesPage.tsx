import { useEffect, useState } from "react";
import type { Badge } from "../api/types";
import TitleBlock from "../components/TitleBlock";
import { useTopicContext } from "../contexts/TopicContext";

export default function BadgesPage() {
  const { topic, api } = useTopicContext();
  const [badges, setBadges] = useState<Badge[] | null>(null);
  useEffect(() => {
    api.listBadges().then(setBadges);
  }, [api]);
  const earned = badges?.filter((badge) => badge.earned_at !== null) ?? [];
  const locked = badges?.filter((badge) => badge.earned_at === null) ?? [];
  return (
    <main className="shell">
      <TitleBlock title="Insignias" backTo={`/t/${topic.slug}`} backLabel="Panel" />
      {!badges && <p>Cargando…</p>}
      <h2>Obtenidas</h2>
      <div className="card-list">
        {earned.map((badge) => (
          <article className="panel panel--highlight" key={badge.code}>
            <h3>{badge.icon} {badge.name}</h3><p>{badge.description}</p>
          </article>
        ))}
      </div>
      <h2>Por obtener</h2>
      <div className="card-list">
        {locked.map((badge) => (
          <article className="panel" key={badge.code}>
            <h3>{badge.icon} {badge.name}</h3><p>{badge.description}</p>
          </article>
        ))}
      </div>
    </main>
  );
}
