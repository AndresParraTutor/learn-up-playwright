import { useState } from "react";

import {
  downloadTopic,
  importTopicArchive,
  type TopicImportReport,
  validateTopicArchive,
} from "../api/topicTransfer";

const TRUST_WARNING =
  "Importá temas de learn-up únicamente de personas y fuentes en las que confíes. La validación reduce riesgos comunes del archivo, pero no vuelve seguro un archivo no confiable.";

type Props = {
  topicSlug?: string;
  onImported?: (topicSlug: string) => void | Promise<void>;
};

export function TopicTransferPanel({ topicSlug, onImported }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<TopicImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="panel topic-transfer"
      aria-labelledby="topic-transfer-title"
    >
      <h2 id="topic-transfer-title">Compartir un tema</h2>
      <p className="disclaimer">{TRUST_WARNING}</p>
      {topicSlug && (
        <button
          disabled={busy}
          onClick={() => void run(() => downloadTopic(topicSlug))}
        >
          Exportar este tema
        </button>
      )}
      <label className="field__label" htmlFor="topic-archive">
        Archivo del tema
      </label>
      <input
        id="topic-archive"
        type="file"
        accept=".zip,.learnup.zip,application/zip"
        disabled={busy}
        onChange={(event) => {
          setFile(event.target.files?.[0] ?? null);
          setReport(null);
          setError(null);
        }}
      />
      <button
        disabled={busy || file === null}
        onClick={() =>
          void run(async () => {
            if (file === null) return;
            setReport(await validateTopicArchive(file));
          })
        }
      >
        Validar archivo
      </button>
      {report && (
        <div role="status" className="topic-transfer__report">
          <p>
            <strong>{report.topic_slug}</strong> es{" "}
            {report.mode === "update" ? "una actualización" : "una importación nueva"}{" "}
            proveniente de la versión {report.source_app_version}. El formato de
            archivo {report.archive_format} es compatible con esta app (
            {report.destination_app_version}).
          </p>
          <p>
            Preguntas y respuestas para combinar: {report.merged_q_and_a}.
            Archivos ignorados: {report.ignored.length}. Preguntas y respuestas
            omitidas:{" "}
            {report.skipped_q_and_a.length}.
          </p>
          {report.status === "validated" && (
            <button
              disabled={busy || file === null}
              onClick={() =>
                void run(async () => {
                  if (file === null) return;
                  const installed = await importTopicArchive(file);
                  setReport(installed);
                  await onImported?.(installed.topic_slug);
                })
              }
            >
              Confirmar{" "}
              {report.mode === "update" ? "actualización" : "importación"}
            </button>
          )}
          {report.backup && <p>Copia de seguridad: {report.backup}</p>}
        </div>
      )}
      {error && <p className="error-banner">{error}</p>}
    </section>
  );
}
