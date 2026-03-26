"""
Arknights Clue Gifting Strategy Simulation (v3)

Changes from v2:
- Two-source clue generation: daily 4AM (1/day fixed) + operator Poisson
- NONUNIFORM_PROBS corrected: type 7 is +10pp higher (9/70 vs 16/70)
- Blocking mechanic fixed: clues queue up, never discarded
- OPTIMAL_TARGETED strategy: gift to friend who specifically needs the type
- operator_bonus parameter (additive, excludes fixed ambiance +15%)
- Ambiance bonus treated as constant +15% for all strategies
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

# ============================================================
# GAME CONSTANTS
# ============================================================

N_TYPES = 7
CLUES_DAILY = 1              # fixed 4AM clue per day
CLUE_BASE_HOURS = 20         # operator base generation time (no bonus)
MAX_SELF_CLUES = 10
SELF_CLUES_DELETE_TARGET = 8 # selfish: delete duplicates down to this level
EXCHANGE_CREDIT = 210
EXCHANGE_DURATION_DAYS = 1
VISIT_CREDIT = 30
MAX_VISITS_IN_PER_WEEK = 10
VISITED_CREDIT = 30
GIFT_CREDIT_GIVER = 20
DELETE_CREDIT = 5
GIFT_RECV_CREDITS = (15, 10, 5)
DAILY_WALLET_CAP = 300
AMBIANCE_BONUS = 0.15        # fixed +15% for all players, does not vary by strategy

# Clue type probability distributions
UNIFORM_PROBS = np.array([1.0 / N_TYPES] * N_TYPES)
# Type 7 is 10 percentage points higher than types 1-6
# Solve: 6*p + (p+0.10) = 1  =>  p = 9/70, p7 = 16/70
NONUNIFORM_PROBS = np.array([9/70] * 6 + [16/70])

# Typical operator bonus (2×E2-5★ + Room Lv.3): 2×20% + 11% = 51%
DEFAULT_OPERATOR_BONUS = 0.51


# ============================================================
# STRATEGIES
# ============================================================

class Strategy(Enum):
    ALTRUISTIC       = "Altruistic"        # gift every self-generated clue (random target)
    SELFISH          = "Selfish"           # never gift; delete duplicates near cap (+5 each)
    OPTIMAL          = "Optimal_S*"        # gift all duplicates (random target)
    OPTIMAL_TARGETED = "Optimal_Targeted"  # gift all duplicates (to friend who needs the type)
    THRESHOLD_8      = "Threshold_8"       # gift duplicates only when self_total >= 8


# ============================================================
# PLAYER
# ============================================================

@dataclass
class Player:
    pid: int
    strategy: Strategy
    clue_probs: np.ndarray

    self_clues: np.ndarray = field(default_factory=lambda: np.zeros(N_TYPES, dtype=int))
    recv_clues: np.ndarray = field(default_factory=lambda: np.zeros(N_TYPES, dtype=int))
    clue_queue: list = field(default_factory=list)  # clues paused due to cap

    wallet: float = 0.0
    total_spent: float = 0.0
    total_wasted: float = 0.0

    recv_count_today: int = 0
    visits_out_today: int = 0
    visits_in_this_week: int = 0
    pending_visited_credit: float = 0.0
    exchange_days_left: int = 0

    exchange_count: int = 0
    gifts_given: int = 0
    gifts_received: int = 0
    clues_deleted: int = 0

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
        daily_visits: int = 2,
        operator_bonus: float = DEFAULT_OPERATOR_BONUS,
    ):
        self.n = len(strategies)
        self.clue_probs = clue_probs.copy()
        self.shop_capacity = shop_capacity
        self.n_days = n_days
        self.daily_visits = daily_visits
        # λ_operator = (24h / 20h) × (1 + operator_bonus + ambiance_bonus)
        self.lambda_operator = (24 / CLUE_BASE_HOURS) * (1 + operator_bonus + AMBIANCE_BONUS)
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
        # Weekly bookkeeping
        if day % 7 == 0 and day > 0:
            for p in self.players:
                p.earn(p.pending_visited_credit)
                p.pending_visited_credit = 0.0
                p.visits_in_this_week = 0

        # Advance exchange timers
        for p in self.players:
            if p.exchange_active:
                p.exchange_days_left -= 1
                if p.exchange_days_left == 0:
                    p.earn(EXCHANGE_CREDIT)
                    p.exchange_count += 1

        # Generate new clues → queue (never discard)
        for p in self.players:
            t_daily = int(self.rng.choice(N_TYPES, p=self.clue_probs))
            p.clue_queue.append(t_daily)
            n_op = int(self.rng.poisson(self.lambda_operator))
            for t in self.rng.choice(N_TYPES, size=n_op, p=self.clue_probs):
                p.clue_queue.append(int(t))

        # Drain queue into inventory (gifting/deletion may free space for more)
        for p in self.players:
            self._drain_queue(p)

        # Selfish: delete duplicates once per day, then drain again
        for p in self.players:
            if p.strategy == Strategy.SELFISH:
                self._delete_duplicates(p)
                self._drain_queue(p)

        # Trigger exchange if ready
        for p in self.players:
            if not p.exchange_active and p.has_complete_set:
                self._start_exchange(p)

        # Outgoing visits
        for p in self.players:
            self._do_visits(p)

        # End-of-day reset
        for p in self.players:
            p.apply_daily_cap(self.shop_capacity)
            p.recv_count_today = 0
            p.visits_out_today = 0

        # Log
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
                'queue_size': len(p.clue_queue),
            })

    # ----------------------------------------------------------
    def _drain_queue(self, p: Player):
        """Move queued clues into inventory one by one (gifting/deletion may cascade)."""
        remaining = []
        for t in p.clue_queue:
            if p.self_total < MAX_SELF_CLUES:
                p.self_clues[t] += 1
                self._on_new_clue(p, t)
            else:
                remaining.append(t)
        p.clue_queue = remaining

    def _on_new_clue(self, p: Player, clue_type: int):
        """Execute strategy action for a newly acquired clue."""
        if p.strategy == Strategy.ALTRUISTIC:
            self._gift_random(p, clue_type)

        elif p.strategy == Strategy.SELFISH:
            pass  # deletion handled separately

        elif p.strategy == Strategy.OPTIMAL:
            if p.all_clues[clue_type] >= 2:
                self._gift_random(p, clue_type)

        elif p.strategy == Strategy.OPTIMAL_TARGETED:
            if p.all_clues[clue_type] >= 2:
                self._gift_targeted(p, clue_type)

        elif p.strategy == Strategy.THRESHOLD_8:
            if p.all_clues[clue_type] >= 2 and p.self_total >= 8:
                self._gift_random(p, clue_type)

    def _delete_duplicates(self, p: Player):
        """Selfish: delete self-clue duplicates to free cap space (+5 each)."""
        if p.self_total < SELF_CLUES_DELETE_TARGET:
            return
        for t in range(N_TYPES):
            extras = int(p.self_clues[t]) - 1
            if extras > 0:
                p.self_clues[t] -= extras
                p.earn(extras * DELETE_CREDIT)
                p.clues_deleted += extras

    def _gift_random(self, giver: Player, clue_type: int):
        others = [q for q in self.players if q.pid != giver.pid]
        if not others:
            return
        target = self.rng.choice(others)
        self._do_gift(giver, target, clue_type)

    def _gift_targeted(self, giver: Player, clue_type: int):
        """Gift to a friend missing this type; fall back to random if none."""
        needy = [q for q in self.players
                 if q.pid != giver.pid and q.all_clues[clue_type] == 0]
        if needy:
            target = self.rng.choice(needy)
        else:
            others = [q for q in self.players if q.pid != giver.pid]
            if not others:
                return
            target = self.rng.choice(others)
        self._do_gift(giver, target, clue_type)

    def _do_gift(self, giver: Player, target: Player, clue_type: int):
        giver.self_clues[clue_type] -= 1
        giver.gifts_given += 1
        giver.earn(GIFT_CREDIT_GIVER)
        target.recv_clues[clue_type] += 1
        target.gifts_received += 1
        if target.recv_count_today < len(GIFT_RECV_CREDITS):
            target.earn(GIFT_RECV_CREDITS[target.recv_count_today])
        target.recv_count_today += 1

    def _start_exchange(self, p: Player):
        for t in range(N_TYPES):
            if p.self_clues[t] > 0:
                p.self_clues[t] -= 1
            else:
                p.recv_clues[t] -= 1
        p.exchange_days_left = EXCHANGE_DURATION_DAYS

    def _do_visits(self, p: Player):
        candidates = [
            q for q in self.players
            if q.pid != p.pid
            and q.exchange_active
            and q.visits_in_this_week < MAX_VISITS_IN_PER_WEEK
        ]
        self.rng.shuffle(candidates)
        visited = set()
        for target in candidates:
            if p.visits_out_today >= self.daily_visits:
                break
            if target.pid in visited:
                continue
            p.earn(VISIT_CREDIT)
            p.visits_out_today += 1
            visited.add(target.pid)
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
                'clues_deleted': p.clues_deleted,
                'queue_remaining': len(p.clue_queue),
            }
        results['_group'] = {
            'credits_per_day': sum(
                v['credits_per_day'] for k, v in results.items() if k != '_group'
            ),
        }
        return results
