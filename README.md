# Graph-Based Data Modeling and Query System (SAP O2C)

## Overview
This project visualizes and queries an SAP Order-to-Cash (O2C) dataset using a high-performance graph representation. It features a modern, light-themed React frontend and a Python FastAPI backend that integrates NetworkX for graph traversals and **Gemini AI** for natural language conversational queries.

---

## 🛠️ Prerequisites

Before you begin, ensure you have met the following requirements:
- **Node.js (v16+)**: Required to run the Vite React frontend.
- **Python (3.9+)**: Required to run the FastAPI backend and NetworkX graph engine.
- **Gemini API Key**: You must have an active Google Gemini API key. This needs to be placed inside a `.env` file in the `backend/` directory (`GEMINI_API_KEY="your_api_key_here"`).
- **Git**: For version control and deployment.

### 🚀 Running the Application

**1. Start the Backend API:**
```bash
cd backend
pip install -r requirements.txt
uvicorn graph_api:app --reload
```
*(The backend will start locally on port 8000)*

**2. Start the Frontend UI:**
```bash
cd frontend
npm install
npm run dev
```
*(The UI will run locally on port 5173)*

---

## 🏗️ Architecture Decisions

- **Frontend (UI/UX)**: Built with React, Vite, and Cytoscape.js. 
  - **Why Cytoscape?** It handles highly complex, interactive graph visualizations and animation flows effortlessly.
  - **UX Pattern**: The UI uses a strict "drill-down" approach. Instead of overwhelming the user with 1,500+ nodes on initial load, we start with a clean, aggregated schema-level overview (types connected by flows). Detailed instances are fetched incrementally on-demand or during specific traces.
  
- **Backend (API Layer)**: Python + FastAPI.
  - **Why FastAPI?** Chosen for its high-performance async capabilities and automatic Pydantic validation, tying perfectly into our LLM schema extraction.
  - **Core Engineering**: `NetworkX` manages the entire O2C graph in-memory. Because the target O2C subset fits comfortably in RAM, caching the dataset in NetworkX allows for lightning-fast O(1) attribute lookups and highly efficient pathfinding tracking.

---

## 💾 Database Choice

- **Backing Store (SQLite)**: The core source of truth is a normalized SQLite relational database containing O2C tables (`SalesOrder`, `BillingDocument`, `Delivery`, etc.). 
  - **Why SQLite + NetworkX?** SQLite is phenomenal for storing structured relational tables locally. However, tracing an order from `Sales -> Item -> Delivery -> Billing -> Payment` using purely SQL requires complex recursive joins/CTEs. By loading the SQLite data into a `NetworkX` Graph at startup, we get the best of both worlds: tabular storage reliability mapped into a high-speed traversal graph structure.

---

## 🤖 LLM Prompting Strategy (Gemini AI)

Our conversational pipeline is explicitly designed to be **100% Grounded**. We do not allow the LLM to answer from imagination.

1. **Structured Orchestration**: We use `google-generativeai` (Gemini-1.5-Flash) configured with strict Pydantic JSON Output schemas.
2. **Intent Classification**: The LLM acts purely as a linguistic router. It parses the user query (e.g., "Find broken flows") into an exact Intent Enum (`AGGREGATION`, `TRACE_FLOW`, `BROKEN_FLOW`, `ENTITY_LOOKUP`) and extracts necessary entity parameters (`document_id`).
3. **Deterministic Execution**: The `executor.py` module takes the extracted plan and runs deterministic Python/NetworkX or SQLite logic to fetch the exact facts.
4. **Natural Language Translation**: Finally, the raw JSON result is passed back to Gemini to format it into a brief, human-friendly summary for the chat UI.

---

## 🛡️ Guardrails

To ensure the AI assistant is not misused or derailed:

- **Pre-Execution Context Filters**: The `guardrails.py` module uses fast regex keyword screening to verify the prompt is related to the Order-to-Cash business domain. Prompts about unrelated topics are immediately blocked with zero LLM API cost.
- **Injection Protection**: Direct SQL manipulation keywords (`DROP`, `DELETE`, `INSERT`) in user input are intercepted before they touch any NLP component.
- **Isolated Execution**: Because the LLM does not write its own SQL queries directly (it simply triggers predefined python functions based on `Intent`), the attack surface for Prompt Injection leading to data breaches is eliminated.
