import js from "@eslint/js";
import pluginQuery from "@tanstack/eslint-plugin-query";
import prettier from "eslint-config-prettier/flat";
import tailwind from "eslint-plugin-better-tailwindcss";
import { getDefaultSelectors } from "eslint-plugin-better-tailwindcss/defaults";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig, globalIgnores } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig(
  globalIgnores(["dist"]),
  {
    files: ["**/*.{js,ts,tsx}"],
    extends: [
      js.configs.recommended,
      // The strictest of typescript-eslint's recommended sets, including the
      // rules that use the types.
      tseslint.configs.strictTypeChecked,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      // TanStack Query's mistakes, such as a query key that is missing
      // something its request uses.
      pluginQuery.configs["flat/recommended-strict"],
      // Tailwind's mistakes, such as a class that doesn't exist (a typo in
      // "border-wod-600" draws nothing, and nothing else would say so).
      tailwind.configs.correctness,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    settings: {
      "better-tailwindcss": {
        // Where the classes of index.css (@theme, @utility) are.
        entryPoint: "src/index.css",
        // Where classes are: className, and also these constants and props.
        selectors: [
          ...getDefaultSelectors(),
          {
            kind: "variable",
            // Every constant that holds classes: add a new one here.
            name: "^(BUTTON|ALERT|PANEL|FIELD|HELD|SHOWN)$",
            match: [{ type: "strings" }],
          },
          {
            kind: "variable",
            name: "^(WEATHER|PLACEHOLDER)_LOOKS$",
            match: [{ type: "objectValues" }],
          },
          { kind: "attribute", name: "^bubble$", match: [{ type: "strings" }] },
        ],
      },
    },
  },
  // Last: turn off the rules that Prettier's formatting would break.
  prettier,
);
