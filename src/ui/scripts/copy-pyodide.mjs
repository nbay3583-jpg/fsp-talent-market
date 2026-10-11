// Copies the locally packaged Pyodide runtime next to the sandbox page (no CDN at run time).
import { copyFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const from = join(root, "node_modules", "pyodide");
const to = join(root, "public", "sandbox", "pyodide");
mkdirSync(to, { recursive: true });
for (const f of ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]) {
  if (!existsSync(join(from, f))) throw new Error(`pyodide file missing: ${f}`);
  copyFileSync(join(from, f), join(to, f));
}
console.log("pyodide runtime copied to public/sandbox/pyodide");
