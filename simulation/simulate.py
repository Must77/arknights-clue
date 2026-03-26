"""
Arknights Clue Gifting Strategy Simulation
Monte Carlo simulation to analyze credit yield under different gifting strategies.

See model.md for formal definitions and assumptions.

Key mechanic corrections (v2):
- Selfish players CAN delete duplicate self-clues (+5 credits each) — no permanent cap-stall
- Actual daily visits: ~1-3 per day (parameterized), not 10
- Each friend's exchange can only be visited ONCE per exchange event
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

# ============================================================
# GAME CONSTANTS
# ============================================================

N_TYPES = 7
CLUES_PER_DAY = 1.2            # Poisson rate (1 clue per ~20h)
MAX_SELF_CLUES = 10             # cap on self-generated held clues
SELF_CLUES_TARGET = 8           # selfish players delete duplicates down to this level
EXCHANGE_CREDIT = 210           # credits on exchange completion
EXCHANGE_DURATION_DAYS = 1      # exchange window (24h ≈ 1 day)
VISIT_CREDIT = 30               # credits per outgoing visit to friend's exchange
MAX_VISITS_IN_PER_WEEK = 10     # max incoming visits credited per week (paid next week)
VISITED_CREDIT = 30             # credits per incoming visit (pending)
GIFT_CREDIT_GIVER = 20          # credits to giver per clue gifted
DELETE_CREDIT = 5               # credits for deleting a self-clue duplicate
GIFT_RECV_CREDITS = (15, 10, 5) # receiver: 1st/2nd/3rd gift received today
DAILY_WALLET_CAP = 300          # wallet truncated to this at end of each day

# Clue type probability distributions
UNIFORM_PROBS = np.array([1.0 / N_TYPES] * N_TYPES)
NONUNIFORM_PROBS = np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.4])  # type 7 favored


# ============================================================
# STRATEGIES
# ============================================================

class Strategy(Enum):
    ALTRUISTIC  = "Altruistic"   # gift every self-generated clue immediately
    SELFISH     = "Selfish"      # never gift; delete duplicates when cap reached (+5 each)
    OPTIMAL     = "Optimal_S*"   # gift all duplicates (+20 each); keep uniques
    THRESHOLD_8 = "Threshold_8"  # gift duplicates only when self_total >= 8


# ============================================================
# PLAYER
# ============================================================

@dataclass
class Player:
    pid: int
    strategy: Strategy
    clue_probs: np.ndarray

    # Inventory
    self_clues: np.ndarray = field(default_factory=lambda: np.zeros(N_TYPES, dtype=int))
    recv_clues: np.ndarray = field(default_factory=lambda: np.zeros(N_TYPES, dtype=int))

    # Credits
    wallet: float = 0.0
    total_spent: float = 0.0
    total_wasted: float = 0.0

    # Daily counters (reset each day)
    recv_count_today: int = 0
    visits_out_today: int = 0

    # Weekly counters
    visits_in_this_week: int = 0
    pending_visited_credit: float = 0.0

    # Exchange state
    exchange_days_left: int = 0

    # Statistics
    exchange_count: int = 0
    gifts_given: int = 0
    gifts_received: int = 0
    clues_deleted: int = 0
    clues_blocked: int = 0

    @property
    def all_clues(self) -> np.ndarray:
        return self.self_clues + self.recv_clues

    @property
    def self_total(self) -> int:
        return int(self.self_clues.sum())

    @property
    def has_complete_set(self) -> bool:
        return bool(np.all(self.all_clues >= 1))

    @property
    def exchange_active(self) -> bool:
        return self.exchange_days_left > 0

    def earn(self, amount: float):
        self.wallet += amount

    def apply_daily_cap(self, shop_capacity: int):
        spent = min(self.wallet, shop_capacity)
        self.wallet -= spent
        self.total_spent += spent
        wasted = max(0.0, self.wallet - DAILY_WALLET_CAP)
        self.wallet = min(self.wallet, float(DAILY_WALLET_CAP))
        self.total_wasted += wasted


# ============================================================
# SIMULATOR
# ============================================================

class Simulator:
    def __init__(
        self,
        strategies: List[Strategy],
        clue_probs: np.ndarray = UNIFORM_PROBS,
        shop_capacity: int = 600,
        n_days: int = 365,
        seed: Optional[int] = 42,
        daily_visits: int = 2,          # Actual visits per day (B3: 1/2/3)
    ):
        self.n = len(strategies)
        self.clue_probs = clue_probs.copy()
        self.shop_capacity = shop_capacity
        self.n_days = n_days
        self.daily_visits = daily_visits
        self.rng = np.random.default_rng(seed)

        self.players = [
            Player(pid=i, strategy=strategies[i], clue_probs=clue_probs.copy())
            for i in range(self.n)
        ]

        self.daily_log: List[Dict] = []

    def run(self) -> Dict:
        for day in range(self.n_days):
            self._step(day)
        return self._results()

    # ----------------------------------------------------------
    def _step(self, day: int):

        # --- Weekly bookkeeping ---
        if day % 7 == 0 and day > 0:
            for p in self.players:
                p.earn(p.pending_visited_credit)
                p.pending_visited_credit = 0.0
                p.visits_in_this_week = 0

        # --- Advance exchange timers ---
        for p in self.players:
            if p.exchange_active:
                p.exchange_days_left -= 1
                if p.exchange_days_left == 0:
                    p.earn(EXCHANGE_CREDIT)
                    p.exchange_count += 1

        # --- Generate clues ---
        for p in self.players:
            n_new = int(self.rng.poisson(CLUES_PER_DAY))
            types = self.rng.choice(N_TYPES, size=n_new, p=self.clue_probs)
            for t in types:
                self._on_clue(p, int(t))

        # --- Selfish players: delete duplicates when near cap ---
        # Modeled as: once per day, delete all duplicates down to SELF_CLUES_TARGET
        for p in self.players:
            if p.strategy == Strategy.SELFISH:
                self._delete_duplicates(p)

        # --- Trigger exchange if ready ---
        for p in self.players:
            if not p.exchange_active and p.has_complete_set:
                self._start_exchange(p)

        # --- Outgoing visits ---
        for p in self.players:
            self._do_visits(p)

        # --- End-of-day reset ---
        for p in self.players:
            p.apply_daily_cap(self.shop_capacity)
            p.recv_count_today = 0
            p.visits_out_today = 0

        # --- Log ---
        for p in self.players:
            self.daily_log.append({
                'day': day,
                'pid': p.pid,
                'strategy': p.strategy.value,
                'total_spent': round(p.total_spent, 2),
                'exchange_count': p.exchange_count,
                'gifts_given': p.gifts_given,
                'clues_deleted': p.clues_deleted,
                'self_clues_total': p.self_total,
            })

    # ----------------------------------------------------------
    def _on_clue(self, p: Player, clue_type: int):
        """Handle a newly generated clue."""
        if p.self_total >= MAX_SELF_CLUES:
            p.clues_blocked += 1
            return

        p.self_clues[clue_type] += 1

        if p.strategy == Strategy.ALTRUISTIC:
            self._gift(p, clue_type)

        elif p.strategy == Strategy.SELFISH:
            pass  # keep; may delete later in _delete_duplicates

        elif p.strategy == Strategy.OPTIMAL:
            if p.all_clues[clue_type] >= 2:
                self._gift(p, clue_type)

        elif p.strategy == Strategy.THRESHOLD_8:
            if p.all_clues[clue_type] >= 2 and p.self_total >= 8:
                self._gift(p, clue_type)

    def _delete_duplicates(self, p: Player):
        """
        Selfish player deletes self-clue duplicates to free cap space.
        Keeps exactly 1 of each type; deletes extras. Gets +5 per deleted clue.
        Only runs when near cap (self_total >= SELF_CLUES_TARGET).
        """
        if p.self_total < SELF_CLUES_TARGET:
            return
        for t in range(N_TYPES):
            # Keep at most 1 self-clue of each type (the one needed for exchange)
            extras = p.self_clues[t] - 1
            if extras > 0:
                p.self_clues[t] -= extras
                p.earn(extras * DELETE_CREDIT)
                p.clues_deleted += extras

    def _gift(self, giver: Player, clue_type: int):
        """Gift one self-clue of clue_type to a random friend."""
        others = [q for q in self.players if q.pid != giver.pid]
        if not others:
            return
        target = self.rng.choice(others)

        giver.self_clues[clue_type] -= 1
        giver.gifts_given += 1
        giver.earn(GIFT_CREDIT_GIVER)

        target.recv_clues[clue_type] += 1
        target.gifts_received += 1
        if target.recv_count_today < len(GIFT_RECV_CREDITS):
            target.earn(GIFT_RECV_CREDITS[target.recv_count_today])
        target.recv_count_today += 1

    def _start_exchange(self, p: Player):
        """Consume 1 of each type and start exchange."""
        for t in range(N_TYPES):
            if p.self_clues[t] > 0:
                p.self_clues[t] -= 1
            else:
                p.recv_clues[t] -= 1
        p.exchange_days_left = EXCHANGE_DURATION_DAYS

    def _do_visits(self, p: Player):
        """Player visits up to daily_visits friends' active exchanges."""
        candidates = [
            q for q in self.players
            if q.pid != p.pid
            and q.exchange_active
            and q.visits_in_this_week < MAX_VISITS_IN_PER_WEEK
        ]
        self.rng.shuffle(candidates)

        visited_pids = set()
        for target in candidates:
            if p.visits_out_today >= self.daily_visits:
                break
            if target.pid in visited_pids:
                continue

            p.earn(VISIT_CREDIT)
            p.visits_out_today += 1
            visited_pids.add(target.pid)

            target.pending_visited_credit += VISITED_CREDIT
            target.visits_in_this_week += 1

    # ----------------------------------------------------------
    def _results(self) -> Dict:
        results = {}
        for p in self.players:
            results[p.pid] = {
                'strategy': p.strategy.value,
                'credits_per_day': round(p.total_spent / self.n_days, 2),
                'total_wasted': round(p.total_wasted, 1),
                'exchange_rate_per_day': round(p.exchange_count / self.n_days, 4),
                'gifts_given': p.gifts_given,
                'gifts_received': p.gifts_received,
                'clues_deleted': p.clues_deleted,   # selfish: deleted duplicates
                'clues_blocked': p.clues_blocked,
            }
        # --- NOTE: _results_player helper below is unused, kept for reference ---
        results['_group'] = {
            'credits_per_day': sum(
                v['credits_per_day'] for k, v in results.items() if k != '_group'
            ),
        }
        return results

    def _results_player(self, p: Player) -> Dict:
        return {
            'strategy': p.strategy.value,
            'credits_per_day': round(p.total_spent / self.n_days, 2),
            'total_wasted': round(p.total_wasted, 1),
            'exchange_rate_per_day': round(p.exchange_count / self.n_days, 4),
            'gifts_given': p.gifts_given,
            'gifts_received': p.gifts_received,
            'clues_deleted': p.clues_deleted,
            'clues_blocked': p.clues_blocked,
        }
