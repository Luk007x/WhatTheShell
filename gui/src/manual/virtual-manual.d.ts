// SPDX-License-Identifier: AGPL-3.0-or-later
declare module "virtual:manual" {
  export const manual: Record<"de" | "en", import("./manualData").ManualChapter[]>;
}
