import { lazy, Suspense } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import remarkFaqHighlights, {
  type FaqHighlightEntry,
} from "../lib/remarkFaqHighlights";
import remarkVideoPlaceholder from "../lib/remarkVideoPlaceholder";
import Mermaid from "./Mermaid";
import type { VideoStatus } from "../api/types";

const VideoGenerationPanel = !__LEARNUP_HOSTED__
  ? lazy(() => import("./VideoGenerationPanel"))
  : null;

type VideoProps = {
  onGenerate: () => Promise<VideoStatus>;
  onPollStatus: () => Promise<VideoStatus>;
  onReady: () => void;
};

type Props = {
  children: string;
  faqHighlights?: FaqHighlightEntry[];
  video?: VideoProps;
};

export default function Markdown({ children, faqHighlights, video }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[
        remarkGfm,
        remarkVideoPlaceholder,
        [remarkFaqHighlights, faqHighlights ?? []],
      ]}
      components={{
        code({ className, children: codeChildren, ...props }) {
          if (className === "language-mermaid") {
            return <Mermaid chart={String(codeChildren).replace(/\n$/, "")} />;
          }
          return (
            <code className={className} {...props}>
              {codeChildren}
            </code>
          );
        },
        a({ href, children: linkChildren, ...props }) {
          if (href?.toLowerCase().endsWith(".mp4")) {
            return <video controls src={href} />;
          }
          if (href?.toLowerCase().endsWith(".pdf")) {
            return (
              <span>
                <iframe className="pdf-embed" src={href} title={String(linkChildren)} />
                <a href={href} target="_blank" rel="noreferrer">
                  {linkChildren}
                </a>
              </span>
            );
          }
          return (
            <a href={href} {...props}>
              {linkChildren}
            </a>
          );
        },
        div({ className, children: divChildren, ...props }) {
          if (
            className?.includes("video-placeholder") &&
            video &&
            VideoGenerationPanel
          ) {
            return (
              <Suspense fallback={null}>
                <VideoGenerationPanel {...video} />
              </Suspense>
            );
          }
          return (
            <div className={className} {...props}>
              {divChildren}
            </div>
          );
        },
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
