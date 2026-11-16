# GitHub publication and Vercel deployment preparation

**Publication approved for `rrayyann7811/OpsGuard-AI`; Vercel deployment is not authorized by this release.** The isolation procedure below documents safe repository preparation; Vercel steps remain future owner actions. No paid services or AI inference are required for the public demonstration.

## 1. Review the source before publication

Read [PUBLICATION_READINESS.md](PUBLICATION_READINESS.md). The current workspace inherits a home-directory Git repository and has no project-tracked baseline. **Do not run `git add .`, commit or push from that parent repository.** Do not reset it or move/delete its metadata.

Create a fresh, isolated project folder outside the inherited repository, or use an explicitly isolated project repository after owner approval. Copy only reviewed source, lockfiles, configuration examples and intended documentation into that folder. Preserve this working project and its databases. Verify `git rev-parse --show-toplevel` resolves exactly to the new project folder before any staging.

Include README, .gitignore, frontend source/config/lockfile, backend source/requirements/tests, service source/lockfile/tests, scripts and the attributed synthetic knowledge dataset. Review optional agent/evaluation material separately. Exclude virtual environments, node_modules, build output, real environment files, databases/sidecars, model assets/caches, runtime Qdrant, generated demo environments, raw verification logs and private source/evidence exports. The new .gitignore implements these defaults but is not a secret scanner and does not untrack files already committed elsewhere.

Internal progress and older operating guides contain local absolute paths and references to ignored verification artifacts. Review/redact or omit them from the public copy; do not rewrite/delete the originals. Public README/this guide use repository-relative commands. If selecting individual historical verification summaries for publication, inspect them first and remove machine paths/private evidence; do not force-add an entire ignored directory.

The owner approved the MIT license, included as ../LICENSE, with copyright 2026 Syed Rayyan Ali. Review all copied documents and fixtures even when automated scans find no credential signatures.

## Safe independent review-copy commands — run only after approval

The safest recommendation is a new reviewed copy with its own `.git`, leaving the current project and parent repository untouched. The commands below are instructions for the owner, **not executed by this phase**. They first create a temporary review copy; no deletion or history rewrite is involved. The paths `review_dir` and `source_dir` are shell variables, not placeholders to paste literally elsewhere.

```sh
source_dir="$PWD"
test -f "$source_dir/frontend/package.json" && test -f "$source_dir/backend/app/main.py" || exit 1
review_dir="$(mktemp -d /path/to/private-runtime)"
rsync -a --include='.env.example' \
  --exclude='.git/' --exclude='node_modules/' --exclude='.venv*/' --exclude='venv/' --exclude='env/' \
  --exclude='.env*' --exclude='.envrc' --exclude='.demo/' --exclude='.next/' --exclude='out/' \
  --exclude='.vercel/' --exclude='dist/' --exclude='build/' --exclude='coverage/' \
  --exclude='__pycache__/' --exclude='.pytest_cache/' --exclude='.mypy_cache/' --exclude='.ruff_cache/' \
  --exclude='.qdrant/' --exclude='.model-cache/' --exclude='.cache/' --exclude='.huggingface/' --exclude='.ollama/' \
  --exclude='*.db*' --exclude='*.sqlite*' --exclude='*.gguf' --exclude='*.onnx' --exclude='*.safetensors' \
  --exclude='*.pt' --exclude='*.pth' --exclude='*.bin' --exclude='*.pem' --exclude='*.key' \
  --exclude='*.log' --exclude='*.jsonl' --exclude='*.pyc' --exclude='*.tsbuildinfo' --exclude='.DS_Store' \
  --exclude='.idea/' --exclude='.vscode/' --exclude='/docs/verification/' --exclude='/evaluation/' \
  "$source_dir/" "$review_dir/"
printf 'Review copy: %s\n' "$review_dir"
```

Run this from the original project root. Inspect/redact the copied documents and deliberate security-test fixtures before publication. This copy command is a conservative filter, **not a guarantee of secret removal**. Keep generated environment files and original evidence only in their existing private location. The temporary directory can be reclaimed by the OS; preserve the reviewed copy in a durable owner-selected location before relying on it.

Only after **separate approval to initialize a repository**, while the variable still names the reviewed copy:

```sh
test -n "$review_dir" && test -d "$review_dir/frontend" && test ! -e "$review_dir/.git" || exit 1
git init -b main "$review_dir"
test "$(git -C "$review_dir" rev-parse --show-toplevel)" = "$review_dir" || exit 1
git -C "$review_dir" status --short
```

Then, only with **separate publication/commit/push approval**, manually select reviewed paths and inspect them before committing. Substitute the actual repository URL below; no account or remote was created:

```sh
cd "$review_dir"
git add .gitignore README.md frontend backend services scripts knowledge docs agent
# Inspect every staged path/content; do not proceed on an unexpected private artifact.
git diff --cached --name-only
git diff --cached --stat
git diff --cached --check
git diff --cached
# Stop here for final owner review. After approval:
git commit -m "Prepare OpsGuard AI local application and public demonstration"
git remote add origin YOUR_ACTUAL_GITHUB_REPOSITORY_URL
git push -u origin main
```

The named directories must exist in the reviewed copy; omit any optional directory deliberately excluded during review. Do not run these commands in the original home-root Git context. No initialization, staging, commit, remote modification or push was performed here.

## 2. Create and publish the GitHub repository — later owner action

1. After approval, create an empty repository named `OpsGuard-AI` in the owner's GitHub account. Choose public only after the content review. Do not initialize conflicting README/license files remotely if the local reviewed copy already supplies them.
2. In the **new isolated source folder**, initialize Git if necessary, then verify the top-level path again. Add only reviewed paths explicitly. Avoid broad staging from this original workspace.
3. Review the staging diff, filenames and file sizes. Confirm no `.env`, environment.sh, database, Qdrant storage, token, private evidence, model or dependency directory is included.
4. Only with publication authorization, commit the reviewed source, add the exact owner-created remote, and push the chosen branch. No remote URL or account was assumed by this preparation.
5. Inspect the GitHub file listing and rendered README. Check diagram rendering, links and source attribution. Enable available repository secret scanning/push protection and investigate any alert without sharing its value.

Use the actual remote URL GitHub displays, only in the verified isolated folder. The command sequence above intentionally stops for staged-content review before the separately authorized commit/push. Existing history was not changed.

## 3. Vercel frontend compatibility

The current frontend is a regular Next.js app with App Router and generated routes. It needs no replacement framework, separate frontend or new dependency. Vercel supports Next.js natively; a monorepo project can select the application directory. See [Next.js on Vercel](https://vercel.com/docs/frameworks/full-stack/nextjs) and [monorepo setup](https://vercel.com/docs/monorepos).

The reviewed `frontend/vercel.json` selects Next.js, `npm ci` and `npm run build:demo`. Do not set an arbitrary output directory or add static-export/SPA rewrite rules; use Next.js defaults. The existing webpack path is retained.

## 4. Import into Vercel — later owner action

After separate deployment authorization:

1. Connect only the approved GitHub repository to the owner's Vercel account.
2. Import a new project; select **Root Directory: `frontend`** and **Framework: Next.js**.
3. Install command: **`npm ci`**. Build command: **`npm run build:demo`**. Output directory: **Next.js default**. These commands are also specified in frontend/vercel.json.
4. Choose a currently supported Node.js version satisfying package.json (`>=22.18.0`); select 22.x or a later supported compatible major and confirm the actual build log. No Node version was provisioned here.
5. Use the same demo build for Preview and Production. No API URL or credential is required. The build command explicitly sets `NEXT_PUBLIC_DEMO_MODE=true` regardless of a stale API origin. Do not override it with a generic `npm run build` for the public showcase.
6. Review the build preview, then execute the actual deployment only when authorized. Verify the visible synthetic-data banner, every route, details/filters, empty investigations and disabled inference/search. Network inspection must show no calls to localhost, FastAPI, Ollama or an AI provider.
7. Record the actual deployed URL only after a successful deployment. No URL or deployment success is claimed here.

Importing a Git repository can trigger a deployment; it is an external publishing action, not part of the completed local preparation.

## 5. Environment variables and mode separation

| Setting | Local full-stack mode | Public demonstration |
| --- | --- | --- |
| `NEXT_PUBLIC_DEMO_MODE` | `false` or unset | Set to `true` by build:demo |
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` by default | Not required; never called |
| Backend `DATABASE_URL` | Private local SQLite configuration | Not supplied |
| `INCIDENT_WEBHOOK_TOKEN` | Matching backend/services server-only secret | Never supplied |
| `AGENT_AUTH_TOKEN`, other agent credentials | Private backend only; execution disabled until separately authorized | Never supplied |
| Qdrant/model configuration | Backend only | Not supplied |

`NEXT_PUBLIC_*` values become browser-visible build configuration. Never add webhook/action tokens, provider keys, database connection secrets or credentials to them. Changing public values requires a rebuild. See [Vercel environment variables](https://vercel.com/docs/environment-variables).

Local mode retains real FastAPI monitoring, SQLite persistence, historical retrieval when configured and optional guarded local Ollama. Public demo mode uses bundled authored synthetic records through the existing components. No API request is made; health stays Unknown, there is no database connection, semantic search is disabled and no investigation can be started. No generated report is presented as a real diagnosis. Preferences save only in the visitor's browser. Legacy Phase 1 fixture metrics are not used as production statistics.

The public build is a presentation, not a fallback after a live API failure. Local mode continues to report real connection failures and never substitutes demo records. To return to a local full-stack production build:

```sh
cd frontend
NEXT_PUBLIC_DEMO_MODE=false NEXT_TELEMETRY_DISABLED=1 npm run build -- --webpack
npm start
```

Do not run both builds or dev servers concurrently. Check memory pressure first on the 8 GB Mac.

## 6. Why a public localhost URL does not work

Browser requests execute on the visitor's computer. `127.0.0.1` and `localhost` refer to that computer, not the owner's Mac or the Vercel deployment. Vercel does not make a private loopback FastAPI server reachable publicly. HTTPS pages also require an appropriately secured reachable API; do not expose the Mac, disable security controls or embed server credentials to make a showcase work.

There is no reverse proxy or tunnel in this preparation. The public demo works while the owner's Mac is off because its synthetic examples are bundled into the frontend.

## 7. Future hosted FastAPI and full-stack requirements

A real hosted deployment needs a separately designed, authorized backend environment:

- Persistent storage with tested backup/restore for SQLite and embedded Qdrant, or a deliberate database/vector-service migration. SQLite's single-host write characteristics and embedded Qdrant's ownership/locking must be respected.
- A long-running application/worker supervisor for health polling and investigation lifecycle, graceful shutdown, restart recovery and the supported single-worker topology. Durable queue/lease coordination is needed before multiple API workers/replicas.
- A reachable HTTPS API, restricted CORS for the exact frontend origins and authenticated/authorized access to sensitive read/write routes. Current development actions intentionally require loopback clients; simply changing CORS does not make them safe for public multi-user use. Do not remove these controls to deploy.
- Private service connectivity, authenticated ingestion, development-only fault injection, secret management, request limits, monitoring and log redaction.
- Measured RAM/CPU/disk budgets for API, embeddings and any later local inference. Real Ollama compatibility/peak resources remain unverified; the historical ~3.32 GiB cold-load admission estimate is a local safety guard, not a measured cloud sizing recommendation.
- Explicit inference authorization and the unchanged memory/provenance guards. No model download, cloud AI, paid API or autonomous fix is enabled by frontend deployment.

Although Vercel supports Python/FastAPI functions, ordinary function filesystems are read-only except temporary scratch storage. That is not a durable home for this application's existing SQLite/Qdrant storage or evidence retention. A frontend deployment therefore does **not** establish full-stack compatibility. See [Vercel runtime filesystem documentation](https://vercel.com/docs/functions/runtimes#file-system-support). No serverless conversion was implemented.

## 8. Free and paid hosting assessment

The backend-free public showcase is a plausible low-traffic use of Vercel's free Hobby quota, subject to account eligibility, current plan terms and actual usage. The official [Hobby plan](https://vercel.com/docs/plans/hobby) is free with usage limits; [Pro](https://vercel.com/docs/plans/pro) offers paid capacity/features. Check current allowances and billing settings before deployment; a free tier is not an unlimited hosting promise. No account eligibility or billing setup was tested.

Full-stack hosting may require paid persistent volumes, always-on compute, backups and enough RAM for embeddings/optional Ollama. Sleeping/ephemeral free services cannot be assumed to preserve local databases or support continuous polling. No provider SKU, budget or free full-stack claim is approved: measure the complete workload, verify persistence/restart behavior and obtain owner approval before provisioning.

## 9. Final owner checklist

- [x] MIT license approved; review public source/documents before any later updates.
- [ ] Create an isolated Git repository; confirm its top-level path and staged-file list.
- [ ] Confirm ignored environment/data/model/evidence/dependency directories are absent.
- [ ] Publish only after separate authorization.
- [ ] Import frontend/ into Vercel only after separate deployment authorization.
- [ ] Verify build:demo, no credentials, no localhost API calls and visible synthetic labels.
- [ ] Complete actual browser/console/responsive QA; current local tests are not screenshots.
- [ ] Keep genuine Ollama verification, full-stack hosting and autonomous remediation out of this deployment.
