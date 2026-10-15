# AGENTS.md

Messy experimental repo. The only real, runnable app lives in `app/`; almost everything at the repo root is a one-off experiment or archived snapshot. Don't treat root-level files as core code.

## The app

- `app/server.py` — chat proxy: a stdlib `http.server` (`ThreadingHTTPServer`) with two endpoints:
  - `GET /` (or `/index.html`) serves `app/index.html` (Persian RTL chat UI).
  - `GET /health` returns `{ok, model}`.
  - `POST /api/chat` takes `{messages, model?}` and proxies to OpenRouter (`https://openrouter.ai/api/v1`) if `OPENROUTER_API_KEY` is set, otherwise the HuggingFace router (`https://router.huggingface.co/v1`) with `HF_TOKEN`. Falls back to a Llama-3.1-8B default model.
- `app/` is **untracked in git** — remember it exists even though `git status` won't show it as tracked.
- The frontend is hardcoded to `lang="fa" dir="rtl"`. Keep Persian RTL when editing UI.
- `app/server.py` imports `openai` and `python-dotenv`; there is no `requirements.txt`. Install them (e.g. `python3 -m pip install openai python-dotenv`) before running.

## Running

- Secrets load from `.env` (gitignored — never commit or print them). `load_dotenv()` runs at import.
- Start: `python3 app/server.py` (defaults to port 8000, override with `PORT`).
- Model override via `CHAT_MODEL` env var.

## Repo hygiene

- Root contains throwaway artifacts: zip archives (`workspace-*.zip`, skill zips), `build_command_center.py`, `hf_test.py`, `run_kimi.py`, `kimi_k3.py`, `mongo_test.py`, `setup_ml (1).sh`, a stray `docker-compose (1).yml`. `docker-compose (1).yml` references `./backend`/`./frontend` that **do not exist** — it is stale. The `setup_ml`/font scripts target `/home/user` paths from another environment and are not repo-specific.
- These are not wired into the app. Only touch them if the user asks.

## Config & tooling

- `opencode.json` wires the `opencode-browser` plugin and the `browsermcp` MCP server (`@browsermcp/mcp@0.1.3` via `npx`).
- `.opencode/skills/` holds skills: `langfuse`, `ui-ux-pro-max`, and several `21st.dev` skills. Load them via the skill tool when a task matches their description.
- No test suite, linter, formatter, or build step exists. Verify changes by running the server and exercising `/health` and `/api/chat`.
- `.devcontainer/` Dockerfile installs MongoDB CLI tools into a Node dev container; not required to run the app.
