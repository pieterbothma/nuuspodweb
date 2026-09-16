import { defineConfig } from "vitest/config";
import path from "path";

const alias = { "@": path.resolve(__dirname, ".") };

/**
 * Two projects, because the suites need different globals:
 *  - `node` covers the pure-logic tests in `lib/` and the route handlers in `app/api/`,
 *    which must run without a DOM so a stray `window` reference fails loudly.
 *  - `komponente` covers `.test.tsx` only, in jsdom, for React Testing Library.
 * The JSX is compiled by Vite's own transform (tsconfig already says `react-jsx`), so no
 * React Vite plugin is needed — the tests don't use fast refresh.
 */
export default defineConfig({
  resolve: { alias },
  test: {
    projects: [
      {
        resolve: { alias },
        test: {
          name: "node",
          environment: "node",
          include: ["lib/**/*.test.ts", "app/**/*.test.ts"],
        },
      },
      {
        resolve: { alias },
        test: {
          name: "komponente",
          environment: "jsdom",
          include: ["app/**/*.test.tsx", "lib/**/*.test.tsx"],
        },
      },
    ],
  },
});
