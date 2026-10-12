import { randomInt } from "node:crypto";
import { z } from "zod";
import { names } from "./wordlist";

export const StoreName = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/, "Use 1-100 letters, digits, '.', '_' or '-', starting with a letter or digit");
const gen = names((n) => randomInt(n));
/** Readable random names: stores "amber-heron-27", workspaces "Amber Heron". */
export const randomStoreName = gen.store;
export const randomWorkspaceName = gen.workspace;
