# NEURON: the vision (every session reads this first)

## What NEURON is

NEURON is an **independent, general-purpose AI computer**: offline-native, online-enhanced.

You give it a goal in ordinary language. It understands the goal, investigates, plans the work, picks
the right tools, does the work, checks the result with evidence, fixes what is wrong, and delivers a
verified outcome: real files, a running app, a report with sources. It keeps going across crashes,
restarts and long tasks, because its memory lives on disk, not in a model's context window.

It is **not** a chatbot, not only a coding assistant, not a website builder and not a task scheduler.
Those are things it can do; none of them is what it is.

## What it must be able to do (the architecture must allow all of it)

- **Software:** complete websites and web apps; mobile apps (Flutter and native); desktop apps; games;
  any installed language (Python, C++, JavaScript, TypeScript, Rust, Go, Java, Dart and others);
  frontend, backend, APIs, databases, authentication, tests; debugging and maintaining large existing projects.
- **Documents and data:** Excel workbooks and formulas, Word documents, PowerPoint decks, PDF reading
  with source references, file organisation, data analysis, reports and charts.
- **Research:** answers from local knowledge, multi-step investigation, calculation with real tools,
  search over stored documents, web research when connected, findings kept with their sources.
- **Media:** understand and generate images, transcribe and generate speech, process audio, edit video.
- **Automation:** operate authorised apps and terminals, long-running and scheduled jobs, approved
  messages and calls, device control.

A capability is claimed only when it has been built and verified. Everything else is reported as missing.

## How it thinks

- **One primary reasoning model per hardware tier** (2, 4, 8 GB), chosen by measurement and then frozen.
  Specialist models (vision, speech, image) may sit beside it. Models are swappable files; nothing in
  the system depends on one model.
- **The intelligence is the whole system, not the model:** persistent project state, small focused tasks,
  context slices, a shared loop (understand, investigate, plan, execute, observe, verify, revise,
  continue), changing strategy on failure, sequential roles with one model in memory, deterministic code
  wherever a model is not needed, and verification that does not trust the model's own claims.
- The research question: **how far can careful engineering extend what small local models can really do?**

## Where it runs

- The product is a **separate physical device** with its own processor, memory and storage. Phones and
  laptops talk to it over an authenticated message protocol; they never lend it their compute.
- Until that device exists, the same software runs on an ordinary computer, with the phone as the
  interface over local Wi-Fi. Two processes on one machine simulate, but do not prove, a separate device.
- **Offline first.** Basic intelligence never needs the internet or a cloud model. When connected, NEURON
  may fetch current information, updates and documentation, use approved services, or consult a cloud
  model the owner authorises. Ownership of the task, the plan, the memory and the continuity stays local.

## Non-negotiable rules for development

- Never fabricate a result, weaken a test, or hide a failure. Report partial success as partial.
- Frozen evaluations stay frozen: tasks are locked before tuning; reruns are labelled as reruns.
- Track what the model wrote versus what deterministic templates or tools produced.
- Untrusted input (generated code, downloads, web content) runs isolated, with time and memory limits.
- Sensitive actions wait for the owner's approval. No data leaves the device without permission.
