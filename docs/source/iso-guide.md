<!-- Extracted from Multimodal_Knowledge_Store_ISO26514_User_Guide.docx
     SHA-256 d13feca66cd1ff44817833cb382466716b5cd43e46d21a193d78fc72bb6c716e, pandoc 3.9 (gfm).
     Cover text box (not emitted by pandoc): "Multimodal Knowledge Store Platform" / "User and API guide".
     Header: "MULTIMODAL KNOWLEDGE STORE / USER AND API GUIDE / ISO 26514:2022".
     Footer: "Pre-release guide v1.0 • 6 October 2026" + page number. -->

Information development plan and supporting product design

Prepared for Himanshu Ninawe

Version 1.0 \| 6 October 2026 \| Pre-release design draft

Structured with reference to ISO/IEC/IEEE 26514:2022

**CLI first. Shared API. Hosted EmbeddingGemma 2.**

Upload company material. Create a named store. Connect applications through generated code.

# Document control and use

| **Item** | **Definition** |
|----|----|
| Document purpose | Explain user tasks, integration, reference information, and the documentation lifecycle. |
| Product status | Proposed service. No public deployment or installation package is supplied by this document. |
| Software baseline | Proposed /v1 API and kb CLI. Version numbers will be assigned during implementation. |
| Source baseline | Multimodal Knowledge Store Specification, version 1.1, 6 October 2026. |
| Intended users | Workspace owners, store editors, application developers, and operators. |
| Reference standard | ISO/IEC/IEEE 26514:2022, Design and development of information for users. \[R1\] |
| Document status | Original project document informed by the standard's published scope. Not a conformity certificate. |

## How this version differs

The original document describes the product and its technical requirements. This version organises the same service around user needs and tasks.

It adds prerequisites, expected results, recovery information, navigation, and a plan for maintaining user information.

Technical design and business decisions remain included as supporting material.

## Standard application

ISO/IEC/IEEE 26514:2022 addresses the development, structure, content, presentation, and maintenance of information for software users. \[R1\]

It is not a fixed document template. This document uses an original structure suitable for the proposed platform.

The full standard has not undergone a clause-by-clause assessment here. Section 18 records coverage and outstanding validation work.

No ISO clause text is reproduced. No percentage of conformity is claimed.

## Reading conventions

“Agreed” marks an established product decision. “Proposed” marks a design choice. “Later release” marks an unavailable initial capability.

Commands and endpoints are proposed examples. They require implementation and release testing before publication as operational instructions.

store_abc123, file_abc123, and job_abc123 are example IDs. Replace them with returned IDs.

https://api.example.com is a placeholder. Replace it with the actual deployed base URL.

Procedures use numbered steps. Each procedure gives its prerequisites, expected result, and recovery route.

## Navigation

Start with Section 3 if you need access and setup. Use Section 4 for the first import and search.

Use Sections 10 and 11 for command and API details. Use Section 13 when a task fails.

Use Section 19 for terms and a task index. Section 20 lists sources and unresolved release details.

# Contents

1\. Purpose, audiences, and task needs 4

2\. Service overview and concepts 5

3\. Access and setup 5

4\. First successful import and search 6

5\. Import files and manage jobs 7

6\. Inspect and edit source material 9

7\. Manage stores and custom selections 9

8\. Search and interpret results 10

9\. Connect a customer application 11

10\. CLI command reference 13

11\. API reference 14

12\. Subscription and usage 17

13\. Troubleshooting and support 18

14\. Access, retention, and deletion 19

15\. Supporting technical design 21

16\. Product requirements and delivery plan 22

17\. Information development and maintenance plan 23

18\. Documentation review and coverage 25

19\. Glossary and task index 26

20\. Sources and release information 28

# 1. Purpose, audiences, and task needs

## 1.1 Product purpose

The platform turns company material into a reusable retrieval resource. Customers name stores and connect applications to them.

The platform hosts Google EmbeddingGemma 2. It manages source storage, preparation, embeddings, indexes, and query embedding.

The first client is a CLI. A later web application will use the same API.

Customers pay for storage and the hosted embedding service. The pricing model remains a storage subscription plus an embedding surcharge.

## 1.2 User groups

| **Audience** | **Knowledge assumed** | **Information needed** |
|----|----|----|
| Workspace owner | Understands team access and subscriptions. | Permissions, usage, retention, and deletion. |
| Store editor | Can use a terminal and work with local folders. | Import, inspect, edit, retry, and organise material. |
| Application developer | Can make HTTP calls and manage secrets. | Generated code, API contracts, authentication, and source results. |
| Service operator | Can manage hosted services and queues. | Profiles, job reliability, isolation, backup, and release checks. |

Editors do not need to understand vector coordinates. Developers do not need to install the embedding model.

## 1.3 Task needs

| **Task group** | **User objective** | **Main sections** |
|----|----|----|
| Start | Gain access and complete a first search. | 3–4 |
| Load | Import files and recover interrupted work. | 5 |
| Maintain | Inspect, replace, tag, and remove material. | 6–7 |
| Retrieve | Find useful evidence and interpret its source. | 8 |
| Integrate | Connect an application to the correct store. | 9–11 |
| Control | Manage access, cost, and deletion. | 12–14 |
| Operate | Understand service design and release boundaries. | 15–16 |

## 1.4 User environment

The initial service assumes a network connection to the hosted API. Local folders remain on the user's machine until uploaded.

The CLI must upload the actual files. Passing a local path does not give the server access to that folder.

The planned web interface will support folder selection and connection code tabs. It is outside the first release.

## 1.5 Documentation objectives

A first-time editor should complete the core workflow without manual database work.

A developer should retrieve evidence using the generated code. Each result should identify its original source.

A user should know whether a failure concerns upload, processing, indexing, access, or quota.

These objectives require user testing before operational publication.

# 2. Service overview and concepts

## 2.1 What the service provides

The platform supplies ingestion and retrieval for RAG. The customer's application chooses the model that generates answers.

Uploading material does not train the embedding model. The platform creates an index of the material.

Several customer applications can reuse one store. Content changes can require new processing and embeddings.

## 2.2 Important concepts

| **Concept** | **Meaning for a user** |
|----|----|
| Workspace | The team ownership and access boundary. |
| Store | A named resource that an application searches. |
| File version | An immutable copy of source content. |
| Segment | A passage, image, or media portion with a source location. |
| Embedding | A numerical representation used to find similar content. |
| Profile | The model and processing configuration associated with an index. |
| Job | A tracked background operation, such as an import. |
| Index revision | The published searchable version used for a query. |

An embedding cannot reconstruct the original material. The platform must preserve the content or a durable source reference.

## 2.3 Store types

A material store contains explicitly assigned sources. A live view uses a saved filter over parent stores.

A snapshot preserves fixed membership at selected source versions. Live views and snapshots belong to the later composition release.

Each type has a stable store ID. A name change must not break application connections.

## 2.4 Responsibility boundary

| **Platform responsibility** | **Customer responsibility** |
|----|----|
| Host the model and index infrastructure. | Supply material the workspace may use. |
| Prepare and index supported content. | Review file failures and retrieval quality. |
| Enforce access and store configuration. | Protect application credentials. |
| Return evidence with source references. | Use evidence appropriately in the application. |
| Report usage and plan limits. | Select a suitable plan and retention policy. |

# 3. Access and setup

## 3.1 Prerequisites

Before first use, obtain a workspace, a permitted identity, and the deployed API base URL.

Use a terminal on a supported operating system. The first release must publish supported systems and runtime requirements.

The customer machine does not need a GPU or model weights. It needs enough local capacity to read the selected files.

Obtain the CLI package from the published release channel. The exact package name and installation command remain open.

Do not treat a proposed command name as an available package.

## 3.2 T01 — Configure and authenticate the CLI

Prerequisites: an installed CLI, network access, and a workspace invitation or permitted account.

1\. Set the API base URL through the released configuration method.

2\. Run kb auth login.

3\. Complete the published authentication flow.

4\. Select an accessible workspace.

5\. Check the identity and workspace shown by the CLI.

Expected result: the CLI can list stores in the selected workspace.

If authentication fails, follow Section 13.1. If the workspace is missing, ask its owner to check membership.

Human authentication and application keys are separate credentials. A future device flow can use a browser without requiring a product web interface.

## 3.3 Credentials for scripts

Scripts and applications use scoped service credentials. They must not depend on an interactive login session.

Keep credentials in the operating system's credential store or an approved secret manager. Do not include secrets in logs or source control.

The proposed API uses bearer authentication. Section 9 explains the application integration.

## 3.4 Limits and capabilities

Read the published format list, upload limits, and plan limits before a large import.

The API must expose validated models and profiles. The first model is EmbeddingGemma 2, not Gemini Embedding 2.

The model card describes text, image, audio, video, and combined inputs. Product support also depends on validated parsers and codecs. \[R2\]

# 4. First successful import and search

## 4.1 T02 — Complete the first workflow

Prerequisites: complete T01 and prepare a small folder of supported files.

1\. Run kb stores create manuals.

2\. Record the returned store ID.

3\. Run kb ingest manuals ./company-material --wait.

4\. Review the uploaded and indexed file counts.

5\. Inspect any failed-file results.

6\. Run kb search manuals "Replace the pressure sensor" --limit 5.

7\. Check the returned passage or media reference.

8\. Check the original source and location.

9\. Create an application key for this store.

10\. Run kb connect manuals --language python.

11\. Copy the generated code into the customer application.

12\. Execute the code with the application key.

Expected result: a separate application retrieves relevant content from the selected store.

The sample names and query are illustrative. Choose a query with an expected source in your own folder.

## 4.2 Proposed command sequence

kb auth login\
kb stores create manuals\
kb ingest manuals ./company-material --wait\
kb search manuals "Replace the pressure sensor" --limit 5\
kb keys create --store manuals --scope search,source:read\
kb connect manuals --language python

The proposed key scope names require confirmation in the API contract.

## 4.3 Check completion

Uploading bytes and indexing content are different stages. Do not connect an application based only on upload completion.

A completed job means all required files succeeded. A completed-with-errors job means that only part of the submitted material is available.

A similarity score does not prove that the result answers the question. Review source relevance before production use.

## 4.4 Recovery routes

| **Observation** | **Next action** |
|----|----|
| Transfer stopped | Resume the upload session. See T04. |
| Some files failed | Inspect the job item report. See T05. |
| Search returns nothing | Check store state, filters, and material. See Section 13. |
| Code cannot authenticate | Check the key, store scope, and base URL. See Section 9. |

# 5. Import files and manage jobs

## 5.1 Formats and preparation

| **Source type** | **Proposed initial format** | **Preparation and source reference** |
|----|----|----|
| Text | TXT and Markdown | Passages with relative paths and offsets. |
| Documents | Text PDF | Passages with page references. |
| Scans | Image PDF | Page images or validated OCR with page references. |
| Images | JPEG and PNG | Image records with file version IDs. |
| Audio | WAV and MP3 | Segments with source start and end times. |
| Video | MP4 | Segments with source times and configured media streams. |

This support list is proposed. Publish each format only after parser, codec, and retrieval tests pass.

Long material produces multiple segments. Related multimodal material can share an embedding when the profile supports that combination.

The system must not silently truncate inputs. Mixed inputs share the model's input budget. \[R2\]

## 5.2 T03 — Import a folder

Prerequisites: an editable store, supported files, and sufficient plan capacity.

1\. Run kb ingest STORE ./folder.

2\. Review the file manifest and exclusions.

3\. Start the upload when the released CLI requests confirmation.

4\. Record the upload session and job IDs.

5\. Run kb jobs status JOB_ID.

6\. Review the final item results.

Expected result: published source versions become searchable in the target store.

The CLI preserves relative paths. It should ignore symbolic links by default and show ignored files.

Repeated imports can reuse unchanged bytes and compatible embeddings within the workspace.

## 5.3 T04 — Recover an interrupted transfer

Prerequisites: an unexpired upload session and access to the original files.

1\. Inspect the retained upload session ID.

2\. Use the released resume option to reopen that session.

3\. Transfer the missing parts.

4\. Commit the completed manifest.

5\. Check the resulting job ID.

Expected result: the service processes one verified upload without duplicate committed content.

The resume command syntax remains a release detail. The required API operations appear in Section 11.

An expired session requires a new session. The service can still reuse verified workspace content.

## 5.4 T05 — Inspect and retry a job

1\. Run kb jobs status JOB_ID.

2\. Retrieve the failed-file results.

3\. Correct an unreadable file or other reported cause.

4\. Run kb jobs retry JOB_ID for retryable failed items.

5\. Inspect the new job report.

Expected result: successful items remain available, and retryable failed items receive new processing attempts.

A retry must not duplicate published segments. If the local file changed, upload a new file version instead.

## 5.5 T06 — Cancel processing

1\. Run kb jobs cancel JOB_ID.

2\. Wait until the job reports a terminal state.

3\. Inspect which items were published before cancellation.

Expected result: remaining work stops at a safe boundary.

Cancellation does not delete published content. Use a store or membership deletion task when removal is required.

## 5.6 Job states

| **State** | **User meaning** |
|----|----|
| queued | The service accepted the operation. |
| running | Workers process the material. |
| cancel_requested | Safe cancellation is pending. |
| completed | All required items succeeded. |
| completed_with_errors | Some items failed. Published successes remain available. |
| failed | The job did not publish a usable result. |
| cancelled | Processing stopped. Inspect completed items. |

Closing the CLI does not stop a committed job. Uploads must finish or remain resumable before the background job starts.

# 6. Inspect and edit source material

## 6.1 T07 — Inspect a source

Prerequisites: permission to inspect the selected store.

1\. Run kb files list STORE.

2\. Select the required file ID.

3\. Run kb files inspect FILE_ID.

4\. Check its current version, segment count, and status.

5\. Retrieve permitted segment or original content when needed.

Expected result: you can trace a searchable item to its original source and location.

For audio or video, inspect start and end times. For PDFs, inspect the page reference.

The API offers separate endpoints for file details, segments, and original content. Source downloads require permission.

## 6.2 T08 — Change metadata

1\. Run kb files tag FILE_ID --set department=service.

2\. Inspect the updated metadata.

3\. Test any store view that depends on the changed field.

Expected result: the source has the new tag. Matching live-view membership can change.

A metadata-only change usually does not require new embeddings. A processing profile can treat selected metadata as embedding input.

The API must declare which fields affect the representation. A change to those fields can trigger reprocessing.

## 6.3 T09 — Replace content

Prerequisites: editor access and a supported replacement file.

1\. Run kb files replace FILE_ID ./manual-v2.pdf.

2\. Record the returned revision job ID.

3\. Wait for the complete new file version to publish.

4\. Inspect the current version.

5\. Search for material introduced by the replacement.

Expected result: searches use the complete published replacement. The previous version remains current until publication succeeds.

A snapshot can retain the old source version. Replacement does not silently modify that snapshot.

## 6.4 T10 — Remove store membership

1\. Inspect the target store and file ID.

2\. Run kb files remove STORE FILE_ID.

3\. Check that the store no longer returns this source.

Expected result: the source is excluded from that store's retrieval scope.

This action differs from deleting the source everywhere. Other stores can retain their references.

Global source deletion needs an affected-resource preview and an explicit scope. See Section 14.

# 7. Manage stores and custom selections

## 7.1 T11 — Create or rename a store

Prerequisites: permission to create or edit stores in the workspace.

1\. Run kb stores create NAME.

2\. Record its stable ID and selected profile.

3\. Inspect it with kb stores info STORE.

Expected result: an empty store exists and can accept material.

A rename uses PATCH /v1/stores/{id}. The final CLI rename syntax must be published with the release.

Applications use IDs, so a name change must preserve their connection.

## 7.2 T12 — Merge stores

Availability: later composition release.

Prerequisites: permitted parent stores with compatible profiles.

1\. Inspect the parent profiles.

2\. Run kb stores merge manuals training --into support.

3\. Check the returned job and target store IDs.

4\. Review duplicate removal and source references.

5\. Run a representative target-store search.

Expected result: a new store combines compatible material without unnecessary re-embedding.

The service must reject incompatible profiles. An explicit later rebuild mode can generate all target vectors from retained source content.

Matching vector dimensions alone do not establish compatibility.

## 7.3 T13 — Create a custom store

Availability: later composition release.

Prerequisites: access to parent stores and a valid filter definition.

1\. Prepare a structured filter file.

2\. Select live-view or snapshot behaviour.

3\. Run the released derive command.

4\. Inspect the new store ID and membership.

5\. Generate connection code for the derived store.

Expected result: the application can search the selected material through its own store ID.

A live view follows current matching membership. A snapshot keeps fixed membership at selected source versions.

A derived store does not grant access beyond the creator's permitted scope.

## 7.4 T14 — Delete a store

Prerequisites: delete permission and knowledge of dependent applications.

1\. Request a deletion preview for the store ID.

2\. Review memberships and dependent references.

3\. Submit the scoped deletion request.

4\. Check the deletion job.

5\. Confirm that searches to the deleted store fail.

Expected result: the store becomes inaccessible. Cleanup removes data only when no retained reference requires it.

The first CLI must expose preview and delete operations. Final flag names remain a release detail.

Deleting a store does not necessarily remove shared original files. Section 14 explains retained references and backups.

# 8. Search and interpret results

## 8.1 T15 — Run a text search

Prerequisites: an accessible store with published content.

1\. Run kb search STORE "Your question" --limit 5.

2\. Read each returned source reference.

3\. Inspect the passage, image, or media portion.

4\. Open the permitted original when context is necessary.

Expected result: relevant evidence comes from the selected store's active index.

Add metadata filters to narrow the scope. Keep filters in a structured file when shell quoting would become difficult.

The service selects the query profile automatically. The customer does not supply a new model choice for every search.

## 8.2 Result fields

| **Field**      | **Meaning**                                            |
|----------------|--------------------------------------------------------|
| request_id     | Identifier for support and diagnostics.                |
| store_id       | The logical resource searched.                         |
| index_revision | The published index used for this result.              |
| profile_id     | The embedding and preparation configuration.           |
| segment_id     | The returned passage or media portion.                 |
| score          | A ranking value from the configured similarity method. |
| content        | The available passage or media reference.              |
| source         | File ID, version ID, filename, and location.           |

A score is not an answer-confidence percentage. No universal score threshold fits all datasets.

An empty result does not always mean missing material. Filters, permissions, indexing state, and relevance can affect results.

## 8.3 Media and mixed queries

Availability: later query release, after validation.

Upload a temporary query asset and obtain its ID. Submit that ID to the documented store-search request.

Use a media reference with its correct type. The platform must validate asset access and expiry.

A related text description can accompany the media. Unrelated items should not share one query representation.

Do not assume that a generic OpenAI text-embeddings SDK supports media objects. Section 11 describes the separate extension.

## 8.4 Retrieval testing

Test questions with known source material. Include exact product codes and less common wording.

Check both relevance and source accuracy. Index completion alone does not prove useful retrieval.

Dense search can miss exact identifiers. Hybrid search is a later option when evaluations justify it.

# 9. Connect a customer application

## 9.1 T16 — Generate the store connection

Prerequisites: a searchable store and permission to create or use an application key.

1\. Create a key with the required store and operation scopes.

2\. Run kb connect STORE --language python.

3\. Record the store ID and API base URL.

4\. Put the key in the application's secret configuration.

5\. Execute the generated search example.

6\. Inspect its returned source references.

Expected result: the application retrieves evidence from the correct store and compatible model profile.

The connection output must include available code tabs, the embeddings base URL, and the matching query-model alias.

The future React/Next.js web interface will show these details in a connection modal.

## 9.2 Default integration

Use the store search endpoint for the simplest integration. It embeds the query and retrieves evidence in one request.

The backend performs model selection, access checks, membership filtering, and source retrieval.

The application can send the resulting evidence to its own answer model. This service does not require OpenAI-hosted inference.

## 9.3 Python search example

Install the HTTP client with python -m pip install requests.

Set KNOWLEDGE_API_KEY through a secret manager or environment configuration. Replace the placeholder URL and store ID.

import os\
import requests\
\
response = requests.post(\
"https://api.example.com/v1/stores/store_abc123/search",\
headers={\
"Authorization": f"Bearer {os.environ\['KNOWLEDGE_API_KEY'\]}"\
},\
json={\
"query": {"text": "How do I replace the pressure sensor?"},\
"limit": 5\
},\
timeout=30\
)\
response.raise_for_status()\
for result in response.json()\["results"\]:\
print(result\["source"\])\
print(result\["content"\])

## 9.4 Direct text embeddings example

Use this route when an application needs a query vector. It does not retrieve store content by itself.

The model alias below is a placeholder for an immutable query profile. Use the alias returned for your store.

import os\
import requests\
\
response = requests.post(\
"https://api.example.com/v1/embeddings",\
headers={\
"Authorization": f"Bearer {os.environ\['KNOWLEDGE_API_KEY'\]}"\
},\
json={\
"model": "eg2-profile_abc123-query",\
"input": "How do I replace the pressure sensor?",\
"encoding_format": "float"\
},\
timeout=30\
)\
response.raise_for_status()\
vector = response.json()\["data"\]\[0\]\["embedding"\]

The platform hosts EmbeddingGemma 2 behind this endpoint. The key belongs to this platform, not OpenAI.

An existing SDK may use the deployed base URL if it matches the declared compatibility subset. Pin and test that SDK before release.

## 9.5 JavaScript search example

Use a server-side environment with a supported fetch implementation.

const response = await fetch(\
"https://api.example.com/v1/stores/store_abc123/search",\
{\
method: "POST",\
headers: {\
Authorization: \`Bearer \${process.env.KNOWLEDGE_API_KEY}\`,\
"Content-Type": "application/json"\
},\
body: JSON.stringify({\
query: {text: "How do I replace the pressure sensor?"},\
limit: 5\
}),\
signal: AbortSignal.timeout(30000)\
}\
);\
if (!response.ok) {\
throw new Error(\`Search failed: \${response.status}\`);\
}\
const data = await response.json();\
console.log(data.results);

Keep application secrets in the customer backend. Browser code must not contain a permanent service key.

## 9.6 Connection failure

Confirm the actual base URL, key status, store ID, and allowed scopes.

Check that the store has published content. Record the request ID if the service returns an error.

Direct PostgreSQL access is an advanced later feature. It requires restricted roles and enforced membership rules.

# 10. CLI command reference

## 10.1 Proposed commands

| **Command** | **Purpose** |
|----|----|
| kb auth login | Authenticate a human user. |
| kb stores create NAME | Create an empty named store. |
| kb stores list | List accessible stores. |
| kb stores info STORE | Inspect state, profile, and size. |
| kb stores delete STORE | Delete a store after scoped review. |
| kb ingest STORE ./folder | Upload and index local material. |
| kb jobs status JOB_ID | Inspect job state and progress. |
| kb jobs retry JOB_ID | Retry eligible failed items. |
| kb jobs cancel JOB_ID | Request safe cancellation. |
| kb files list STORE | List assigned sources. |
| kb files inspect FILE_ID | Inspect a file version and its segments. |
| kb files tag FILE_ID --set KEY=VALUE | Update source metadata. |
| kb files replace FILE_ID ./file | Upload a replacement version. |
| kb files remove STORE FILE_ID | Remove membership from one store. |
| kb search STORE QUERY --limit N | Retrieve ranked source content. |
| kb connect STORE --language LANGUAGE | Generate connection information and code. |
| kb keys create --store STORE | Create a restricted application key. |
| kb usage show | Read storage and processing use. |
| kb stores merge A B --into C | Combine compatible stores in a later release. |
| kb stores derive STORE --filter @file | Create a selected view or snapshot later. |

Authentication configuration, resume syntax, metadata options, and deletion flags must be finalised before release.

## 10.2 Common arguments

| **Argument or option** | **Proposed meaning** |
|----|----|
| STORE | A stable store ID or an unambiguous visible name. |
| FILE_ID and JOB_ID | IDs returned by the service. |
| --wait | Wait for a terminal job result. |
| --json | Return structured output for scripts. |
| --limit | Set the maximum result count within service limits. |
| --language | Select Python, JavaScript, or cURL connection code. |
| @filter.json | Read complex filters from a local JSON file. |

The CLI must keep progress messages separate from JSON result data.

## 10.3 Completion and exit behaviour

A submission without --wait reports acceptance, not processing success.

With --wait, failure or partial completion must produce a nonzero exit code. Numeric exit codes remain a release detail.

Errors include a stable code, explanation, and request ID. Scripts should inspect job results after asynchronous submissions.

## 10.4 Help and local operations

The released CLI must support top-level and command-level help. Help must state prerequisites, defaults, and the related API operation.

Local help, folder scans, and local configuration do not need artificial remote endpoints.

Every store, job, retrieval, and administration operation must remain accessible through the API.

# 11. API reference

## 11.1 Contract rules

Use versioned resource paths under /v1. Publish the contract through OpenAPI before the CLI depends on it.

Use HTTPS and bearer authentication. Apply workspace and store permissions to each request.

Use cursor pagination for lists. Use UTC timestamps and bytes for file sizes.

Use idempotency keys for job creation and upload commits. Reuse the same key only for the same request body.

Return HTTP 202 for accepted background work. Return a job ID and a status URL.

Return explicit errors for quota limits, incompatible profiles, and unreadable inputs.

## 11.2 Account and model operations

| **Operation** | **Proposed endpoint** |
|----|----|
| Create a human login session | POST /v1/auth/device-sessions |
| Exchange an authorised session for a token | POST /v1/auth/token |
| Inspect the current identity | GET /v1/me |
| List accessible workspaces | GET /v1/workspaces |
| List and manage workspace members | GET, POST /v1/workspaces/{id}/members |
| Update or remove a member | PATCH, DELETE /v1/workspaces/{id}/members/{member_id} |
| List, create, and revoke API keys | GET, POST /v1/api-keys; DELETE /v1/api-keys/{id} |
| List validated model aliases and profiles | GET /v1/models; GET /v1/embedding-profiles |
| Read usage and subscription status | GET /v1/usage; GET /v1/subscription |
| Inspect audit events | GET /v1/audit-events |

The identity provider and payment provider remain open choices. Provider redirects can support authentication and subscription changes.

## 11.3 Store and content operations

| **Operation** | **Proposed endpoint** |
|----|----|
| Create or list stores | POST, GET /v1/stores |
| Read or rename a store | GET, PATCH /v1/stores/{id} |
| Preview store deletion | POST /v1/stores/{id}/deletion-previews |
| Delete a store | DELETE /v1/stores/{id} |
| Read store statistics | GET /v1/stores/{id}/stats |
| List store files | GET /v1/stores/{id}/files |
| Inspect a source | GET /v1/files/{id} |
| Change source metadata | PATCH /v1/files/{id} |
| Replace source content through an upload | POST /v1/files/{id}/revisions |
| Inspect prepared segments | GET /v1/files/{id}/segments |
| Retrieve allowed original content | GET /v1/files/{id}/content |
| Remove store membership | DELETE /v1/stores/{id}/files/{file_id} |
| Delete a source within an explicit scope | DELETE /v1/files/{id} |
| Merge compatible stores | POST /v1/store-merges |
| Create a live view or snapshot | POST /v1/stores/{id}/derivations |
| Build a new index with a selected profile | POST /v1/stores/{id}/reindex-jobs |
| Promote a validated index | POST /v1/stores/{id}/index-promotions |

Composition and index-management endpoints belong to later releases. Source deletion must support a preview of affected memberships.

## 11.4 Upload, job, and retrieval operations

| **Operation** | **Proposed endpoint** |
|----|----|
| Create an upload session | POST /v1/upload-sessions |
| Inspect or abandon an upload | GET, DELETE /v1/upload-sessions/{id} |
| Transfer file parts through the API | PUT /v1/upload-sessions/{id}/files/{file_id}/parts/{part} |
| Commit the completed upload | POST /v1/upload-sessions/{id}/commit |
| Start import of committed material | POST /v1/stores/{id}/ingestions |
| List or inspect jobs | GET /v1/jobs; GET /v1/jobs/{id} |
| Read per-file results | GET /v1/jobs/{id}/items |
| Cancel or retry a job | POST /v1/jobs/{id}/cancel; POST /v1/jobs/{id}/retry |
| Search a store | POST /v1/stores/{id}/search |
| Generate connection templates | GET /v1/stores/{id}/connection |
| Create a temporary media query asset | POST /v1/query-assets |
| Delete a temporary media query asset | DELETE /v1/query-assets/{id} |
| Generate an advanced query vector | POST /v1/stores/{id}/query-embeddings |
| Generate text embeddings through the compatible interface | POST /v1/embeddings |
| Generate media or mixed embeddings through the extension | POST /v1/multimodal-embeddings |

An upload commit can include a target store and create its import job. The separate ingestion endpoint supports reuse of committed material.

The upload implementation can later issue temporary transfer URLs. Session creation and final verification remain API operations.

Local CLI helpers do not need artificial endpoints. All remote business operations must remain accessible without the CLI.

## 11.5 Common errors

| **HTTP status** | **Example code** | **Meaning** |
|----|----|----|
| 400 | INVALID_REQUEST | The request does not match the contract. |
| 401 | AUTHENTICATION_REQUIRED | The credential is missing or invalid. |
| 403 | ACCESS_DENIED | The identity lacks permission. |
| 404 | RESOURCE_NOT_FOUND | The resource is absent or not visible. |
| 409 | PROFILE_INCOMPATIBLE | The requested combination cannot share an index. |
| 413 | INPUT_TOO_LARGE | The input exceeds a published limit. |
| 415 | FORMAT_UNSUPPORTED | The service cannot process this format. |
| 429 | QUOTA_EXCEEDED | The plan or rate limit blocks this request. |
| 503 | SERVICE_UNAVAILABLE | A required service cannot accept work. |

Choose one consistent policy for concealed resources. Do not use error differences to expose another workspace.

## 11.6 OpenAI-compatible embeddings interface

OpenAI compatibility describes an HTTP contract. OpenAPI describes the machine-readable API specification. These are different concepts.

The reference embeddings interface accepts text inputs and returns vectors with ordered result indexes. \[R6\]

Our initial compatible subset accepts a string or list of strings. Return one vector for each input in its original order.

Support model, input, and encoding_format. Implement float and base64 responses before claiming compatibility with SDK defaults.

Reject token-ID inputs until a compatible token interface is explicitly supported. Never interpret OpenAI tokenizer IDs as Gemma tokenizer IDs.

Each public model alias must bind to an immutable profile and purpose. Use separate query and document aliases when their instructions differ.

Expose validated aliases through GET /v1/models. Store connection details must return the matching query alias.

{\
"model": "eg2-profile_abc123-query",\
"input": "Replace the pressure sensor",\
"encoding_format": "float"\
}

This proposed request uses POST /v1/embeddings. A successful response contains object, data, model, and usage.

Each data item contains object, embedding, and index. The production embedding has the profile's full dimension.

Usage must report measured Gemma token counts. Multimodal metering remains separate from this text usage contract.

The initial alias fixes 768 dimensions. Accept dimensions only when it matches the alias. Reject other values with a clear error.

Do not accept arbitrary unsupported parameters silently. Publish the compatibility subset and test the selected SDK versions.

## 11.7 Multimodal extension

The standard text embeddings input does not define image, audio, or video objects. \[R6\]

Use POST /v1/multimodal-embeddings for these inputs. Use uploaded asset IDs and explicitly ordered parts.

{\
"profile_id": "profile_abc123",\
"purpose": "query",\
"inputs": \[{\
"parts": \[\
{"type": "text", "text": "Find this component"},\
{"type": "image", "asset_id": "asset_abc123"}\
\]\
}\]\
}

This is a platform extension. Do not claim that an unmodified text-embeddings SDK can send these objects.

The store search endpoint remains the simplest customer interface. It selects the correct profile and performs retrieval automatically.

## 11.8 Error and model envelopes

The compatible text endpoint should return the declared OpenAI-style error envelope. Include error.message, error.type, error.param, and error.code.

Return request IDs separately for diagnostics. GET /v1/models should use a list envelope with ordered model entries.

Document supported aliases and their query or document purpose. Do not advertise response-generation endpoints that the service does not implement.

## 11.9 Asynchronous response

A long operation returns HTTP 202 and a job reference. For example:

{\
"job_id": "job_abc123",\
"state": "queued",\
"status_url": "/v1/jobs/job_abc123"\
}

This response means the request was accepted. Inspect the status endpoint for publication and per-file results.

# 12. Subscription and usage

## 12.1 Charges

The agreed model has two parts: a storage subscription and an embedding-service surcharge.

| **Charge** | **Proposed coverage** |
|----|----|
| Storage | Originals, retained versions, prepared material, vectors, and customer metadata. |
| Embedding service | Hosted model availability plus indexing and query allowances. |
| Optional excess use | Additional use enabled through an explicit plan setting. |

No prices, capacities, or contractual service targets are set in this design document.

The default service uses shared model capacity. A surcharge does not promise a dedicated GPU.

## 12.2 T17 — Review usage

1\. Run kb usage show.

2\. Review storage by content category.

3\. Review indexing and query allowances separately.

4\. Inspect warnings and remaining quota.

5\. Select a plan change through the released account flow if required.

Expected result: the owner can identify which resource approaches its limit.

A small store can create high query load. Storage use does not measure model compute use.

## 12.3 Storage rules

The proposed meter uses GiB-month. One GiB equals 1,073,741,824 bytes.

The plan must state whether retained versions and deleted-data retention remain billable.

Reused physical source bytes should count once within a workspace. Membership references should not repeat the source-byte charge.

Infrastructure replication and index overhead should be reflected in the rate, rather than unexplained separate charges.

## 12.4 Processing rules

The operator records text tokens, image work, audio duration, and video work where appropriate.

The text embeddings response reports measured Gemma token usage. Media metering needs its own declared units.

Validation failures and duplicate request replays should not create duplicate charges. Completed work before cancellation can consume an allowance.

The plan must state these rules before commercial launch. Hard caps are the proposed default when excess charges are not enabled.

# 13. Troubleshooting and support

## 13.1 Access and connection problems

| **Symptom** | **Likely cause** | **Recovery action** |
|----|----|----|
| HTTP 401 | Missing, expired, or invalid credential. | Authenticate again or replace the application key. |
| HTTP 403 | The identity lacks the operation or store scope. | Ask the owner to review permissions. |
| Store not found | Wrong ID, wrong workspace, or concealed resource. | Check visible stores and the returned ID. |
| Network failure | Wrong base URL, network block, or service outage. | Verify the deployed URL and connectivity. |
| Browser integration exposes a key | A permanent key was placed in client code. | Revoke the key and move access to the customer backend. |

Do not send a permanent key in a support report.

## 13.2 Import problems

| **Symptom** | **Likely cause** | **Recovery action** |
|----|----|----|
| Transfer stopped | Lost connection or client exit. | Resume the unexpired upload session. |
| Unsupported format | Missing parser or codec support. | Use a published supported format. |
| Encrypted PDF fails | The service cannot read protected content. | Supply an authorised readable version. |
| Job stays queued | Busy workers or plan limits. | Check queue state and service status. |
| Partial completion | One or more files failed. | Read item errors and retry corrected items. |
| Input exceeds model budget | Preparation did not split enough content. | Report the item and processing profile for correction. |

A server path cannot substitute for a local upload. Ensure the CLI transferred the manifest's file bytes.

## 13.3 Retrieval problems

| **Symptom** | **Likely cause** | **Recovery action** |
|----|----|----|
| No results | Empty index, narrow filters, or restricted membership. | Inspect store status and simplify the filter. |
| Too few filtered results | Approximate search scanned too few eligible candidates. | Report the query and filter for operator evaluation. |
| Wrong meaning | Poor segmentation or incompatible profile. | Inspect sources and compare the active profile. |
| Exact code is missing | Dense search did not rank the exact identifier. | Test keyword or hybrid retrieval when available. |
| Stale content | The replacement is unpublished or a snapshot retains an old version. | Inspect the source and store type. |
| Source link expired | Temporary access URL exceeded its lifetime. | Request a new authorised source reference. |

Operators must test selective filters with pgvector. Exact search, partitions, and scan settings can change the result count. \[R4\]

## 13.4 Compatibility problems

| **Symptom** | **Likely cause** | **Recovery action** |
|----|----|----|
| Unknown model alias | An OpenAI model name or inactive alias was supplied. | Use the alias returned by this platform. |
| Unsupported input type | A media object or foreign tokenizer IDs reached the text endpoint. | Use text strings or the media extension. |
| Dimensions rejected | The request conflicts with the selected profile. | Use the store's declared dimension. |
| SDK cannot decode output | Encoding or response schema differs from the declared subset. | Set float encoding and report the SDK version. |

OpenAI compatibility does not make the service a complete implementation of every OpenAI endpoint.

## 13.5 T18 — Prepare a support report

1\. Record the command or endpoint.

2\. Record the request ID and job ID when available.

3\. Record the CLI or SDK version.

4\. Record the store profile and index revision.

5\. Describe the expected and observed result.

6\. Remove credentials and sensitive source content.

7\. Send the report through the published support channel.

Expected result: support can locate the operation without unnecessary disclosure of customer material.

The actual support channel and response terms remain release details.

# 14. Access, retention, and deletion

## 14.1 Roles and scopes

Owners manage workspace membership and plans. Editors manage source material and stores.

Application keys can permit search, source reads, or edits independently. A search key must not permit deletion.

Each request must enforce the workspace boundary. Background workers must preserve the same boundary.

## 14.2 T19 — Revoke application access

Prerequisites: owner or key-management permission.

1\. Identify the application's key ID.

2\. Submit its revocation request.

3\. Replace or remove the key from the application.

4\. Confirm that old-key requests fail after the declared revocation delay.

Expected result: the revoked credential can no longer access the service.

The revocation delay must be published and tested. Do not assume an indefinite cache is acceptable.

## 14.3 T20 — Delete source content

Prerequisites: source-delete permission and a reviewed deletion scope.

1\. Request an affected-resource preview.

2\. Inspect stores and snapshots that retain the source.

3\. Select the authorised scope.

4\. Submit the deletion operation.

5\. Confirm that active retrieval access is removed.

6\. Inspect the cleanup job for physical removal.

Expected result: content becomes inaccessible in the selected scope. Physical cleanup follows the declared retention policy.

Store deletion and source deletion are different operations. Shared references can retain bytes outside a store-deletion scope.

Backups can have a separate removal schedule. Publish that schedule before production use.

## 14.4 Data handling

The proposed service encrypts transport and stored data. Customer content must not enter routine operational logs.

The default policy excludes customer content from model training. Any alternative requires a separate explicit agreement.

Temporary query assets and source URLs have expiry times. Recheck access before creating a source URL.

Publish hosting regions, retention, and deletion policies. This design document does not claim a legal certification.

## 14.5 Database controls

Use PostgreSQL permissions and row security as part of the workspace boundary. Verify the actual service roles and pooling behaviour. \[R7\]

Set workspace context inside each transaction. A connection reused from another request must not retain a customer's context.

The API must still enforce its own permissions. Database policy does not replace the application checks.

# 15. Supporting technical design

<img src="docs/source/media/image1.png" style="width:6.75in;height:3.1125in" alt="The CLI and later React/Next.js client call a shared Next.js API. Python workers and a self-hosted EmbeddingGemma 2 service use PostgreSQL with pgvector and object storage." />

Figure 1. Both clients use the same API. Workers and the API use the data services.

## 15.1 Selected stack

The working baseline uses PostgreSQL, pgvector, React, and Next.js. The model is self-hosted EmbeddingGemma 2.

React and Next.js support the later workbench. Next.js Route Handlers can expose the initial HTTP service without customer-facing web pages. \[R5\]

Run Python model workers separately. Do not keep a bulk import or GPU inference job inside a long web request.

| **Component** | **Design role** |
|----|----|
| CLI | Calls the API and transfers local files. |
| Next.js API | Checks access, manages resources, and dispatches work. |
| React/Next.js web client | Later interface for stores, sources, progress, and connection code. |
| PostgreSQL catalogue | Owns identities, versions, jobs, and membership. |
| pgvector | Stores compatible vectors and supports similarity queries. |
| Object storage | Retains originals and prepared media outside database rows. |
| Queue and Python workers | Run durable preparation, inference, and publication. |
| Compatibility adapter | Exposes the text contract and explicit multimodal extension. |

The architecture figure shows this shared service boundary.

## 15.2 Import and query paths

For imports, the CLI submits a manifest and verified file bytes. Workers prepare segments and generate vectors through the model adapter.

For queries, the API resolves the store, access scope, and active profile. The model service embeds the query and PostgreSQL retrieves allowed records.

The API returns evidence with source references. The generated snippet connects to this route by default.

## 15.3 PostgreSQL design

Use logical store membership rather than a separate database for every customer-facing store.

The initial vector column uses vector(768). Keep profile identity, workspace identity, source identity, and published state with each searchable record.

Catalogue and vector publication can share a PostgreSQL transaction. Object transfers and queue delivery need their own consistency controls.

Use deterministic record identities for safe retries. Reconcile orphaned objects and incomplete operations.

pgvector supports exact and approximate search. Select indexes and partitioning through filtered-retrieval tests. \[R4\]

## 15.4 Model profile

The model card identifies 740 million parameters, a shared multimodal space, native 768-dimensional output, and an 8,192-token context. \[R2\]

Pin the weight revision, adapter version, dimensions, normalization, and retrieval instructions.

Record text segmentation, image settings, audio preparation, video sampling, and inference precision.

The official guide describes a Sentence Transformers integration for media inputs. Validate that route before selecting the production server. \[R3\]

The card recommends bfloat16 or float32 rather than float16 inference. Test the selected host and reject non-finite vectors. \[R2\]

## 15.5 Model changes

A model or preparation change creates a new immutable profile. Build its index separately from the active representation.

Evaluate quality before promotion and retain a rollback route. Never mix incompatible vector spaces silently.

Existing connection details must identify the store's current query alias. Do not repoint an immutable alias to incompatible weights.

## 15.6 Reliability

Committed jobs survive CLI disconnects. Workers record durable progress and handle repeated task delivery safely.

Separate import capacity from query capacity. Enforce bounded queues, workspace quotas, and declared retry delays.

Test restoration of sources, permissions, memberships, and active index references. A restored service must not expose deleted material.

# 16. Product requirements and delivery plan

## 16.1 Agreed product decisions

| **Decision** | **Baseline** |
|----|----|
| Delivery | Hosted service with CLI first and web later. |
| Data | Text, images, audio, video, and validated combinations. |
| Model | Self-hosted Google EmbeddingGemma 2. |
| Connection | Generated code for the correct store and profile. |
| Store control | Create, inspect, edit, delete, merge, and derive. |
| API | Each remote business operation has an endpoint. |
| Pricing | Storage subscription plus embedding-service surcharge. |
| Stack | PostgreSQL/pgvector, with React/Next.js for the later interface. |

## 16.2 Initial and later capabilities

| **Initial release** | **Later release** |
|----|----|
| Named material stores and selected source formats. | Store merges, live views, and snapshots. |
| Folder uploads and durable jobs. | Source connectors and scheduled sync. |
| Text search over supported multimodal material. | Media queries and evaluated hybrid search. |
| Generated connection code and scoped keys. | Visual workbench and richer SDK support. |
| Text embeddings compatibility subset. | Further validated compatibility features. |
| Usage records, quotas, and deletion. | Self-service enterprise deployment options. |

All unavailable capabilities must remain labelled in user information.

## 16.3 Implementation sequence

1\. Validate the model runtime and source adapters.

2\. Implement PostgreSQL, object storage, identities, and the queue.

3\. Publish the OpenAPI contract and compatible embeddings subset.

4\. Complete upload, indexing, search, and connection code.

5\. Implement the CLI through those endpoints.

6\. Test isolation, deletion, retries, and usage records.

7\. Run a controlled customer pilot and measure costs.

8\. Add store composition and media queries.

9\. Add the React/Next.js web workbench.

Do not set a production date or capacity before the validation work finishes.

## 16.4 Acceptance evidence

| **Requirement** | **Required evidence** |
|----|----|
| Shared API | Core tasks execute through HTTP without the CLI. |
| Hosted model | The customer client loads no model weights. |
| Durable ingestion | Transfer resume and worker restart tests preserve correct results. |
| Source traceability | Every retrieved item resolves to a source version and location. |
| Profile compatibility | Queries use the store's active profile and purpose. |
| Store isolation | Tests prevent cross-workspace access and role bypass. |
| Compatibility subset | Declared text inputs, encodings, responses, and errors pass contract tests. |
| Model extension | Media inputs use the explicit extension and valid asset permissions. |
| Safe updates | The old or complete new file version appears in search. |
| Clear deletion | Scope becomes inaccessible before cleanup completion. |
| Usage integrity | Billing events reconcile without replay charges. |
| Store composition | Merges deduplicate; views and snapshots follow their defined membership. |
| Web reuse | The future web client calls the existing API. |

# 17. Information development and maintenance plan

## 17.1 Ownership

This section defines the proposed documentation process. The team must assign named owners before product release.

| **Responsibility** | **Proposed owner role** |
|----|----|
| User needs and scope | Product owner with customer representatives. |
| Information structure | Documentation lead. |
| Technical accuracy | API, CLI, model, and database maintainers. |
| Editorial consistency | Documentation editor. |
| Accessibility and usability | UX reviewer with representative users. |
| Security and data-policy accuracy | Service owner and designated reviewers. |
| Publication and version control | Release maintainer. |

## 17.2 User and task analysis

Interview representative owners, editors, and developers. Confirm their terminology, environment, and most frequent tasks.

Observe a first import and first integration. Identify where a user cannot determine the next action.

Record prerequisites, permissions, desired outcomes, and recovery needs. Update the task map in Section 1 from these findings.

Treat the current audience assumptions as hypotheses until validated.

## 17.3 Information architecture

Maintain separate concept, task, and reference topics. Connect them with stable topic IDs.

Each task topic contains its purpose, prerequisites, ordered steps, expected result, and recovery link.

Each reference topic defines syntax, parameters, defaults, response fields, errors, and version availability.

Use the glossary for one consistent meaning per product term. Keep store, workspace, file version, profile, and segment distinct.

## 17.4 Authoring and source control

Keep documentation source with the versioned API contract and tested examples.

Generate repetitive reference tables where practical. Review generated descriptions for usability rather than publishing schemas alone.

Keep secrets out of examples. Use the reserved example domain and obvious resource placeholders.

Record document versions, software versions, authors, review decisions, and change reasons.

## 17.5 Presentation and accessibility

Use meaningful heading levels, real table headers, and readable code blocks.

Provide alternative descriptions for diagrams. Do not use colour alone to indicate success or failure.

PDF, Word, web help, and CLI help should use consistent terminology and task names.

Check keyboard access and screen-reader navigation for later web help. Validate accessible PDF output separately before claiming accessibility conformity.

## 17.6 Documentation verification

Review technical statements against the implemented service. Execute released commands and code examples against a test deployment.

Verify links, contents references, prerequisites, error recovery, and permissions.

Give first-time users the guide without coaching. Record task completion, errors, and missing information.

Correct both the document and the product when a usability problem requires both changes.

## 17.7 Publication

Publish documentation with an explicit software compatibility range and update date.

Make CLI help available without a network request where practical. Keep online API reference and downloaded guides discoverable.

Release the public guide only after its operational procedures pass the checks in Section 18.

The current document is a pre-release design guide. Its commands have syntax examples, not evidence of a working deployment.

## 17.8 Maintenance triggers

| **Trigger** | **Required documentation update** |
|----|----|
| Endpoint or schema change | Update API reference, generated code, and affected tasks. |
| CLI option change | Update help, procedures, scripts, and command reference. |
| Model or profile change | Update aliases, limits, compatibility, and migration instructions. |
| Format support change | Update prerequisites, format lists, and troubleshooting. |
| Billing or retention change | Update usage, deletion, and commercial information. |
| Incident or support pattern | Add recovery guidance and correct misleading text. |
| Web client release | Add interface procedures while retaining API consistency. |

Use feedback and support records to prioritise maintenance. Mark deprecated information and preserve migration routes.

## 17.9 Localisation

English is the first proposed documentation language. Select further languages from customer needs.

Translate product terms consistently. Preserve command names, API paths, and resource identifiers.

Recheck procedures after translation. Do not let a translated guide describe a different software baseline.

# 18. Documentation review and coverage

## 18.1 Coverage record

This is an original project coverage record. It does not map invented clause numbers or assert formal ISO conformity.

| **Information area** | **Location** | **Current status** |
|----|----|----|
| Identification and status | Front matter and Section 20. | Included; release values remain open. |
| Audience and user needs | Section 1. | Assumptions included; user research pending. |
| Product concepts and scope | Section 2. | Included. |
| Setup and prerequisites | Sections 3–4. | Draft; installation and authentication details pending. |
| Task procedures | Sections 4–9 and 12–14. | Included; operational validation pending. |
| Command and API references | Sections 10–11. | Proposed contract; implementation tests pending. |
| Examples and outcomes | Sections 4 and 9. | Included; example execution pending. |
| Troubleshooting | Section 13. | Included; real error-message verification pending. |
| Navigation and terminology | Contents and Section 19. | Included; user navigation tests pending. |
| Presentation and accessibility | Section 17.5. | Design rules included; accessibility validation pending. |
| Review and maintenance | Section 17. | Process defined; owners and evidence pending. |
| Standard reference | Front matter and Section 20. | Published scope used; full assessment pending. |

## 18.2 Publication gates

| **Gate** | **Evidence required before operational publication** |
|----|----|
| G01 Technical baseline | A released CLI and API version match the guide. |
| G02 Installation | A clean supported machine completes setup. |
| G03 Core tasks | Representative users complete import, search, and connection. |
| G04 Recovery | Documented failures produce the stated recovery paths. |
| G05 Permissions | Procedures work with the stated role and scope. |
| G06 Examples | Python, JavaScript, and HTTP examples run against the test service. |
| G07 Navigation | Contents, task links, and glossary terms resolve correctly. |
| G08 Accessibility | Required formats pass the selected accessibility review. |
| G09 Ownership | Review owners and change control are assigned. |
| G10 Standard assessment | Any conformity claim has a completed assessment against the full standard. |

No publication gate is marked complete from document creation alone.

## 18.3 Current document checks

The delivered draft receives structural, example-syntax, and layout checks.

These checks do not establish endpoint availability, user-task success, or conformity with all requirements of the standard.

# 19. Glossary and task index

## 19.1 Glossary

| **Term** | **Meaning in this platform** |
|----|----|
| API | The HTTP interface for service operations. |
| CLI | The command-line client. |
| Embedding | A numerical representation used for similarity comparison. |
| Embedding profile | An immutable model and preparation configuration. |
| Index revision | A published searchable dataset version. |
| Ingestion | Loading, preparation, embedding, and publication of material. |
| Job | A tracked background operation. |
| Live view | A store defined by current matching parent membership. |
| OpenAI-compatible | The declared text-embeddings HTTP subset supported by this platform. |
| OpenAPI | A machine-readable description of the API contract. |
| pgvector | The PostgreSQL extension for vectors and similarity search. |
| RAG | Retrieval-augmented generation using retrieved evidence. |
| Segment | A source passage or media portion with a location. |
| Snapshot | Fixed membership at selected source versions. |
| Store | A named retrieval resource with a stable ID. |
| Workspace | The team ownership and access boundary. |

## 19.2 Task index

| **Task**                   | **Topic**         |
|----------------------------|-------------------|
| Authenticate and configure | T01, Section 3.2  |
| Cancel processing          | T06, Section 5.5  |
| Change metadata            | T08, Section 6.2  |
| Connect an application     | T16, Section 9.1  |
| Create a custom store      | T13, Section 7.3  |
| Create or rename a store   | T11, Section 7.1  |
| Delete a source            | T20, Section 14.3 |
| Delete a store             | T14, Section 7.4  |
| First import and search    | T02, Section 4.1  |
| Import a folder            | T03, Section 5.2  |
| Inspect a source           | T07, Section 6.1  |
| Merge stores               | T12, Section 7.2  |
| Recover a transfer         | T04, Section 5.3  |
| Remove store membership    | T10, Section 6.4  |
| Replace content            | T09, Section 6.3  |
| Report a problem           | T18, Section 13.5 |
| Retry a job                | T05, Section 5.4  |
| Review usage               | T17, Section 12.2 |
| Revoke a key               | T19, Section 14.2 |
| Run a text search          | T15, Section 8.1  |

# 20. Sources and release information

## 20.1 Sources

External references support technical facts. They do not approve the platform or certify the document.

\[R1\] ISO. ISO/IEC/IEEE 26514:2022, Systems and software engineering — Design and development of information for users.

<https://www.iso.org/standard/77451.html>

\[R2\] Google. EmbeddingGemma 2 model card.

<https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2>

\[R3\] Google. Multimodal Embeddings with EmbeddingGemma 2.

<https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers>

\[R4\] pgvector maintainers. Vector search, filtering, indexes, and tenant isolation.

<https://github.com/pgvector/pgvector>

\[R5\] Next.js. Route Handlers.

<https://nextjs.org/docs/app/getting-started/route-handlers>

\[R6\] OpenAI. Embeddings API reference, used for the compatibility contract.

<https://developers.openai.com/api/reference/resources/embeddings/methods/create>

\[R7\] PostgreSQL. Row Security Policies.

<https://www.postgresql.org/docs/current/ddl-rowsecurity.html>

\[R8\] Project baseline. Multimodal Knowledge Store Specification, version 1.1, 6 October 2026.

## 20.2 Release details still required

Before operational publication, add the real product name, CLI package, supported versions, base URL, and identity flow.

Add validated format limits, key scope names, support contacts, plan terms, hosting region, and retention periods.

Add the test evidence and completed reviews listed in Section 18.

## 20.3 Change record

Version 1.0 creates the user-oriented software document from the current product discussion and specification.

It includes the PostgreSQL/pgvector baseline, later React/Next.js interface, and self-hosted OpenAI-compatible text embeddings contract.

The aerospace-style specification remains a separate information product. Both documents describe the same platform.
