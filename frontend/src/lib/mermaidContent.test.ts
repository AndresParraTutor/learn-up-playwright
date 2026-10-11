import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import mermaid from "mermaid";
import { describe, expect, it } from "vitest";

type Block = { file: string; index: number; code: string };

function markdownFiles(root: string): string[] {
  return readdirSync(root).flatMap((name) => {
    const path = resolve(root, name);
    if (statSync(path).isDirectory()) return markdownFiles(path);
    return path.endsWith(".md") ? [path] : [];
  });
}

const contentRoot = resolve(process.cwd(), "..", "content");
const blocks: Block[] = markdownFiles(contentRoot).flatMap((file) => {
  const text = readFileSync(file, "utf8");
  return [...text.matchAll(/```mermaid\s*\n([\s\S]*?)```/g)].map(
    (match, index) => ({ file, index, code: match[1] }),
  );
});

describe("diagramas Mermaid del contenido", () => {
  it.each(blocks)("$file · diagrama $index", async ({ code }) => {
    await expect(
      mermaid.parse(code, { suppressErrors: true }),
    ).resolves.not.toBe(false);
  });
});
