// eslint-config-next 16 ships flat config directly.
//
// The generated version of this file went through `FlatCompat`, a shim that
// translates old-style `.eslintrc` configs. On Next 16 that path throws
// ("property 'react' closes the circle") because the config it is translating
// is already flat. Importing the exports is both correct and one dependency
// lighter — `@eslint/eslintrc` is no longer needed.
import next from "eslint-config-next";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default [
  ...next,
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    ignores: [".next/**", "node_modules/**", "out/**"],
  },
];
