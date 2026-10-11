import { lazy, Suspense, useEffect, useState } from "react";

import type { About } from "../api/types";
import Markdown from "../components/Markdown";
import TitleBlock from "../components/TitleBlock";
import { IS_HOSTED } from "../config/runtime";
import { useTopicContext } from "../contexts/TopicContext";

const TopicTransferPanel = !__LEARNUP_HOSTED__
  ? lazy(() =>
      import("../components/TopicTransferPanel").then((module) => ({
        default: module.TopicTransferPanel,
      })),
    )
  : null;

export default function AboutPage() {
  const { topic, api } = useTopicContext();
  const [about, setAbout] = useState<About | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.getAbout().then(setAbout).catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason)),
    );
  }, [api]);
  return (
    <main className="shell shell--wide">
      <TitleBlock title="Acerca de" backTo={`/t/${topic.slug}`} backLabel="Panel" />
      {error && <p className="banner banner--error">{error}</p>}
      {!about && !error && <p>Cargando…</p>}
      {about && (
        <>
          <p className="chip">Versión de la aplicación {about.app_version}</p>
          <section className="panel"><Markdown>{about.app_markdown}</Markdown></section>
          <section><h2>Fuentes</h2><Markdown>{about.sources_markdown}</Markdown></section>
          {!IS_HOSTED && (
            <>
              <blockquote>
                Importá temas de learn-up únicamente de personas y fuentes en las que
                confiás. La validación reduce riesgos comunes de archivos, pero no puede
                volver seguro un archivo no confiable.
              </blockquote>
              {TopicTransferPanel && (
                <Suspense fallback={null}>
                  <TopicTransferPanel topicSlug={topic.slug} />
                </Suspense>
              )}
            </>
          )}
        </>
      )}
    </main>
  );
}
