import { FlatCompat } from "@eslint/eslintrc";
import { defineConfig, globalIgnores } from "eslint/config";
import prettier from "eslint-config-prettier/flat";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const baseDirectory = dirname(fileURLToPath(import.meta.url));
const compat = new FlatCompat({ baseDirectory });

export default defineConfig([
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  prettier,
  globalIgnores([".next/**", "node_modules/**", "coverage/**", "next-env.d.ts"]),
]);
