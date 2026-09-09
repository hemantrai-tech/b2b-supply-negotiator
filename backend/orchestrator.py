"""
Orchestrator for the Autonomous B2B Supply Chain & SLA Contract Negotiator.

WHAT THIS FILE DOES (in plain words):
1. Loads the Buyer agent, Supplier agent, and the Guardrail rules from the
   agents/ folder.
2. Makes the two agents take turns sending offers and counter-offers.
3. After every offer, checks it against the Guardrail rules (hard-coded
   rules, not an AI opinion) before letting it count.
4. Stops when both sides land on the same terms (a DEAL) or after too many
   rounds with no agreement (NO DEAL).
5. Writes two files that the frontend reads:
   - audit_log.json  -> every single offer, counter-offer, and guardrail
                         check, with timestamps
   - contract.json    -> the final signed terms (only if a deal was made)

HOW TO RUN IT:
  1. cd backend
  2. pip install -r requirements.txt
  3. Copy ../.env.example to ../.env and add your ANTHROPIC_API_KEY
     (get one at https://console.anthropic.com)
  4. python orchestrator.py

IF YOU DON'T HAVE AN API KEY YET:
  The script still works. It falls back to a simple built-in simulation
  mode so you always have something to demo while you get a key sorted.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"
OUTPUT_DIR = ROOT / "backend"
MAX_ROUNDS = 6

# Try to load a real API key. If it's not there, we run in simulation mode
# so the demo still works without any setup.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
USE_REAL_AI = bool(API_KEY)

if USE_REAL_AI:
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def now():
    return datetime.now(timezone.utc).isoformat()


def call_agent(config, conversation_history, own_attempts):
    """
    Asks one agent (buyer or supplier) for its next offer.
    conversation_history is a list of {"role": ..., "message": ...} so the
    agent can see what's been offered so far, but never sees the other
    side's private_constraints (that's what keeps it a real negotiation).
    own_attempts tracks this agent's own past offers (accepted or not) so
    simulation mode always keeps moving instead of repeating a rejected
    offer forever.
    """
    if USE_REAL_AI:
        history_text = "\n".join(
            f"{h['role']}: {json.dumps(h['offer'])} - {h['message']}"
            for h in conversation_history
        )
        prompt = (
            f"Your private constraints: {json.dumps(config['private_constraints'])}\n\n"
            f"Negotiation so far:\n{history_text if history_text else '(no offers yet, make your opening offer)'}\n\n"
            f"Respond with your next offer as JSON only."
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=config["system_prompt"],
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    else:
        # SIMULATION MODE: no API key set. We nudge each side's opening
        # offer toward the middle a little each round, so you still get a
        # realistic-looking negotiation to demo.
        if not conversation_history:
            return {
                "offer": config["opening_offer"],
                "message": f"Opening offer from {config['name']} (simulation mode).",
            }
        last_own = own_attempts[-1] if own_attempts else {"offer": config["opening_offer"]}
        last_other = next(
            (h for h in reversed(conversation_history) if h["role"] != config["role"]),
            None,
        )
        offer = dict(last_own["offer"])
        if last_other:
            offer["unit_price"] = round(
                (offer["unit_price"] + last_other["offer"]["unit_price"]) / 2, 2
            )
            offer["delivery_days"] = round(
                (offer["delivery_days"] + last_other["offer"]["delivery_days"]) / 2
            )
        return {
            "offer": offer,
            "message": f"{config['name']} moves toward middle ground (simulation mode).",
        }


def check_guardrails(offer, rules):
    """Deterministic, rule-based check. Not an AI call on purpose - these
    limits must be impossible to talk the system out of."""
    violations = []
    if not (rules["min_unit_price"] <= offer["unit_price"] <= rules["max_unit_price"]):
        violations.append(
            f"unit_price {offer['unit_price']} outside allowed range "
            f"[{rules['min_unit_price']}, {rules['max_unit_price']}]"
        )
    if not (rules["min_delivery_days"] <= offer["delivery_days"] <= rules["max_delivery_days"]):
        violations.append(
            f"delivery_days {offer['delivery_days']} outside allowed range "
            f"[{rules['min_delivery_days']}, {rules['max_delivery_days']}]"
        )
    if not (rules["min_sla_penalty_pct"] <= offer["sla_penalty_pct"] <= rules["max_sla_penalty_pct"]):
        violations.append(
            f"sla_penalty_pct {offer['sla_penalty_pct']} outside allowed range "
            f"[{rules['min_sla_penalty_pct']}, {rules['max_sla_penalty_pct']}]"
        )
    return violations


def offers_match(offer_a, offer_b, price_tolerance=0.05, delivery_tolerance=1):
    return (
        abs(offer_a["unit_price"] - offer_b["unit_price"]) <= price_tolerance
        and abs(offer_a["delivery_days"] - offer_b["delivery_days"]) <= delivery_tolerance
    )


def run_negotiation():
    buyer_cfg = load_json(AGENTS_DIR / "buyer_config.json")
    supplier_cfg = load_json(AGENTS_DIR / "supplier_config.json")
    guardrails = load_json(AGENTS_DIR / "guardrail_rules.json")["rules"]

    audit_log = []
    history = []
    own_attempts = {"buyer": [], "supplier": []}
    deal = None

    agents = [(buyer_cfg, "buyer"), (supplier_cfg, "supplier")]

    for round_num in range(1, MAX_ROUNDS + 1):
        for config, role in agents:
            result = call_agent(config, history, own_attempts[role])
            offer = result["offer"]
            own_attempts[role].append({"offer": offer, "message": result["message"]})
            violations = check_guardrails(offer, guardrails)
            passed = len(violations) == 0

            entry = {
                "round": round_num,
                "role": role,
                "agent_name": config["name"],
                "offer": offer,
                "message": result["message"],
                "guardrail_passed": passed,
                "guardrail_violations": violations,
                "timestamp": now(),
            }
            audit_log.append(entry)
            print(f"[Round {round_num}] {config['name']}: {offer} -> "
                  f"{'PASS' if passed else 'REJECTED: ' + '; '.join(violations)}")

            if not passed:
                # In a fuller version you'd loop back and ask the same
                # agent to revise. For this starter, we log it and move on.
                continue

            history.append({"role": role, "offer": offer, "message": result["message"]})

            last_buyer = next((h for h in reversed(history) if h["role"] == "buyer"), None)
            last_supplier = next((h for h in reversed(history) if h["role"] == "supplier"), None)
            if last_buyer and last_supplier and offers_match(last_buyer["offer"], last_supplier["offer"]):
                deal = offer
                break
        if deal:
            break

    result = {
        "deal_reached": deal is not None,
        "final_terms": deal,
        "rounds_taken": round_num,
        "generated_at": now(),
    }

    with open(OUTPUT_DIR / "audit_log.json", "w") as f:
        json.dump(audit_log, f, indent=2)

    if deal:
        contract = {
            "contract_id": f"CTR-{int(time.time())}",
            "parties": {"buyer": "Buyer Co.", "supplier": "Supplier Co."},
            "item": buyer_cfg["private_constraints"]["item"],
            "terms": deal,
            "signed_at": now(),
            "status": "EXECUTED",
        }
        with open(OUTPUT_DIR / "contract.json", "w") as f:
            json.dump(contract, f, indent=2)
        print(f"\nDEAL REACHED: {deal}")
    else:
        print("\nNO DEAL: rounds exhausted without convergence.")
        if os.path.exists(OUTPUT_DIR / "contract.json"):
            os.remove(OUTPUT_DIR / "contract.json")

    with open(OUTPUT_DIR / "result_summary.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nWrote audit_log.json and result_summary.json to {OUTPUT_DIR}")
    print("Open frontend/index.html in a browser to see the transcript.")


if __name__ == "__main__":
    mode = "REAL AI (Claude API)" if USE_REAL_AI else "SIMULATION (no API key set)"
    print(f"Running negotiation in {mode} mode...\n")
    run_negotiation()
