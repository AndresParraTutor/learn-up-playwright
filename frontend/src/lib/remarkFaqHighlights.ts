export type FaqHighlightEntry = { index: number; text: string };

type MdastNode = {
  type: string;
  value?: string;
  url?: string;
  children?: MdastNode[];
  data?: {
    hProperties?: Record<string, unknown>;
  };
};

function linkNode(entry: FaqHighlightEntry, value: string): MdastNode {
  return {
    type: "link",
    url: `#faq-${entry.index}`,
    data: { hProperties: { className: ["faq-source-link"] } },
    children: [{ type: "text", value }],
  };
}

function longestPrefixAtEnd(value: string, quote: string): string | null {
  for (let length = quote.length - 1; length > 0; length -= 1) {
    const prefix = quote.slice(0, length);
    if (value.endsWith(prefix)) return prefix;
  }
  return null;
}

export default function remarkFaqHighlights(options: FaqHighlightEntry[] = []) {
  return (tree: MdastNode) => {
    const used = new Set<number>();

    function visit(node: MdastNode) {
      if (!node.children || node.type === "link" || node.type === "code") return;
      const next: MdastNode[] = [];
      for (const child of node.children) {
        if (child.type !== "text" || !child.value) {
          visit(child);
          next.push(child);
          continue;
        }
        let parts: MdastNode[] = [child];
        for (const entry of options) {
          if (used.has(entry.index) || !entry.text) continue;
          const candidate = parts.find(
            (part) => part.type === "text" && part.value !== undefined,
          );
          if (!candidate?.value) continue;
          let matched = entry.text;
          let start = candidate.value.indexOf(matched);
          if (start < 0) {
            const partial = longestPrefixAtEnd(candidate.value, entry.text);
            if (!partial) continue;
            matched = partial;
            start = candidate.value.length - partial.length;
          }
          const before = candidate.value.slice(0, start);
          const after = candidate.value.slice(start + matched.length);
          const replacement: MdastNode[] = [];
          if (before) replacement.push({ type: "text", value: before });
          replacement.push(linkNode(entry, matched));
          if (after) replacement.push({ type: "text", value: after });
          parts = parts.flatMap((part) =>
            part === candidate ? replacement : [part],
          );
          used.add(entry.index);
        }
        next.push(...parts);
      }
      node.children = next;
    }

    visit(tree);
  };
}
