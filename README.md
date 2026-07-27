# Autonomous Multi-Agent Content Marketing Pipeline

An enterprise-grade, 3-agent **CrewAI** content orchestration pipeline designed for automated research, writing, editing, and publishing. Built with a **FastAPI** backend, **MongoDB Atlas** vector-persisted memory/knowledge stores, human-in-the-loop (HITL) approval controls, and a lightweight, responsive HTML/JS interface.

![Content Creation System Interface](https://github.com/rahmasaber123/content_creation_crewAgents_system/blob/main/project_content_imge.png?raw=true)

---

## 🏗️ System Architecture

                             ┌──────────────────────────┐
                             │   Vanilla HTML/JS UI     │
                             └────────────┬─────────────┘
                                          │ HTTP / JSON
                                          ▼
                             ┌──────────────────────────┐
                             │       FastAPI API        │
                             │ (/generate, /approve...) │
                             └────────────┬─────────────┘
                                          │
                ┌─────────────────────────┴─────────────────────────┐
                │          CrewAI Agent Orchestrator                │
                │                                                   │
                │  [1. Strategist-Researcher]                       │
                │         │                                         │
                │         ▼                                         │
                │  [2. Writer-Editor] ──── (Generates Draft) ────┐  │
                │         │                                  │  │
                └─────────┼──────────────────────────────────┼──┘
                          │                                  │
                          ▼                                  │
               ┌─────────────────────┐                       │
               │ Human-in-the-Loop   │◄──────────────────────┘
               │  Approval Check     │
               └──────────┬──────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                 │
 [Approve Clicked]                 [Reject Clicked]
         │                                 │
         ▼                                 ▼
[3. Publisher Agent]                Discard Draft
├── Generates Captions
├── Compiles PDF
└── Sends Email Notification


### 🧠 Persistence & Vector Storage Layer
* **MongoDB Atlas Vector Search:** Serves as the primary persistence layer for agent memory (short-term, long-term, and entity memory) and domain knowledge (brand guidelines, approved product claims, and technical writing rules).
* **Automated Indexing:** Attempts auto-creation of Atlas Vector Search indexes on initial run, falling back gracefully to manual JSON schema logging if restricted by tier or permissions.

---

## 🚀 Key Features

* **Multi-Agent Collaboration:** Sequential hand-off across specialized research, writing/editing, and distribution agents.
* **Human-in-the-Loop (HITL) Control:** Automated guardrails prevent immediate publishing—drafts require explicit manual approval before post-processing.
* **Grounded Brand Knowledge (RAG):** Dynamic retrieval from MongoDB Atlas knowledge stores ensures outputs strictly adhere to brand voice guidelines.
* **Multi-Format Output Delivery:** Automatically formats approved drafts into clean PDFs, compiles platform-specific social captions, and executes email dispatches.

---

## 🛠️ Tech Stack

* **Framework:** CrewAI, FastAPI
* **Database / Vector Search:** MongoDB Atlas
* **Language / Environment:** Python 3.10+, Docker / Docker Compose
* **Frontend:** Vanilla HTML5 / ES6 JavaScript

---

## 📦 Getting Started

### Prerequisites

* Python 3.10+
* MongoDB Atlas Cluster (with Vector Search enabled)
* OpenAI / LLM API Key

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/rahmasaber123/content_creation_crewAgents_system.git](https://github.com/rahmasaber123/content_creation_crewAgents_system.git)
   cd content_creation_crewAgents_system
Configure environment variables:

Bash
cp .env.example .env
Fill in your LLM keys, MongoDB connection string (MONGODB_URI), and optional settings (ENABLE_EMAIL_SEND).

Install dependencies:

Bash
pip install -r requirements.txt
Seed knowledge store:
Seed local markdown rules (knowledge/*.md) into MongoDB Atlas:

Bash
python -m src.seed_knowledge
🏃 Running the Application
Option A: Local Execution
Start the FastAPI application with uvicorn:

Bash
PYTHONPATH=src uvicorn api.main:app --reload
Open http://localhost:8000 in your browser to access the chat UI.

Option B: Docker Compose
Build and launch the complete stack using Docker:

Bash
docker compose up --build
🔄 Workflow Walkthrough
Input: Select your desired content type (Marketing Blog or Technical Guide) and submit a prompt in the chat UI.

Drafting (/generate): The Strategist-Researcher gathers domain context via RAG, passing structured notes to the Writer-Editor to produce a polished draft.

Review: The generated draft is held in a pending state in the UI.

Action:

Approve: Executes the Publisher agent to generate platform captions, compile a PDF report, and send an email dispatch.

Reject: Safely purges the draft state without publishing.


---

### Project Title & 3-Line Description

#### **Project Title:**
**Autonomous Multi-Agent AI Content Orchestration & RAG Pipeline**

#### **3-Line Description:**
An enterprise multi-agent AI pipeline built with CrewAI, FastAPI, and MongoDB Atlas Vector Search that automates the end-to-end lifecycle of technical and marketing content creation. It integrates grounded brand-voice RAG with short- and long-term memory persistence to ensure factual accuracy and consistent messaging across workflows. Features strict human-in-the-loop approval controls, automated PDF generation, social media captioning, and seamless email dispatching.
