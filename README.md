# Autonomous B2B Supply Chain & SLA Contract Negotiator

**Problem Statement 02 — Enterprise B2B / Procurement / Supply Chain Management (Advanced)**

Two AI agents — a **Buyer** and a **Supplier** — negotiate a real supply
contract with each other. Neither one can see the other's private limits.
Every offer they make is checked against hard-coded company rules (a
**Guardrail layer**) before it counts. If they reach terms both sides
accept, the system generates a final contract and a full audit log of the
entire negotiation.

## Why this matters

Procurement teams spend huge amounts of time manually negotiating price,
delivery timelines, and SLA penalty terms with suppliers. A single AI
agent doing this alone is risky — it can be talked into a bad deal. This
project solves that by using **two separate, bounded agents plus a
rule-based guardrail** that neither agent can override, so the negotiation
stays realistic and safe at the same time.

## How it works (plain-language architecture)

```
   Buyer Agent  <---- offers/counter-offers ---->  Supplier Agent
        |                                                |
        +---------------> Guardrail Agent <--------------+
                        (hard-coded rules,
                         not another AI call)
                                |
                       audit_log.json
                       contract.json (if a deal is reached)
                                |
                        frontend/index.html
                     (shows it all as a live transcript)
```

1. **Buyer Agent** — wants the lowest price and fastest delivery, within a
   private budget it never reveals.
2. **Supplier Agent** — wants the highest price, within a private minimum
   it never reveals.
3. **Guardrail layer** — a plain rules file (`agents/guardrail_rules.json`)
   that checks every single offer. This is deliberately **not** an AI
   call — it's simple code, so it can't be argued with or hallucinate an
   exception.
4. The two agents go back and forth for up to 6 rounds. If their offers
   converge, that's a **deal** — a contract is generated automatically. If
   not, the system reports **no deal** and explains why.
5. Every offer, rejection, and reason is written to `audit_log.json` so
   the whole negotiation can be reviewed after the fact.

## Folder structure

```
your-repo/
├── agents/                    Agent configs (Lyzr-style: prompts + rules)
│   ├── buyer_config.json      Buyer's system prompt + private constraints
│   ├── supplier_config.json   Supplier's system prompt + private constraints
│   └── guardrail_rules.json   Hard rules every offer must pass
├── backend/                   The orchestration logic
│   ├── orchestrator.py        Runs the negotiation, writes the audit log
│   └── requirements.txt       Python packages needed
├── frontend/
│   └── index.html             Live transcript viewer (just open in a browser)
├── .env.example                Template for your API key (no real key inside)
└── README.md                  This file
```

## How to run it

You do **not** need an API key to see it work — it has a built-in
simulation mode. But it's more impressive with real AI reasoning behind
each agent, so setting up a key is recommended if you have time.

**Step 1 — Install dependencies**
```bash
cd backend
pip install -r requirements.txt
```

**Step 2 — (Optional but recommended) Add your API key**
```bash
cd ..
cp .env.example .env
# open .env and paste your Anthropic API key after ANTHROPIC_API_KEY=
```
Get a key at https://console.anthropic.com if you don't have one.
If you skip this step, the script automatically runs in **simulation
mode** and still produces a full demo.

**Step 3 — Run the negotiation**
```bash
cd backend
python orchestrator.py
```
You'll see each round print in the terminal, ending in either
`DEAL REACHED` or `NO DEAL`. This creates three files in `backend/`:
`audit_log.json`, `result_summary.json`, and (if a deal was made)
`contract.json`.

**Step 4 — View the transcript**
```bash
# from the repo root, in a new terminal
python -m http.server 8000
```
Then open `http://localhost:8000/frontend/index.html` in your browser.
(Opening the HTML file directly by double-clicking it won't work —
browsers block local file reads for security, so it needs a tiny local
server, which the command above starts for you.)

## What makes this "governed," not just automated

- Neither agent ever sees the other's true budget or minimum price —
  that's what makes it a real negotiation instead of a scripted handshake.
- The guardrail check is deterministic code, not an AI's opinion, so it
  cannot be reasoned around.
- Every decision (accepted or rejected, and why) is logged with a
  timestamp, producing a full audit trail — this is what "enforceable
  contract plus audit log" means in the problem statement.

## What to improve next (if there's time)

- Swap the simulation fallback for calling the real Lyzr Agent API
  instead of / alongside the Anthropic API.
- Let a rejected offer loop back to the same agent for a revision instead
  of just logging the rejection and moving on.
- Add more negotiation terms (payment terms, minimum order quantity).
- Add a second "no-deal" test scenario to `agents/` to prove the
  guardrails work under pressure (see the roadmap step "stress-test with
  an edge case").

## Team

_(add your name(s) and roles here before submitting)_
