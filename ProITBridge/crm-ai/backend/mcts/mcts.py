"""
mcts.py — Monte Carlo Tree Search for complaint/warranty decision optimization.
Pure Python, no external dependencies.

Actions:
  auto_resolve   — Bot resolves without human involvement
  escalate        — Escalate to senior support
  request_info    — Ask customer for more details
  partial_refund  — Offer partial refund (requires approval if > threshold)
  reject          — Reject the claim with explanation

State features used for scoring:
  - warranty_valid (bool)
  - days_since_purchase (int)
  - priority (low/medium/high/critical)
  - complaint_count (int) — how many times this customer has complained
  - sentiment (positive/neutral/negative)
  - ticket_age_days (int)
"""

import math, random
from typing import List, Dict, Tuple, Optional

ACTIONS = ["auto_resolve", "escalate", "request_info", "partial_refund", "reject"]

# ── Reward function ───────────────────────────────────────────────────────────
def _reward(action: str, state: Dict) -> float:
    """
    Returns a reward score [0, 1] for taking an action in a given state.
    Higher = better decision.
    """
    warranty_valid   = state.get("warranty_valid", False)
    days_purchase    = state.get("days_since_purchase", 0)
    priority         = state.get("priority", "low")
    complaint_count  = state.get("complaint_count", 0)
    sentiment        = state.get("sentiment", "neutral")
    ticket_age       = state.get("ticket_age_days", 0)
    has_evidence     = state.get("has_evidence", False)

    priority_score = {"low": 0.2, "medium": 0.4, "high": 0.7, "critical": 1.0}.get(priority, 0.3)
    sentiment_score= {"positive": 0.2, "neutral": 0.5, "negative": 0.9}.get(sentiment, 0.5)

    if action == "auto_resolve":
        # Best when: warranty valid, low priority, first complaint, recent
        score = 0.8 if warranty_valid else 0.3
        score -= 0.2 * priority_score
        score -= 0.1 if complaint_count > 2 else 0
        score += 0.1 if ticket_age < 2 else 0
        return max(0.0, min(1.0, score))

    elif action == "escalate":
        # Best when: high priority/critical, repeated complaints, negative sentiment
        score = 0.3
        score += 0.5 * priority_score
        score += 0.2 if complaint_count > 2 else 0
        score += 0.2 if sentiment == "negative" else 0
        score -= 0.3 if priority in ("low", "medium") else 0
        return max(0.0, min(1.0, score))

    elif action == "request_info":
        # Best when: no evidence, unclear issue, fresh ticket
        score = 0.6 if not has_evidence else 0.2
        score += 0.2 if ticket_age < 3 else 0
        score -= 0.3 if ticket_age > 7 else 0   # too late to ask info on old tickets
        return max(0.0, min(1.0, score))

    elif action == "partial_refund":
        # Best when: warranty valid but borderline, medium-high priority, negative sentiment
        score = 0.5 if warranty_valid else 0.2
        score += 0.3 if sentiment == "negative" else 0
        score += 0.1 * priority_score
        score -= 0.2 if days_purchase > 365 else 0  # old purchase
        return max(0.0, min(1.0, score))

    elif action == "reject":
        # Best when: warranty expired, low priority, no evidence
        score = 0.7 if not warranty_valid and days_purchase > 365 else 0.1
        score -= 0.4 if sentiment == "negative" else 0
        score -= 0.3 if priority in ("high", "critical") else 0
        return max(0.0, min(1.0, score))

    return 0.1


# ── MCTS Node ─────────────────────────────────────────────────────────────────
class MCTSNode:
    def __init__(self, action: Optional[str] = None, parent=None):
        self.action  = action
        self.parent  = parent
        self.children: List["MCTSNode"] = []
        self.visits  = 0
        self.value   = 0.0

    def uct_score(self, c: float = 1.41) -> float:
        if self.visits == 0:
            return float("inf")
        exploitation = self.value / self.visits
        exploration  = c * math.sqrt(math.log(self.parent.visits + 1) / self.visits)
        return exploitation + exploration

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def expand(self, available_actions: List[str]):
        for a in available_actions:
            self.children.append(MCTSNode(action=a, parent=self))

    def best_child(self) -> "MCTSNode":
        return max(self.children, key=lambda c: c.uct_score())

    def most_visited_child(self) -> "MCTSNode":
        return max(self.children, key=lambda c: c.visits)


# ── MCTS Search ───────────────────────────────────────────────────────────────
def mcts_decide(state: Dict, n_simulations: int = 80) -> Tuple[str, Dict]:
    """
    Run MCTS and return the best action + full scores.
    
    Args:
        state: dict with warranty_valid, days_since_purchase, priority,
               complaint_count, sentiment, ticket_age_days, has_evidence
        n_simulations: number of MCTS rollouts (80 is fast and sufficient)
    
    Returns:
        (best_action, scores_dict)
    """
    root = MCTSNode()
    root.expand(ACTIONS)

    for _ in range(n_simulations):
        # Selection
        node = root
        while not node.is_leaf():
            node = node.best_child()

        # Expansion
        if node.visits > 0 and node.is_leaf():
            node.expand(ACTIONS)
            if node.children:
                node = random.choice(node.children)

        # Simulation (rollout)
        reward = _reward(node.action, state) if node.action else 0.0
        # Add small noise for exploration
        reward += random.gauss(0, 0.05)
        reward = max(0.0, min(1.0, reward))

        # Backpropagation
        while node is not None:
            node.visits += 1
            node.value  += reward
            node = node.parent

    # Result
    scores = {}
    for child in root.children:
        avg = (child.value / child.visits) if child.visits > 0 else 0.0
        scores[child.action] = round(avg, 3)

    best = root.most_visited_child()
    return best.action, scores


def build_state(ticket: Dict, warranty: Optional[Dict], customer_tickets: List[Dict]) -> Dict:
    """Build MCTS state dict from raw CRM data."""
    from datetime import datetime
    today = datetime.today()

    warranty_valid = False
    days_purchase  = 0
    if warranty:
        warranty_valid = warranty.get("status") == "Active"
        try:
            pd = datetime.strptime(warranty.get("purchase_date", ""), "%Y-%m-%d")
            days_purchase = (today - pd).days
        except Exception:
            pass

    # ticket age
    ticket_age = 0
    try:
        cd = datetime.strptime(ticket.get("created_date", ""), "%Y-%m-%d")
        ticket_age = (today - cd).days
    except Exception:
        pass

    priority   = ticket.get("priority", "medium").lower()
    sentiment  = "negative" if priority in ("high", "critical") else "neutral"
    complaint_count = len([t for t in customer_tickets if t.get("status") not in ("Closed",)])

    return {
        "warranty_valid":    warranty_valid,
        "days_since_purchase": days_purchase,
        "priority":          priority,
        "complaint_count":   complaint_count,
        "sentiment":         sentiment,
        "ticket_age_days":   ticket_age,
        "has_evidence":      bool(ticket.get("resolution_notes")),
    }
