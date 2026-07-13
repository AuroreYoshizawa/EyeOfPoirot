#!/usr/bin/env node
/**
 * Export values from selected sheets in a working XLSX to UTF-8 CSV.
 *
 * This is a one-way audit/import helper. The workbooks themselves are private
 * working artefacts; only reviewed, derived CSVs are committed. Reading uses
 * @oai/artifact-tool so formulas are exported as their calculated values.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [inputPath, outputDir, ...requestedSheets] = process.argv.slice(2);
if (!inputPath || !outputDir) {
  throw new Error(
    "usage: export_workbook_sheets.mjs INPUT.xlsx OUTPUT_DIR [SHEET ...]",
  );
}

function csvCell(value) {
  if (value === null || value === undefined) return "";
  const text = value instanceof Date ? value.toISOString() : String(value);
  return /[\",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function safeFileName(name) {
  return name
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, "-")
    .replaceAll(/^-|-$/g, "");
}

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheetSummary = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 20000,
});
const sheets = sheetSummary.ndjson
  .trim()
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line));
const names = requestedSheets.length
  ? requestedSheets
  : sheets.map((sheet) => sheet.name);

await fs.mkdir(outputDir, { recursive: true });
const inventory = [];
for (const name of names) {
  const sheet = workbook.worksheets.getItem(name);
  const used = sheet.getUsedRange(true);
  const values = used?.values ?? [];
  const csv = values.map((row) => row.map(csvCell).join(",")).join("\n") + "\n";
  const outputPath = path.join(outputDir, `${safeFileName(name)}.csv`);
  await fs.writeFile(outputPath, csv, "utf8");
  inventory.push({ sheet: name, rows: values.length, cols: values[0]?.length ?? 0, outputPath });
}

await fs.writeFile(
  path.join(outputDir, "inventory.json"),
  JSON.stringify(inventory, null, 2) + "\n",
  "utf8",
);
console.log(JSON.stringify(inventory, null, 2));
