import { useRef } from "react";

import type { AskOutcome, FaqEntry, QuotaStatus, VideoStatus } from "../api/types";
import FaqSection from "./FaqSection";
import Markdown from "./Markdown";
import SelectionAsk from "./SelectionAsk";

type Props = {
  bodyMarkdown: string;
  whyItMattersMarkdown: string;
  faq: FaqEntry[];
  onAsk: (
    selectedText: string,
    question: string,
    onDelta: (text: string) => void,
    useFullSources: boolean,
    idempotencyKey?: string,
  ) => Promise<AskOutcome>;
  onAnswered: (entry: FaqEntry) => void;
  onDeleteFaq: (index: number) => Promise<void>;
  getQuotaStatus?: () => Promise<QuotaStatus>;
  video?: {
    onGenerate: () => Promise<VideoStatus>;
    onPollStatus: () => Promise<VideoStatus>;
    onReady: () => void;
  };
};

export default function TeachingArticle({
  bodyMarkdown,
  whyItMattersMarkdown,
  faq,
  onAsk,
  onAnswered,
  onDeleteFaq,
  getQuotaStatus,
  video,
}: Props) {
  const articleRef = useRef<HTMLElement>(null);
  const faqHighlights = faq
    .filter((entry): entry is FaqEntry & { selected_text: string } =>
      Boolean(entry.selected_text),
    )
    .map((entry) => ({ index: entry.index, text: entry.selected_text }));
  return (
    <>
      <article ref={articleRef} className="teaching-article">
        <Markdown faqHighlights={faqHighlights} video={video}>
          {bodyMarkdown}
        </Markdown>
        <section className="panel panel--highlight">
          <h2>Por qué importa</h2>
          <Markdown faqHighlights={faqHighlights}>{whyItMattersMarkdown}</Markdown>
        </section>
        <FaqSection entries={faq} onDelete={onDeleteFaq} />
        <p className="disclaimer">
          Este texto fue generado automáticamente por un modelo de lenguaje y
          puede contener errores. Leelo con criterio y verificá por otra vía
          cualquier tema sensible.
        </p>
      </article>
      <SelectionAsk
        containerRef={articleRef}
        onAsk={onAsk}
        onAnswered={onAnswered}
        getQuotaStatus={getQuotaStatus}
      />
    </>
  );
}
