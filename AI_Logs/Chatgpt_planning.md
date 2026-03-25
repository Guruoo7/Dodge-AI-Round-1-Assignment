# Graph-Based Data Modeling and Query System

They’re basically testing whether you can build a **mini enterprise data intelligence system**, not just a chatbot.

## What the company actually wants

They want you to take **separate business records** like:

- Orders
- Deliveries
- Invoices
- Payments
- Customers
- Products
- Addresses

and turn them into one **connected graph model** so a user can:

- visually explore how records connect
- ask questions in plain English
- get answers based on actual data, not hallucinations

So this assignment is checking whether you understand **data modeling + backend architecture + LLM integration + guardrails**.

---

## Their real requirement in simple words

### 1. Convert tabular business data into a connected graph
They do **not** want you to just keep tables and run basic queries.

They want you to identify:

- what should become a **node**
- what should become an **edge**
- how business flow is represented end-to-end

Example:

- Customer → places → Order
- Order → contains → Product
- Order → fulfilled_by → Delivery
- Delivery → billed_as → Invoice
- Invoice → paid_by → Payment

This graph should help trace business flow.

---

### 2. Show that graph in UI
They want an interface where the user can:

- click nodes
- expand neighbors
- inspect metadata
- understand relationships visually

It does **not** need to be super fancy.
It needs to be **clear and functional**.

---

### 3. Add a chat interface beside the graph
The user types natural language like:

- “Which products have the most billing documents?”
- “Trace invoice INV-1023”
- “Show sales orders that were delivered but not billed”

Your system should:

- understand the question
- map it to a structured query
- run the query on your dataset/database/graph
- return a grounded answer

This is the main part.

---

### 4. Make sure the LLM is controlled
They explicitly said guardrails matter.

That means your chatbot should **not** behave like normal ChatGPT.

If someone asks:

- “Write me a poem”
- “Who is the president of India?”
- “Give me startup ideas”

your system should refuse and say something like:

> This system is designed to answer questions related to the provided dataset only.

So they are testing whether you can keep the LLM **inside the business domain**.

---

## What they are evaluating behind the scenes

### Graph modeling
Can you design a meaningful graph, not random nodes and edges?

### Architecture
Can you structure backend, frontend, storage, query layer, LLM layer properly?

### Query translation
Can your LLM convert user language into SQL or graph queries safely?

### Grounding
Do answers come from data?

### Maintainability
Is your project clean, understandable, and demo-friendly?

---

# Best way to solve this

Do **not** build an overcomplicated system.

For an interview/assignment, the best impression usually comes from:

- clean architecture
- strong graph model
- a working UI
- a reliable NL-to-SQL pipeline
- proper guardrails
- 2–3 impressive demo queries

That is much better than trying 20 half-working features.

---

# Recommended solution approach

Build this as a **3-layer system**:

## Layer 1: Data + Graph Modeling
Use the dataset, clean it, normalize keys, and create relationships.

Store in either:

- **PostgreSQL / SQLite** for structured querying
- plus **NetworkX** in memory for graph visualization/traversal

This is a very strong practical choice.

Why this is good:
- SQL is easier for LLM query generation
- graph library is easier for visualization and tracing
- hybrid design looks smart in interview

---

## Layer 2: Backend API
Build backend using:

- **Python FastAPI** or **Node.js Express**
  
Best choice: **FastAPI**

Why:
- easy data handling
- good for pandas, SQLAlchemy, NetworkX
- clean API design
- easy LLM integration

Backend responsibilities:

- load and preprocess data
- create graph
- serve graph nodes/edges
- accept chat questions
- run guardrails
- generate SQL/query using LLM
- execute query
- turn result into natural language answer

---

## Layer 3: Frontend UI
Build frontend using:

- **React**
- graph library: **Cytoscape.js** or **React Flow**

Best choice: **Cytoscape.js**
because it is better suited for graph/network visualization.

Frontend sections:

- left side: chat panel
- right side: graph visualization
- details panel: selected node metadata

That layout will look very professional.

---

# Step-by-step development plan

## Phase 1: Understand and inspect the dataset
First, open the dataset and identify:

- what files/tables are present
- what columns exist
- what IDs connect entities
- whether keys are clean or messy
- whether flow is direct or indirect

You need to answer questions like:

- Does order_id connect to delivery_id?
- Does invoice connect to order or delivery?
- Does payment connect to invoice?
- Are customer/product/address separate tables or embedded?

### Output of this phase
Create a mapping document like:

- `customers.customer_id -> orders.customer_id`
- `orders.order_id -> deliveries.order_id`
- `deliveries.delivery_id -> invoices.delivery_id`
- `invoices.invoice_id -> payments.invoice_id`

This is the foundation.

---

## Phase 2: Design the graph schema
Now define your graph model.

## Recommended node types
- Customer
- Order
- OrderItem
- Product
- Delivery
- Invoice
- Payment
- Address

## Recommended edge types
- Customer → PLACED → Order
- Order → HAS_ITEM → OrderItem
- OrderItem → FOR_PRODUCT → Product
- Order → SHIPPED_AS → Delivery
- Delivery → BILLED_AS → Invoice
- Invoice → PAID_BY → Payment
- Customer → LOCATED_AT → Address
- Delivery → DELIVERED_TO → Address

### Important interview point
Explain that **OrderItem** is necessary because products usually connect through line items, not directly to an order in a normalized system.

That will impress them.

---

## Phase 3: Clean and preprocess data
Use pandas to:

- remove duplicates
- standardize ID formats
- handle nulls
- normalize dates
- create surrogate keys if necessary
- validate referential integrity

Also mark broken flows:

Examples:
- order exists but no delivery
- delivery exists but no invoice
- invoice exists without linked delivery
- invoice exists but no payment

### Output of this phase
A cleaned dataset ready for graph creation and SQL querying.

---

## Phase 4: Create storage layer
Use:

- **SQLite** if this is an assignment/demo
- **PostgreSQL** if you want to look more production-oriented

For interview speed, **SQLite is enough**.

Store normalized tables there.

Why this matters:
- LLM can generate SQL against structured schema
- SQL is deterministic
- easier to validate than free-form graph query generation

---

## Phase 5: Build graph from dataset
Create a graph using **NetworkX**.

Each row becomes nodes and edges based on your schema.

Each node should contain metadata like:

- node type
- id
- display label
- key attributes

Example:

- Customer node: name, region, segment
- Order node: order date, total amount, status
- Delivery node: delivery date, status
- Invoice node: invoice amount, billing date
- Payment node: payment date, payment status

### Output of this phase
A graph object that supports:

- neighbor lookup
- path tracing
- subgraph extraction
- node metadata inspection

---

## Phase 6: Build backend APIs
Using FastAPI, create APIs like:

### Graph APIs
- `GET /graph/summary`
- `GET /graph/node/{id}`
- `GET /graph/neighbors/{id}`
- `GET /graph/path?source=...&target=...`

### Chat API
- `POST /chat/query`

Input:

```json
{
  "question": "Trace the full flow of billing document INV-001"
}
```

Output:

```json
{
  "answer": "Billing document INV-001 is linked to Sales Order SO-1001, Delivery DEL-204, and Journal Entry JE-888.",
  "query": "...generated SQL...",
  "nodes_to_highlight": ["SO-1001", "DEL-204", "INV-001", "JE-888"]
}
```

This `nodes_to_highlight` thing is a very nice bonus feature.

---

## Phase 7: Implement conversational query pipeline
This is the most important part.

Your pipeline should look like this:

### Step 1: User enters natural language question

Example:
“Which products are associated with the highest number of billing documents?”

### Step 2: Guardrail classifier
Check whether the question is:

- in-domain
- out-of-domain
- unsafe/irrelevant

If out of domain, reject.

### Step 3: Intent extraction
Determine what kind of query it is:

- aggregation query
- path tracing query
- anomaly detection query
- entity lookup query

### Step 4: Generate structured query
Use LLM to generate SQL from:

- schema
- allowed tables
- allowed joins
- few-shot examples

### Step 5: Validate generated SQL
Before execution:
- allow only `SELECT`
- block `DROP`, `DELETE`, `UPDATE`, etc.
- verify only allowed tables/columns used
- add execution timeout

### Step 6: Execute query
Run against SQLite/Postgres.

### Step 7: Convert result to answer
Use LLM or template-based formatting to generate a natural answer based only on query result.

This prevents hallucination.

---

# Strong architecture for NL-to-SQL

Use the LLM for only these tasks:

- understanding the user question
- generating SQL
- summarizing SQL results into natural language

Do **not** let the LLM directly answer from imagination.

That’s the biggest design point.

---

## Prompting strategy
Give the LLM:

- database schema
- table relationships
- business meaning of each table
- examples of valid queries
- strict instructions:
  - only use known schema
  - return SQL only
  - do not assume missing fields
  - if query cannot be answered, say so

Example system prompt idea:

- You are a data assistant for a business transaction dataset.
- You may answer only using the given schema.
- Generate read-only SQL queries.
- Use only listed tables and columns.
- If the question is unrelated to the dataset, return `OUT_OF_DOMAIN`.

That is exactly the kind of thing they want.

---

## Phase 8: Build graph visualization UI
Frontend layout:

### Left panel
Chat interface

### Center/right panel
Graph visualization

### Bottom/side drawer
Selected node details

Graph features:
- zoom and pan
- click node to inspect
- expand neighbors
- highlight traced path from chat result

This “highlight traced path from answer” is a killer feature for demo.

---

## Phase 9: Add broken flow detection
This is one of their sample requirements, so make it strong.

Examples of broken flows:

- delivered but not billed
- billed without delivery
- invoice without payment
- order with missing customer
- delivery with missing address

You can implement this with SQL rules or graph traversal checks.

Example:
- left join deliveries to invoices
- where invoice is null
- mark as incomplete

This is a very business-useful feature and looks impressive.

---

## Phase 10: Add guardrails
You must implement this clearly.

## Basic guardrail method
Before sending a question to SQL generator:

1. keyword/domain check
2. optional LLM classifier
3. reject if unrelated

Examples of allowed topics:
- orders
- deliveries
- invoices
- billing
- customers
- products
- payments
- addresses
- flow trace
- broken flow

Examples rejected:
- jokes
- politics
- coding questions
- general knowledge

### Better guardrail
Use a two-stage approach:

- stage 1: simple rule-based filter
- stage 2: LLM domain classifier for borderline cases

This sounds mature in interviews.

---

# Best tech stack for this assignment

## Recommended
### Backend
- FastAPI
- pandas
- SQLAlchemy
- SQLite
- NetworkX

### Frontend
- React
- Cytoscape.js
- Axios
- simple chat UI

### LLM
- Gemini API or OpenAI API

Since you mentioned Gemini API before, that is fine.

---

# Best folder structure

```bash
project/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   ├── graph.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── guardrails.py
│   │   │   ├── prompts.py
│   │   ├── services/
│   │   │   ├── data_loader.py
│   │   │   ├── graph_builder.py
│   │   │   ├── sql_generator.py
│   │   │   ├── query_executor.py
│   │   │   ├── response_generator.py
│   │   ├── models/
│   │   │   ├── schema.py
│   │   │   ├── db_models.py
│   │   └── db/
│   │       ├── app.db
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── GraphView.jsx
│   │   │   ├── ChatPanel.jsx
│   │   │   ├── NodeDetails.jsx
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.jsx
│
├── data/
│   ├── raw/
│   ├── processed/
│
├── notebooks/
├── README.md
```

This structure looks clean and professional.

---

# How to present the solution to interviewer

You should explain it in phases like this:

## Phase A: Data understanding and normalization
Understand source tables and relationships.

## Phase B: Graph modeling
Map entities to nodes and business relationships to edges.

## Phase C: Hybrid query architecture
Use SQL database for reliable querying and graph structure for traversal/visualization.

## Phase D: LLM-powered natural language querying
Translate questions to SQL safely, execute them, summarize results.

## Phase E: UI and explainability
Visual graph + highlighted nodes + metadata inspection.

## Phase F: Guardrails
Restrict out-of-domain questions and unsafe query generation.

This will sound very strong.

---

# What will impress them most

These are the high-value things:

### 1. Hybrid design
“Graph for relationships + SQL for deterministic querying”

Very smart and practical.

### 2. Path tracing
Given an invoice, highlight complete flow in graph.

### 3. Broken flow detection
Business anomaly detection is very useful.

### 4. Safe NL-to-SQL
Read-only SQL generation with validation.

### 5. Grounded answers
Every response comes from executed data.

### 6. Highlight nodes from answer in graph
Super demo-friendly.

---

# What not to do

Avoid these mistakes:

### Don’t make it only a chatbot
They asked for graph + chat, not only chat.

### Don’t make it only a graph viewer
The LLM query part is core.

### Don’t let LLM answer directly
Must be data-backed.

### Don’t overbuild with too many fancy features
A solid working core is much better.

### Don’t skip guardrails
They explicitly mentioned this as evaluation criteria.

---

# Ideal MVP you should build first

Build these first:

### Must-have
- ingest dataset
- normalize data
- build graph
- graph UI
- chat input
- NL-to-SQL
- execute and answer
- guardrails

### Best demo queries
- top billed products
- trace billing document flow
- incomplete order flow detection

Once these work, then add:
- node highlighting
- conversation memory
- streaming response

---

# Exact step-by-step execution plan for you

## Step 1
Study dataset and identify join keys.

## Step 2
Write graph schema document:
- node types
- edge types
- attributes

## Step 3
Clean and normalize data with pandas.

## Step 4
Load cleaned data into SQLite.

## Step 5
Build NetworkX graph from same cleaned data.

## Step 6
Create FastAPI endpoints for graph exploration.

## Step 7
Create chat endpoint.

## Step 8
Implement guardrail filter.

## Step 9
Create prompt for NL-to-SQL with schema and examples.

## Step 10
Validate and execute generated SQL.

## Step 11
Convert result to grounded natural-language answer.

## Step 12
Build React UI with graph + chat + node details.

## Step 13
Add node highlighting from chat results.

## Step 14
Test against sample business questions.

## Step 15
Prepare demo script and architecture explanation.

---

# Final understanding in one line

This company wants to see whether you can build a **business data graph exploration system with a safe LLM-powered natural language query layer grounded in real data**.

---

The best next thing is a **full implementation roadmap with milestones, tech stack, modules, and what to build day by day**, so you can start coding without confusion.

