import type { FaqEntry } from "../api/types";
import Markdown from "./Markdown";

type Props = {
  entries: FaqEntry[];
  onDelete?: (index: number) => Promise<void>;
};

export default function FaqSection({ entries, onDelete }: Props) {
  if (entries.length === 0) {
    return (
      <section aria-labelledby="faq-title">
        <h2 id="faq-title">Preguntas y respuestas</h2>
        <p className="muted">Todavía no hiciste preguntas sobre este material.</p>
      </section>
    );
  }
  return (
    <section aria-labelledby="faq-title">
      <h2 id="faq-title">Preguntas y respuestas</h2>
      {entries.map((entry) => (
        <article className="faq-entry panel" id={`faq-${entry.index}`} key={entry.index}>
          <div className="row row--between">
            <h3>{entry.question}</h3>
            {onDelete && (
              <button
                type="button"
                className="btn btn--ghost btn--small"
                onClick={() => void onDelete(entry.index)}
              >
                Eliminar
              </button>
            )}
          </div>
          {entry.selected_text && (
            <blockquote>{entry.selected_text}</blockquote>
          )}
          <Markdown>{entry.answer_markdown}</Markdown>
        </article>
      ))}
    </section>
  );
}
