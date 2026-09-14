# Cauvis

Cauvis is an experimental, modular AI assistant platform being built toward a Jarvis-style architecture: one central assistant that can reason about a request, determine what information or capability is required, use only verified capabilities, verify results where possible, recover from failures, and remain honest about what it actually did.

> **Development status:** Beta 1.2E / Live Beta Round 2 checkpoint
> **Current automated regression baseline:** **56 / 56 tests passing**

Cauvis is under active development and is **not yet a finished autonomous desktop assistant**. Several execution, web, voice, persistent-memory, and device-control capabilities are intentionally unavailable until they are implemented, connected, and verified.

---

## Project Goal

The long-term goal is not simply:

```text
I do not know -> refuse
```

The target behavior is:

```text
User request
    |
Does Cauvis already have enough trusted information?
    |
    +-- YES -> Answer using appropriate provenance
    |
    +-- NO / UNCERTAIN
            |
            v
What information or capability is missing?
            |
Can Cauvis obtain it through a verified runtime/tool?
            |
    +-- YES -> retrieve / observe / execute
    |          -> verify evidence/result
    |          -> reason over the verified result
    |          -> answer
    |
    +-- NO -> can Cauvis help build/connect the capability?
               |
               +-- YES -> design / code / test / document for developer review
               |
               +-- NO -> explain the exact limitation without inventing success
```

---

## Architecture

Cauvis is designed around a single central assistant rather than multiple competing "brains."

```text
User / Interaction
        |
        v
CauvisBrain
        |
        v
Task analysis + capability mapping + reasoning + policy
        |
        v
AIModelRouter / Model Providers
        |
        v
Adaptive Planner
        |
        v
Execution Engine
        |
        v
AEM / Worker Scheduler / Workers
        |
        v
Tools / Device Integrations
        |
        v
Verification
        |
        v
Recovery
```

Core design principles:

- **Cauvis remains the central assistant.**
- Model providers are components, not separate identities.
- Model output is not execution authority.
- A model saying an action succeeded does not prove the action happened.
- Current/live facts require appropriate fresh evidence.
- User-provided facts retain their provenance.
- Missing capabilities should fail closed rather than produce fake success.
- Local operation is a first-class goal.
- Cloud providers can enhance Cauvis without becoming mandatory.

---

## Current AI Runtime

The current development environment includes native local-model support through:

- **Ollama**
- **Phi-4-mini**

Cauvis also contains provider/runtime architecture for additional model providers, including OpenAI-compatible provider handling.

Provider state is separated into concepts such as configured, healthy, available, and selected rather than assuming that a configured provider is usable.

---

## Verified Capability Truth

Cauvis uses a capability-truth model so a capability is not considered available merely because a module, configuration entry, or model claim exists.

The project uses a truth progression similar to:

```text
DEFINED
  ->
REGISTERED
  ->
BOUND TO IMPLEMENTATION
  ->
HEALTHY
  ->
TESTED
  ->
AVAILABLE
```

This is intended to prevent capability hallucination.

### Verified available in the current Beta runtime

The tested running instance currently supports core capabilities including:

- conversation
- central brain/orchestration
- AI routing
- local Ollama provider operation
- current-session conversation continuity
- user-supplied factual grounding
- explicit location grounding and correction
- deterministic shutdown commands
- capability-state reporting
- evidence/provenance transport architecture
- action and factual-safety guards

### Not currently verified as available

Depending on the running configuration, these are currently unavailable or not yet fully connected:

- persistent memory across restarts
- desktop/system action execution
- filesystem actions
- live web retrieval
- tool execution
- worker execution as a live user-facing capability
- reminders
- voice interaction
- autonomous device control

Cauvis is expected to state these limitations rather than pretend an action was completed.

---

## Factual Grounding and Evidence

Beta 1.2E introduced explicit factual provenance and evidence boundaries.

### User-supplied facts

Cauvis can maintain current-session user facts while preserving provenance such as:

- `USER_ASSERTED`
- `RUNTIME_VERIFIED`
- `RETRIEVAL_VERIFIED`
- `INFERRED`
- `UNVERIFIED`

A user assertion is not automatically treated as externally verified truth.

### Evidence model

The evidence layer distinguishes sources including:

- user assertions
- runtime observations
- retrieval evidence
- provider citations
- model generation
- unknown sources

Claim evidence states include:

- `UNVERIFIED`
- `SUPPORTED`
- `CONTRADICTED`
- `INSUFFICIENT`

A key project rule is:

```text
MODEL GENERATED A FACT != CAUVIS VERIFIED THE FACT

MODEL KNOWS SOMETHING != CAUVIS HAS CURRENT EVIDENCE FOR IT
```

---

## Current / Live Fact Boundary

Cauvis contains a deterministic factual-freshness boundary.

Requests involving live or changing information are intended to require fresh evidence rather than relying on model memory.

Examples include:

- current weather
- forecasts
- stock prices
- exchange rates
- live scores
- outages
- current officeholders
- current versions/releases
- current schedules and rankings

If the required verified retrieval capability is unavailable, Cauvis currently fails closed.

Live Beta Round 2 identified several classifier refinements that are still needed. See **Known Beta Findings** below.

---

## Action Honesty

Cauvis contains a deterministic external-action guard.

For example, if a user asks Cauvis to open Notepad but `system_actions` are not verified as available, Cauvis blocks the request and does not claim that Notepad was opened.

Model-generated text is never treated as proof that an external action occurred.

---

## Recovery and Execution Architecture

The project includes development work around:

- execution planning
- adaptive execution
- worker scheduling
- dependency graphs
- fallback behavior
- failure normalization
- recovery policy
- graph resume
- verification
- runtime-aware provider ranking and failover

These systems are being built incrementally and tested before being exposed as verified user-facing capabilities.

---

## Automated Validation

Current verified baseline:

```text
PASSED: 56
FAILED: 0
TOTAL: 56

ALL TESTS PASSED
```

Major regression milestones covered by the validation suite include:

- core orchestration
- execution/recovery behavior
- worker catalog behavior
- system context
- provider runtime
- provider configuration
- OpenAI provider architecture
- runtime-aware provider ranking
- provider failover
- Ollama local AI
- session runtime and identity
- verified capability truth
- multilingual shutdown commands
- deterministic action-claim protection
- factual context provenance
- explicit user-location extraction
- orchestrator factual grounding
- factual evidence trust boundary
- evidence transport
- factual freshness classification
- deterministic factual-freshness guard

Run the current master validation suite with:

```powershell
python .\validate_cauvis.py
```

---

## Live Beta Round 2

The project has completed a formal Live Beta Round 2 plus additional casual conversation trials.

### Successful behaviors observed

The tested runtime successfully demonstrated:

- Cauvis identity grounding
- separation of Cauvis identity from underlying model/provider identity
- current-session memory continuity
- explicit location grounding
- user location correction
- verified capability reporting
- external-action honesty
- fail-closed handling of current weather without fresh evidence
- multi-question completion on the tested case
- Spanish-language consistency on the tested case
- multilingual deterministic shutdown
- local Ollama/Phi-4-mini operation
- long-session conversation recall

### Known Beta findings

Round 2 also exposed important issues that are now part of the development roadmap:

1. **Internal prompt/context leakage**
   - Internal tags such as `<verified_capability_truth>` and `</conversation_history>` appeared in some model responses.
   - This is the highest-priority post-checkpoint fix.

2. **Factual freshness overblocking**
   - Phrases such as `right now` can incorrectly force external retrieval even when the requested information is a local runtime fact such as the active model/provider.

3. **Capability-question classification**
   - `Can you browse the web?` may be misread as a command to browse rather than a question about whether that capability exists.

4. **User assertion vs. verification request**
   - A user stating a current fact can be overblocked instead of being retained as `USER_ASSERTED` provenance.

5. **Future-weather wording**
   - Some forecast-style wording was not deterministically caught by the freshness classifier.

6. **Session-memory wording**
   - A same-session remembered fact was once incorrectly described as coming from a previous session.

7. **Developer coding-request classification**
   - Requests to *write code for developer review* to add a capability can be incorrectly treated as requests for Cauvis to autonomously modify itself.

8. **Duplicate `Cauvis:` prefix**
   - A presentation path can produce `Cauvis: Cauvis: ...`.

9. **Latency**
   - Normal local-model responses during testing were commonly observed in the approximate 5–11 second range.
   - Timing telemetry is planned before optimization.

These findings are documented in greater detail in `CAUVIS_PROJECT_STATE.md`.

---

## Project State / Development Continuity

`CAUVIS_PROJECT_STATE.md` is the project's source-of-truth development checkpoint.

It records:

- architecture decisions
- completed milestones
- test baselines
- important implementation details
- live beta findings
- known problems
- next development priorities

The purpose is to allow development to resume accurately in a future AI/developer session without relying on conversational memory alone.

`CAUVIS_CROSS_REPO_REUSE_AUDIT.md` records relevant cross-repository reuse/audit work.

---

## Source / Donor Repository Philosophy

Cauvis has been developed while studying useful concepts from several experimental assistant projects.

The design rule is:

> Reuse useful concepts and implementation ideas, but keep Cauvis as the central system.

Donor projects are treated as source/reference material rather than additional competing assistant brains.

The project intentionally rejects:

- fake metrics
- hardcoded "success"
- placeholder integrations presented as real capabilities
- model claims being treated as proof of execution

---

## Installation / Development Setup

### Requirements

Current development is primarily on:

- Windows 11
- Python 3.11
- PowerShell
- virtual environment (`.venv`)
- Ollama for local model execution

### Clone

```powershell
git clone https://github.com/chango112595-cell/Cauvis.git
cd Cauvis
```

### Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install project dependencies as required by the current development branch.

### Local AI

Install and run Ollama separately, then ensure the configured local model is available.

The current development model is:

```text
phi4-mini
```

### Run Cauvis

```powershell
python .\cauvis.py
```

### Run validation

```powershell
python .\validate_cauvis.py
```

---

## Security and Secrets

Do not commit credentials or local secrets.

The repository ignores common secret/configuration files including:

```text
.env
.env.*
```

with an exception available for a safe example configuration:

```text
.env.example
```

Any future web, email, cloud, device, or account integrations should use explicit configuration and permission boundaries rather than hardcoded credentials.

---

## Roadmap

### Immediate post-Round-2 priorities

1. Prevent internal prompt/context leakage.
2. Refine factual freshness classification.
3. Correct session-memory provenance wording.
4. Distinguish developer code/design requests from real execution requests.
5. Remove duplicate response prefixes.
6. Add latency telemetry and diagnose performance.
7. Expand multi-question regression coverage.
8. Expand language-consistency regression coverage.
9. Improve uncertainty/evidence behavior.
10. Connect a real retrieval execution/evidence bridge.

### Voice roadmap

Planned after the text/runtime Beta is sufficiently reliable:

**Beta 1.3**
- microphone input
- voice activity detection
- offline speech-to-text
- speaker output
- offline text-to-speech
- natural conversational turns

**Beta 1.4**
- wake behavior
- interruption
- background operation

Voice is intended to be another I/O layer around the **same CauvisBrain**, not a separate assistant.

---

## Current Status

Cauvis is a serious development prototype with a growing deterministic safety and truth architecture, but it is still under construction.

The current milestone demonstrates that Cauvis can increasingly distinguish between:

- what the model says
- what the user asserted
- what the runtime actually knows
- what Cauvis can actually do
- what requires current evidence
- what has and has not been verified

That distinction is foundational to the larger Jarvis-style goal.

---

## Repository

GitHub:

https://github.com/chango112595-cell/Cauvis

Current milestone baseline:

**Beta 1.2E / Live Beta Round 2 — 56/56 automated tests passing**
