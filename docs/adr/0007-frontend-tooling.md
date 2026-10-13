# ADR 0007: Use npm, ESLint and Prettier for the frontend, with a 14-day minimum release age

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

[ADR 0004](0004-monorepo-with-uv.md) left the frontend's tooling to be chosen
when the frontend was created. The plan already fixes the main pieces: React,
TypeScript in strict mode, Vite, and Vitest with React Testing Library. Still
open were the Node.js version, the package manager, the lint and format tools,
the TypeScript version, and how to protect the project from malicious package
releases.

The forces are the same as for the backend: the same checks on the author's
Windows machine and in CI, the same strictness as mypy `--strict`, and
widely used tools that a reader of the repository already knows.

There is also a risk that the backend does not have to the same degree: a
frontend project installs hundreds of packages from npm, most of them
indirect. In 2025, attackers published malicious versions of popular npm
packages (such as `chalk` and `debug`) from stolen maintainer accounts. Those
versions were found and removed within hours, but anyone who installed in that
window got them.

## Decision

- **Node.js 24**, the current LTS version, written in `frontend/.nvmrc` (which
  CI reads) and in `engines` in `package.json`.
- **npm**, which comes with Node.js, as the package manager.
  `package-lock.json` is committed, and CI installs with `npm ci`, which
  fails if the lockfile is out of date with `package.json`.
- **A minimum release age of 14 days** (`min-release-age=14` in
  `frontend/.npmrc`): npm only installs versions published at least 14 days
  earlier. It needs npm 11.10.0 or later, so `engines` requires that version
  and `engine-strict=true` makes npm refuse to run with an older one. When a
  security fix is younger than that, it is installed on purpose, for that one
  command, with `--min-release-age=0`. This was needed when the frontend was
  created: `npm audit` reported a high-severity issue in `source-map-js`
  1.2.1, used by the build tools, and the fix was 13 days old.
- **No install scripts** (`ignore-scripts=true` in `frontend/.npmrc`): npm
  never runs the scripts that packages ask to run when they are installed,
  which is how malicious releases usually run their code. None of the
  packages the project uses needs one. The project's own scripts
  (`npm run lint`, `npm test`, ...) still run.
- **Vite's `react-ts` template** as the starting point, with TypeScript in
  strict mode plus `noUncheckedIndexedAccess`.
- **ESLint** with typescript-eslint's `strictTypeChecked` rules (the strictest
  set, including the rules that use the types), the React Hooks rules and the
  React Refresh rule. **Prettier** formats the code with its default options,
  and `eslint-config-prettier` turns off the ESLint rules that would fight it.
- **TypeScript 6.0**, the version of the template.
- A **`Frontend` CI job** next to `Backend`, with the same step names: install
  dependencies, lint, check formatting, type-check, test, plus a build.

## Alternatives considered

- **oxlint**, which Vite's template now uses instead of ESLint. It is written
  in Rust and much faster, and since July 2026 its type-aware rules are
  stable (59 of typescript-eslint's 61), on top of TypeScript 7. It was not
  chosen because ESLint with typescript-eslint is still what most projects
  use, and it comes with a ready-made strict rule set (`strictTypeChecked`),
  where oxlint's would have to be put together from its rule categories.
  Each release of oxlint's type-aware engine is also tied to one exact
  TypeScript version.
- **TypeScript 7**, the compiler rewritten in Go, which is several times
  faster. typescript-eslint does not support it yet (it requires a TypeScript
  version below 6.1).
- **pnpm or Yarn.** pnpm is faster and stricter about packages a project uses
  without declaring them, but it is one more tool to install. For a single
  app, npm is enough.
- **No minimum release age.** Simpler, but every install could pick a version
  published minutes earlier, which is exactly the window that the attacks
  above used.
- **npm's newer approval list for install scripts** (`allowScripts` in
  `package.json`, with `strict-allow-scripts`) instead of turning them all
  off. It allows the scripts of chosen packages, but no package here needs
  one, so turning them all off is simpler.

## Consequences

- Everyone gets the same package versions, and a Node.js or npm version that
  is too old fails at install time with a clear message.
- ESLint and Prettier are two tools to configure instead of one, and the
  type-aware rules make linting slower (a few seconds for now).
- Moving to TypeScript 7 waits until typescript-eslint supports it.
- A new package, or an update, arrives at least 14 days after its release. A
  fresh security fix needs a deliberate `--min-release-age=0`, so it has to be
  noticed first (`npm audit`).
- A package that needs its install script to work will not work until its
  script is allowed on purpose.
