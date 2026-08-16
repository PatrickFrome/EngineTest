import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const sourceUrl = "https://www.klostermann.de/Buecher/Seite-/-Kategorie/Editionsplan";
const navigationUrl = "https://www.beyng.com/hb/gesamt.html";
const output = path.join(root, "experiments", "heidegger-ga", "catalog_snapshot.json");

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function decodeHtml(value) {
  return value
    .replace(/<br\s*\/?\s*>/giu, " ")
    .replace(/<[^>]+>/gu, " ")
    .replace(/&nbsp;|&#160;/giu, " ")
    .replace(/&ndash;|&#8211;/giu, "–")
    .replace(/&mdash;|&#8212;/giu, "—")
    .replace(/&quot;|&#34;/giu, "\"")
    .replace(/&amp;|&#38;/giu, "&")
    .replace(/\s+/gu, " ")
    .trim();
}

function dateFromTitle(value) {
  const match = value.match(/\(\s*((?:19|20)\d{2})(?:\s*–\s*((?:19|20)\d{2}))?\s*\)\s*$/u);
  if (!match) return { title: value.trim(), date_label: null };
  return {
    title: value.slice(0, match.index).trim(),
    date_label: match[2] ? `${match[1]}–${match[2]}` : match[1],
  };
}

const response = await fetch(sourceUrl, { headers: { "user-agent": "Destruktion-Automation-Engine/0.3.0 research-catalog-snapshot" } });
if (!response.ok) throw new Error(`Klostermann Editionsplan returned ${response.status} ${response.statusText}.`);
const html = await response.text();
const category = html.match(/<div class="CategoryText"[\s\S]*?<\/div>/iu)?.[0];
if (!category) throw new Error("Could not locate the Editionsplan category block.");
const paragraphs = [...category.matchAll(/<p(?:\s[^>]*)?>([\s\S]*?)<\/p>/giu)]
  .map((match) => ({ html: match[1], text: decodeHtml(match[1]) }));

const divisions = [];
const volumes = [];
let division = null;
let subseries = null;
for (const paragraph of paragraphs) {
  const divisionMatch = paragraph.text.match(/^(I{1,3}|IV)\. Abteilung:\s*(.+)$/u);
  if (divisionMatch) {
    division = divisionMatch[1];
    subseries = null;
    divisions.push({ id: division, title: divisionMatch[2] });
    continue;
  }
  if (/^(?:Marburger Vorlesungen|Freiburger Vorlesungen|Frühe Freiburger Vorlesungen|Vorträge – Gedachtes)$/iu.test(paragraph.text)) {
    subseries = paragraph.text;
    continue;
  }
  const volumeMatch = paragraph.text.match(/^(\d+(?:\.\d+|\/\d+)?(?:\s*A)?)\s+(.+)$/u);
  if (!volumeMatch || !division) continue;
  const link = paragraph.html.match(/href="([^"]+)"[^>]*>[\s\S]*?<\/a>/iu)?.[1] ?? null;
  const parsed = dateFromTitle(volumeMatch[2]);
  volumes.push({
    volume_id: volumeMatch[1].replace(/\s+/gu, ""),
    division_id: division,
    subseries,
    title: parsed.title,
    date_label: parsed.date_label,
    official_url: link ? new URL(link, sourceUrl).href.replace(/^http:/u, "https:") : null,
    access_state: "BIBLIOGRAPHIC_METADATA_ONLY",
  });
}

const unique = new Set(volumes.map((item) => item.volume_id));
if (divisions.length !== 4) throw new Error(`Expected four GA divisions, parsed ${divisions.length}.`);
if (volumes.length !== 105 || unique.size !== volumes.length || volumes.at(-1)?.volume_id !== "105") {
  throw new Error(`Unexpected GA plan shape: entries=${volumes.length}, unique=${unique.size}, last=${volumes.at(-1)?.volume_id}.`);
}

const normalized = JSON.stringify({ divisions, volumes });
const snapshot = {
  snapshot_version: "DAE-HGA-CATALOG-1.0",
  retrieved_at: new Date().toISOString().replace(/\.\d{3}Z$/u, "Z"),
  sources: {
    bibliographic_authority: {
      id: "HGA-KLOSTERMANN-PLAN",
      url: sourceUrl,
      role: "OFFICIAL_PUBLISHER_EDITION_PLAN",
      raw_html_sha256: sha256(html),
    },
    navigation_index: {
      id: "HGA-BEYNG-CATALOG",
      url: navigationUrl,
      role: "SECONDARY_NAVIGATION_AND_ACCESS_INDEX",
    },
  },
  claim_ceiling: "BIBLIOGRAPHIC_CATALOG_ONLY_NOT_PRIMARY_TEXT_OR_PHILOSOPHICAL_EVIDENCE",
  entry_count: volumes.length,
  normalized_sha256: sha256(normalized),
  divisions,
  volumes,
};
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify(snapshot, null, 2)}\n`, "utf8");
console.log(`Heidegger GA snapshot: ${volumes.length} entries through GA ${volumes.at(-1).volume_id}; sha256=${snapshot.normalized_sha256}`);
