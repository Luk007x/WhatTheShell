// SPDX-License-Identifier: AGPL-3.0-or-later
export const FILE_ID_PATTERN = /^[a-z0-9][a-z0-9_-]*$/;

/** Derive a file id from a workflow name (umlauts transliterated, rest reduced to [a-z0-9_-]). */
export function slugify(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^[-_]+|[-_]+$/g, "");
  return slug || "workflow";
}
