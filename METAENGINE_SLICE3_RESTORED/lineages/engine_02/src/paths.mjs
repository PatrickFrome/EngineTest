import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const PROJECT_ROOT = path.resolve(fileURLToPath(new URL("..", import.meta.url)));

export function projectPath(...parts) {
  return path.join(PROJECT_ROOT, ...parts);
}

export async function readJson(filePath) {
  const text = await readFile(filePath, "utf8");
  try {
    return JSON.parse(text);
  } catch (error) {
    error.message = `${filePath}: ${error.message}`;
    throw error;
  }
}
