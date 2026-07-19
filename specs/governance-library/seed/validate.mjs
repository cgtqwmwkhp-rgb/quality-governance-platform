/**
 * Validates taxonomy.json before loading it into the database.
 * No dependencies — run with:  node seed/validate.mjs
 *
 * The loader itself is the builder's job (Cosmos DB or Azure SQL — see SPEC.md §1):
 * read taxonomy.json, upsert one record per category keyed on `id`, idempotent
 * (running twice yields the same 86 records — acceptance criterion #10).
 */

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const raw = await readFile(path.join(__dirname, "..", "taxonomy.json"), "utf8");
const { categories, version, reference_scheme } = JSON.parse(raw);

const errors = [];
const ACCESS = new Set(["all_staff", "managers", "restricted"]);

if (!Array.isArray(categories) || categories.length === 0) {
  errors.push("no categories found");
}

const ids = new Set();
for (const c of categories) {
  if (ids.has(c.id)) errors.push(`duplicate id: ${c.id}`);
  ids.add(c.id);
}

for (const c of categories) {
  const where = `category ${c.id}`;
  if (c.level === 1) {
    if (c.parent_id !== null) errors.push(`${where}: level-1 must have parent_id null`);
    if (!/^PEL-[A-Z]{3}$/.test(c.ref_prefix)) errors.push(`${where}: bad level-1 ref_prefix "${c.ref_prefix}"`);
  } else if (c.level === 2) {
    if (!c.parent_id || !ids.has(c.parent_id)) errors.push(`${where}: missing/unknown parent_id`);
    if (!ACCESS.has(c.default_access)) errors.push(`${where}: default_access "${c.default_access}" not in ${[...ACCESS]}`);
    if (!/^PEL-[A-Z]{3}-\d{2}$/.test(c.ref_prefix)) errors.push(`${where}: bad level-2 ref_prefix "${c.ref_prefix}"`);
    if (c.parent_id && !c.id.startsWith(c.parent_id + ".")) errors.push(`${where}: id does not sit under parent ${c.parent_id}`);
  } else {
    errors.push(`${where}: unexpected level ${c.level}`);
  }
  if (!c.name || !c.slug || !c.description) errors.push(`${where}: name/slug/description must be non-empty`);
}

const slugs = categories.map((c) => c.slug);
if (new Set(slugs).size !== slugs.length) errors.push("duplicate slugs present");

const l1 = categories.filter((c) => c.level === 1).length;
const l2 = categories.filter((c) => c.level === 2).length;

if (errors.length) {
  console.error(`FAILED — ${errors.length} problem(s):`);
  for (const e of errors) console.error("  - " + e);
  process.exit(1);
}

console.log(`OK — taxonomy.json v${version}: ${l1} sections + ${l2} subcategories = ${categories.length} categories.`);
console.log(`Reference scheme: ${reference_scheme.pattern} (e.g. ${reference_scheme.example.split(" =")[0]})`);
