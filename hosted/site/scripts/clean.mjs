import { rm } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const target = resolve(siteRoot, "dist");

if (basename(target) !== "dist" || dirname(target) !== siteRoot) {
  throw new Error(`Unsafe build directory: ${target}`);
}

await rm(target, { recursive: true, force: true });
