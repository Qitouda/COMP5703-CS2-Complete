# PaperTrace client handover and operations

This guide starts and operates the complete PaperTrace application from the consolidated repository. The planned client handover date is 8 November 2026. The 31 October package is the prepared delivery snapshot; the report and other course documents retain their own approval status.

## Delivery contents

- Application source: `frontend/`, `backend/` and `data/` in one repository, including the structured 50-paper corpus, schemas, rubrics and tests.
- Docker environment: root `docker-compose.yml`, `.env.docker.example`, backend and frontend Dockerfiles, frontend proxy configuration and optional help-assistant container.
- Operations: this guide and the application [user guide](../frontend/assistant/guide.md).
- Supplementary delivery: the prepared client ZIP also contains the selected evaluation evidence, human-review source records and the 5-minute-16-second demonstration video. These supplementary files are separate from the source repository.
- Links: the delivery folder's `DELIVERY_LINKS.txt` records the verified repository, archive, video and working-report locations. ZIP checksums are recorded in `SHA256SUMS.txt`.

The source repository is <https://github.com/Qitouda/COMP5703-CS2-Complete>. Repository and Drive access follow their existing permissions. The handover coordinator should confirm that the client's receiving account can open the supplied links.

## Requirements

- Docker Engine running, with Docker Compose v2.24 or later. Docker Desktop is suitable on macOS or Windows; Linux can use Docker Engine with the Compose plugin.
- Internet access for the initial base-image/dependency download and for live paper retrieval, scholarly metadata and model requests.
- Credentials and model access supplied by the receiving operator for live analysis.
- Available host ports 8080 and 8000, or alternative ports configured below.

The package supplies complete build contexts, so Docker resolves base images for the receiving host's supported Linux architecture. Runtime acceptance results name the platform actually tested; receiving operators should run the same startup checks on their host.

## First start

Extract the client ZIP and open a terminal in `Application/COMP5703-CS2-Complete`, or clone the repository and enter its root directory. Use the root Compose file throughout this guide.

Create the configuration file once, preserving any existing configuration:

```sh
# macOS / Linux
test -f .env || cp .env.docker.example .env
```

```powershell
# Windows PowerShell
if (-not (Test-Path .env)) { Copy-Item .env.docker.example .env }
```

Edit `.env` locally. For GPT analysis, set `OPENAI_API_KEY` and check that `OPENAI_BASE_URL` and `OPENAI_MODEL` match the service and model available to that account. The template preserves the project's model configuration; the receiving account must have access to the selected model. Keep credentials on the receiving machine.

```sh
docker compose version
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Open <http://localhost:8080>. The API health endpoint is <http://localhost:8000/health>. With an empty model key, the interface and health service can start, while live model analysis remains unavailable.

If the standard ports are occupied, change `PAPERTRACE_PORT` and `PAPERTRACE_API_PORT` in `.env` and recreate the services. For example, ports 18080 and 18000 keep this installation separate from another local instance.

## Use the application

1. Enter an arXiv link/identifier or upload a PDF.
2. Select an available model and request the credibility check, with the optional quality assessment.
3. Follow progress. The report provides claim, reference and code findings with source evidence; the quality report presents five scored dimensions.
4. Open evidence in the paper reader, export a report or reopen a completed run from history.
5. Use the interface controls to stop an individual check or cancel a run when needed. Resume an interrupted check when the interface offers that action.

See the [user guide](../frontend/assistant/guide.md) for report states, evidence, history and export details. A fresh installation creates an empty run history. The supplied evaluation reports are files in the delivery's evidence directory; they are not automatically loaded into the new application's history.

## Models and optional help assistant

The default live configuration uses the generic paper parser and GPT. Claude and Gemini are optional: set their credentials, confirm the endpoint/model and enable their corresponding flag only after a successful sample check. Code discovery also uses the configured OpenAI search channel. Additional configuration details are in [runtime configuration](../backend/docs/RUNTIME_CONFIGURATION.md).

To enable the help assistant:

```sh
docker compose --profile assistant up -d --build
```

It reads the maintained user guide and uses `ASSISTANT_*` settings, falling back to the configured `OPENAI_*` credentials where supported. The assistant's feedback is kept in its own Docker volume. Its availability is independent of the paper analyses.

For an installation check without paid model calls, set `LLM_PROVIDER=fixture` and `PARSER_PROVIDER=stub` in `.env`, then recreate the services with `docker compose up -d`. The interface identifies the fixture backend; run the fixed scenario from the interface. This returns a software test scenario. Restore `openai` and `generic` before checking real papers.

## Start stop and diagnostics

```sh
# State and recent logs
docker compose ps
docker compose logs --tail 100 backend frontend

# Stop containers while keeping runtime volumes
docker compose down

# Start again using the existing images
docker compose up -d

# Include the optional assistant when using that profile
docker compose --profile assistant up -d
```

The default deployment runs one backend process with SQLite and one credibility worker. The frontend uses the same-origin `/v1` API proxy. This matches the delivered single-instance execution and persistence design.

## Runtime data and backup

The `runtime_data` named volume stores the database, uploads, downloaded papers, immutable evidence, metadata state and task checkpoints under `/opt/papertrace/backend/data`. The optional assistant uses `assistant_data` for feedback. The Compose project name defaults to `papertrace`.

Take a consistent backup by stopping the backend before copying its data. Use a new, empty backup directory each time; the example below assumes `backup/runtime` does not already exist. Run the following in an installation that has already been created:

```sh
docker compose stop backend
mkdir -p backup
docker compose cp backend:/opt/papertrace/backend/data backup/runtime
docker compose start backend
```

For Windows, create `backup` with `New-Item -ItemType Directory -Force backup`, then use the same Compose commands. Keep the database, uploads and immutable evidence together. Store `.env` separately with the receiving operator's configuration records.

Restore the whole matching snapshot into an empty destination using the same application revision, rather than combining unrelated databases and evidence. After creating the receiving installation's containers and stopping its backend:

```sh
docker compose cp backup/runtime/. backend:/opt/papertrace/backend/data
docker compose run --rm --no-deps --user root backend sh -c 'chown -R 10001:10001 /opt/papertrace/backend/data'
docker compose start backend
```

The ownership step gives the backend's non-root account access to restored files. `docker compose down` preserves the volumes; `docker compose down -v` removes them and is not the normal shutdown command.

## Updates and troubleshooting

For a repository installation, first back up the runtime data, fetch the reviewed delivery revision and run `docker compose up -d --build`. For a ZIP installation, extract the replacement snapshot, transfer the operator's `.env`, retain the same Compose project name and rebuild. Updated source, Docker configuration and documentation should be distributed together.

- **Docker is unavailable:** start Docker Desktop or the Docker Engine, then run `docker info`.
- **A port is already in use:** change the two `PAPERTRACE_*_PORT` values and recreate the services.
- **No model is selectable:** configure valid credentials; inspect `/v1/models` and the backend logs. A healthy API does not validate model billing or account access.
- **An external check is unavailable:** inspect the recorded branch status and source coverage before retrying. Accuracy, intermittent availability and credibility latency remain the client's identified refinement priorities.
- **Credibility takes longer than expected:** the model timeout is an individual HTTP waiting limit, not a limit for the entire paper check. Retrieval, retries and capacity waiting add to the total duration.
- **History appears empty after moving machines:** verify that the complete matching runtime data was restored. The source ZIP contains reproducible data and software, not the developer's private runtime database.

Compose's [environment-variable handling](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) and [service health dependencies](https://docs.docker.com/compose/how-tos/startup-order/) are described in the Docker documentation.
