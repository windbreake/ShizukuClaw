import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["**/*.test.ts"],
    exclude: ["node_modules", "dist", ".venv", "__pycache__"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["harness/**/*.ts"],
      exclude: ["harness/**/*.test.ts", "**/*.d.ts"],
    },
    testTimeout: 30000,
    hookTimeout: 10000,
  },
});
