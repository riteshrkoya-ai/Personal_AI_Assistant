# 🤖 Personal AI Assistant

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![LLM Orchestration](https://img.shields.io/badge/LLM-LiteLLM%20%2B%20Ollama-orange.svg)](https://github.com/BerriAI/litellm)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **"Who are you trying to become?"** > Most productivity tools only store tasks. They do not understand *why* those tasks matter. The **Personal AI Assistant** bridges the gap between long-term identity and daily action.

---

## 📌 Overview

The **Personal AI Assistant** is a Python-based, modular AI assistant platform designed to help users manage their personal goals, daily tasks, reminders, memory, and productivity through conversational AI.

The long-term vision is to build a personalized assistant that can understand a user's goals, remember important context, provide daily guidance, summarize information, and eventually connect with external tools such as Gmail, WhatsApp, and voice interfaces.

The project starts with a focused **V1**: a text-based personal assistant that stores a user's “future self” profile, remembers tasks and preferences, and generates daily plans aligned with the user's long-term goals.

This is not meant to be just another chatbot. The goal is to build an assistant that understands who the user wants to become and helps them take small, practical steps toward that future every day.

---

## 🎯 Project Vision

Many people have long-term goals but struggle with daily execution. For example, a person may want to:
* Become a better software engineer
* Improve health and fitness
* Prepare for interviews
* Become more organized
* Improve communication
* Build better habits
* Stay consistent with learning

### The Core Concept: Future Self Assistant
Instead of asking only: *"What do you want to do today?"*, the assistant asks: *"Who are you trying to become?"* It uses that answer to guide future conversations, tasks, reminders, and daily plans.

Long-term identity ➔ Personal goals ➔ Daily tasks ➔ Reminders ➔ Reflection ➔ Progress


### Future Scope Capabilities
* 💬 **Talk conversationally** with the user.
* 🧠 **Remember** the user's goals, preferences, and progress.
* 📅 **Suggest** daily actions based on long-term goals.
* 📝 **Manage** tasks and reminders.
* ✉️ **Summarize** Gmail messages.
* 🗣️ **Support** English and Telugu voice interaction.
* 📲 **Connect** to WhatsApp or other communication channels.

---

## 🛠️ High-Level Architecture & Routing

The project is designed as a backend-first platform. By decoupling the core brain from the user interface, different interfaces can be added later (CLI, Web UI, Desktop app, Mobile app, Voice interface, WhatsApp channel) while the core backend remains the same.

### Assistant Routing Concept
The user interacts with one assistant, but internally the backend routes the request to the right module using an internal assistant router.
+-------------------------------------------------+
               |              User Interface Layer               |
               | (CLI / Web UI / Desktop / Voice / WhatsApp)     |
               +-------------------------------------------------+
                                        |
                                        v
                               [ /chat Endpoint ]
                                        |
                                        v
                            +-----------------------+
                            |   Assistant Router    |
                            +-----------------------+
                                        |
      +-----------------+---------------+---------------+-----------------+
      |                 |               |               |                 |
      v                 v               v               v                 v
+-----------+    +-------------+  +-----------+  +-------------+   +-------------+
|  General  |    | Future Self |  |   Task    |  |   Memory    |   | Daily Plan  |
|   Chat    |    |   Service   |  |  Service  |  |   Service   |   |   Service   |
+-----------+    +-------------+  +-----------+  +-------------+   +-------------+
      |                 |               |               |                 |
      +-----------------+---------------+---------------+-----------------+
                                        |
                                        v
                        +-------------------------------+
                        |           LLM Layer           |
                        |      (LiteLLM + Ollama)       |
                        +-------------------------------+
                                        |
                                        v
                        +-------------------------------+
                        |          Data Layer           |
                        |  (SQLite + Future Vector DB)  |
                        +-------------------------------+


---

## 🚀 V1 Scope & Features

V1 is the first working version of the project. The purpose of V1 is to prove the core assistant loop: **Conversation ➔ Memory ➔ Future-Self Profile ➔ Tasks ➔ Daily Plan**. It is text-based and backend-first, omitting complex integrations until core modules are stable.

### What V1 Allows a User to Do:
* Start the assistant and define a future-self profile.
* Ask general technical/conversational questions.
* Request optimized daily plans and add/complete tasks.
* Store personal preferences and receive answers influenced by goals and memory.

### 💡 Code & Interaction Examples

#### Architectural Framing Breakdown
* **Chat:** How the user talks to the assistant.
* **Future Self:** What the assistant knows about the user's long-term goals.
* **Tasks:** What the user needs to do.
* **Memory:** What the assistant remembers.
* **Router:** Decides which internal module to use.

#### Example Interaction Profile
* **Persona:** Ritesh
* **Goal:** Become a confident AI backend engineer, handle interview preparation, and manage time.

> **User:** *"I only have 20 minutes today. What should I do?"*
> 
> **Assistant:** > Based on your goal, let's keep it light but useful:
> * Review one FastAPI route for 10 minutes.
> * Write 3 bullet points explaining what that route does.
> * Say the explanation out loud once.
> 
> This keeps your streak alive and still supports your future-self goal.

---

## 🗂️ Core Modules Detail

* **Chat Module:** The conversational entry point. Receives user messages and handles routing implicitly without the user needing to know which service runs backend-side.
* **Future Self Module:** Tracks identity records separate from chat streams. Handles active, completed, paused, or updated goals as user focus scales over time.
* **Task Module:** Manages creating, listing, and completing actions. Engineered to support future recurrence tracking.
* **Memory Module:** Stores explicit preferences (e.g., *"Prefers project-based learning"*, *"Studies best in the evening"*).
* **LLM Service:** Connects to language models. Uses LiteLLM as a gateway and Ollama for local free inference, preventing provider lock-in.

---

## 📦 Planned Technology Stack

| Layer | Technologies | Advantages |
| :--- | :--- | :--- |
| **Backend Core** | Python 3.11+, FastAPI, Pydantic, Uvicorn | High performance, strict async type-safety |
| **LLM Engine** | Ollama, LiteLLM (Llama / Mistral / Phi) | Privacy-first, zero local token cost, flexible gateway |
| **Database** | SQLite (V1) ➔ PostgreSQL (Future) | Quick prototyping transitioning to production scale |
| **Memory Engine** | SQLite (V1) ➔ Qdrant Vector Store | Local embedding management for contextual RAG |
| **Scheduling** | APScheduler | Triggers automated reminders and daily planner updates |
| **Voice Stack** | Whisper / Whisper.cpp, Piper TTS | Planned local English & Telugu speech pipelines |

---

## 📂 Repository Structure

Personal_AI_Assistant_Project/
│
├── backend/
│   ├── app/
│   │   ├── main.py                 # Application entry point and startup routines
│   │   ├── config.py               # Settings management and environment parsing
│   │   │
│   │   ├── api/                    # API Endpoints & Request Handlers
│   │   │   ├── health.py
│   │   │   ├── chat.py
│   │   │   ├── future_self.py
│   │   │   ├── tasks.py
│   │   │   └── memory.py
│   │   │
│   │   ├── services/               # Core Business & Engine Logic
│   │   │   ├── llm_service.py
│   │   │   ├── agent_router.py
│   │   │   ├── future_self_service.py
│   │   │   ├── task_service.py
│   │   │   └── memory_service.py
│   │   │
│   │   ├── db/                     # Data Persistence & Session Lifecycle
│   │   │   ├── models.py
│   │   │   ├── session.py
│   │   │   └── database.py
│   │   │
│   │   └── schemas/                # Inbound/Outbound Validation Layouts
│   │       └── schemas.py
│   │
│   └── requirements.txt
│
├── assistant_cli.py                # Terminal client for running the V1 framework
├── docs/
│   └── SDD.md                      # Software Design Document
│
├── tests/                          # Automated execution verification suite
├── .gitignore
└── README.md

---

## 📋 V1 API Contract Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/health` | System Verification |
| **POST** | `/chat` | Conversational interface |
| **POST** | `/future-self/profile` | Create Identity Profile Settings |
| **GET** | `/future-self/profile` | Retrieve Identity Profile Settings |
| **PATCH** | `/future-self/profile` | Update Identity Profile Settings |
| **POST** | `/future-self/daily-plan` | Daily Engine Calculations |
| **POST** | `/tasks` | Create Task Asset |
| **GET** | `/tasks` | List Task Assets |
| **PATCH** | `/tasks/{task_id}/complete` | Complete Task Asset |
| **POST** | `/memory` | Create Memory Register |
| **GET** | `/memory/search` | Search Memory Registers |

---

## 🗺️ Project Roadmap

### Phase 0: Project Setup
Establish repository patterns, documentation matrices, dependencies, and a baseline functional `/health` API check.

### Phase 1: V1 Core Assistant
Build the primary business engine modules, seed local database migration rules, wire LiteLLM/Ollama integrations, and provide a text CLI interface.

### Phase 2: Gmail and RAG
Connect OAuth pipelines to retrieve and summarize email data, extract actionable notifications, and contextualize them against user long-term directives.

### Phase 3: Voice Assistant
Wire native speech-to-text (STT) and text-to-speech (TTS) systems supporting English, Telugu, or mixed bilingual speech paths.

### Phase 4: WhatsApp Automation
Implement safe notification layers and messaging automation pipelines under strict, user-verified configuration boundaries.

### Phase 5: Advanced Personalization
Enable adaptive habit optimization tracking, weekly reflection evaluations, emotional tone parsing, and proactive contextual nudges.

---

## 👥 Team Collaboration Plan

* **Team Lead:** Guides architecture agreements, repository setup, codebase pattern reviews, API contract standardization, and core coordination.
* **AI / LLM Engineer:** Focuses on Ollama connectivity, LiteLLM orchestration configurations, prompt safety engineering, and context-aware RAG vector queries.
* **Backend / Integration Engineer:** Reviews SQLite architecture implementations, data serialization flows, scheduling mechanisms, and external OAuth integrations.
* **Voice / UI Engineer:** Owns terminal wrappers/UIs, local audio translation testing profiles, and end-to-end interface execution loops.

---

## 🌿 Git Workflow Rules

* **Main Branch:** Holds verified, deployable codebase updates.
* **Feature Development:** Cut structured branches off main using prefixes: `feature/chat-endpoint`, `feature/future-self-profile`, `feature/task-service`.
* **Commit Standards:** Use clear imperative messaging styles:
  * `Add FastAPI health endpoint`
  * `Implement task creation API`
  * `Add local LLM service`