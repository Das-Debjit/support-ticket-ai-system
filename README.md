# Support Ticket AI System

An AI powered system for querying and analyzing a customer support ticket dataset. It answers plain English questions about the data, flags anomalies using rule based checks, and exposes everything through a REST API and a simple web UI.

Built as part of the DOTMappers AI Engineer assessment.

## What it does

- Loads a CSV of 500 support tickets into a SQLite database
- Answers natural language questions by converting them to SQL, running the SQL, then turning the result into a plain English answer
- Flags two kinds of anomalies using fixed rules: tickets that took unusually long to resolve, and high priority tickets that have been open too long
- Exposes all of this through a FastAPI backend (4 endpoints) and a Streamlit UI
- Starts everything with a single command

## Tech stack

- **Python 3.13**
- **SQLite** for the data layer (in memory, rebuilt from the CSV on every start)
- **Groq** (`openai/gpt-oss-20b`, free tier) for the language model calls
- **FastAPI** for the REST API
- **Streamlit** for the UI
- **pandas** for data loading and the anomaly rule calculations

## Setup

1. Clone the repo and move into it:
```
git clone https://github.com/Das-Debjit/support-ticket-ai-system.git
cd support-ticket-ai-system
```

2. Create and activate a virtual environment:
```
python -m venv venv
venv\Scripts\activate        (Windows)
source venv/bin/activate     (Mac/Linux)
```

3. Install dependencies:
```
pip install -r requirements.txt
```

4. Get a free Groq API key from [console.groq.com](https://console.groq.com) (no card needed), then copy `.env.example` to `.env` and paste your key in:
```
GROQ_API_KEY=your_key_here
```

5. Run everything with one command:
```
python start.py
```

This starts the API on `http://localhost:8000` and the UI on `http://localhost:8501`, and opens the UI in your browser automatically. API docs are at `http://localhost:8000/docs`.

## Architecture

```
CSV file
   |
   v
SQLite database (app/db.py)
   |
   +--> Rule based anomaly detection (app/anomalies.py)
   |
   +--> LLM query pipeline (app/llm.py)
   |       question -> LLM generates SQL -> SQL runs against SQLite
   |       -> LLM turns the result into a plain English answer
   |
   v
FastAPI backend (app/api.py)
   |
   v
Streamlit UI (ui/streamlit_app.py) -- calls the API over HTTP
```

A few decisions worth explaining:

**Why SQLite instead of just pandas.** The dataset is loaded into a real SQLite database rather than kept as a DataFrame in memory. This means the "queryable" requirement is met with actual SQL, and it gives the language model a real schema to generate queries against.

**Why the LLM generates SQL instead of answering directly.** The question first goes to the LLM to be converted into a single SQL SELECT query. That query is validated (must start with SELECT, and a blocklist catches INSERT/UPDATE/DELETE/DROP/etc. in case the model ever produces something unsafe), then run against SQLite ourselves. Only after that does the LLM see the actual result rows and turn them into a sentence. This means the exact SQL behind every answer is visible and checkable, instead of trusting the model's answer blindly.

**Why anomaly detection is rule based, not LLM based.** The two anomaly checks (resolution time outliers, aging unresolved high priority tickets) use fixed statistical/logical rules rather than asking the LLM to spot anomalies. Rules give the same result every time and can be explained in one sentence, which matters more here than flexibility.

**Why "now" is the dataset's own latest timestamp.** The dataset only covers January to March 2024. Using today's real date for "how old is this ticket" checks would make every ticket look impossibly old. Instead, the most recent `created_at` value in the dataset is treated as "now" for both the aging check and any natural language question involving "this week" or "recent".

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Confirms the API and database are up |
| POST | `/query` | Takes `{"question": "..."}`, returns the generated SQL, row count, and a natural language answer |
| GET | `/anomalies` | Runs both anomaly checks and returns the flagged tickets |
| GET | `/stats` | Quick totals by status, priority, and category |

## Example queries

These are real outputs from running the system against the actual dataset, not made up examples.

**"How many tickets are currently open?"**
```sql
SELECT COUNT(*) AS open_tickets FROM tickets WHERE status = 'Open';
```
> There are 111 tickets currently open.

**"Show me all Critical tickets that are not resolved."**
```sql
SELECT * FROM tickets WHERE priority = 'Critical' AND status IN ('Open', 'Escalated');
```
> There are 31 critical tickets that are not resolved, all with a status of either Open or Escalated.

**"What is the average customer rating for Technical category tickets?"**
```sql
SELECT AVG(customer_rating) AS avg_rating FROM tickets WHERE category = 'Technical';
```
> The average customer rating for Technical category tickets is approximately 3.74.

**"Which agent resolved the most tickets?"**
```sql
SELECT agent_id FROM tickets WHERE status='Resolved' GROUP BY agent_id ORDER BY COUNT(*) DESC LIMIT 1;
```
> Agent AGT-12 resolved the most tickets.
>
> Note: checking the raw data shows AGT-09 and AGT-12 are actually tied at 37 resolved tickets each. This query does not detect ties, see Limitations.

**"What are the top 3 agents by number of tickets handled?"**
```sql
SELECT agent_id, COUNT(*) AS ticket_count FROM tickets GROUP BY agent_id ORDER BY ticket_count DESC LIMIT 3;
```
> The top three agents are AGT-09 with 50 tickets, AGT-12 with 49 tickets, and AGT-11 with 47 tickets.
>
> Note: AGT-11 and AGT-07 are actually tied at 47 tickets each for 3rd place. The query only returns one of them. Same underlying limitation as above, confirmed here on a different query shape.

**"Show me tickets with a customer rating of exactly 1 and priority Critical."**
```sql
SELECT * FROM tickets WHERE customer_rating = 1 AND priority = 'Critical';
```
> There are two tickets that match: TKT-308 (Billing, resolved in 1.3 hrs) and TKT-426 (Technical, resolved in 5.4 hrs), both rated 1 star.

## Anomaly detection

Two checks, both rule based:

1. **Resolution time outliers.** A resolved ticket is flagged if its resolution time is more than 2 standard deviations above the mean resolution time (calculated across resolved tickets only). Currently flags 17 tickets.

2. **Aging unresolved high priority tickets.** A ticket is flagged if it is High or Critical priority, still Open or Escalated, and has been open more than 24 hours (measured from the dataset's latest timestamp). Currently flags 80 tickets.

The 80 figure looks high relative to the 173 total unresolved tickets, but this is expected for a static historical snapshot, in a live system this number would be much smaller since tickets get worked down continuously.

## Known limitations

- **Ties at the edge of a LIMIT clause aren't detected.** This showed up twice in testing, on two different query shapes: "which agent resolved the most tickets" (LIMIT 1, missed the AGT-09/AGT-12 tie at 37) and "top 3 agents by tickets handled" (LIMIT 3, missed the AGT-11/AGT-07 tie at 47 for the last spot). It's a systemic pattern with any ranking question, not a one-off. A fix would check whether the row just past the LIMIT boundary has the same value as the last included row, and mention it in the answer if so.
- **Anomaly related and time relative natural language questions can fail.** Asking things like "are there any anomalies in resolution times this week" doesn't map cleanly to SQL, since anomaly detection lives in a separate rule based endpoint, not the query layer. The system catches this safely (the SQL validator refuses to run malformed output) rather than crashing, but it returns an error instead of a useful answer. A cleaner fix would be to detect anomaly related keywords in the question and redirect to the `/anomalies` endpoint instead of forcing it through SQL generation.
- **Out of scope questions are handled correctly but only in the obvious cases.** Asking something unrelated like "what's the weather like today" correctly triggers the UNANSWERABLE fallback rather than hallucinating an answer, confirmed in testing.
- **Groq's free tier model availability can change.** This project originally used `llama-3.1-8b-instant`, which Groq deprecated for free tier use in mid 2026. It now uses `openai/gpt-oss-20b`. The model name is a single constant at the top of `app/llm.py` if it needs to change again.
- **The database resets on every restart.** Since SQLite runs in memory and is rebuilt from the CSV each time the app starts, nothing is persisted between runs. Fine for this dataset, would need a real database file for production use.
- **No authentication on the API.** Fine for a local assessment, would need auth before being exposed publicly.

## What I'd improve with more time

- Detect ties in aggregate queries and mention them in the answer
- Route anomaly related questions to the rule based endpoint instead of the SQL pipeline
- Add caching so repeated questions don't call the LLM again
- Add more test coverage, especially around the FastAPI endpoints themselves and not just the underlying functions
- Persist the SQLite database to a file instead of rebuilding it in memory each run

## Tests

A small test suite covers the SQL safety validation (blocking non-SELECT statements and destructive keywords, extracting SQL from markdown fences) and the anomaly detection counts against the known dataset. Run with:
```
python -m pytest tests/ -v
```
All 7 tests currently pass.