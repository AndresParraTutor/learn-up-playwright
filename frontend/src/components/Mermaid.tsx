import { useEffect, useId, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });

export default function Mermaid({ chart }: { chart: string }) {
  const reactId = useId().replace(/:/g, "");
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    mermaid
      .render(`mermaid-${reactId}`, chart)
      .then((result) => {
        if (active) setSvg(result.svg);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      active = false;
    };
  }, [chart, reactId]);

  if (error) return <p className="banner banner--error">Diagrama inválido: {error}</p>;
  return <div className="mermaid" dangerouslySetInnerHTML={{ __html: svg }} />;
}
