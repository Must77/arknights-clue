"""
Arknights Clue Gifting Strategy Simulation (v5)

Changes from v4:
- Outgoing visits now use U-shaped Beta-Binomial distribution instead of
  fixed daily_visits=2, reflecting real player behavior:
    * most days either visit ALL available friends or NONE (rarely partial)
    * modeled as: visit_prob ~ Beta(α, β) with α=β=0.3 (U-shape)
                  n_visits  = min(Binomial(n_avail, visit_prob), MAX_VISITS_OUT_PER_DAY)
  Added constants: MAX_VISITS_OUT_PER_DAY=10, VISIT_ALPHA=0.3, VISIT_BETA=0.3
- Simulator parameter daily_visits removed; replaced by visit_alpha, visit_beta
- Player field visits_out_today removed (no longer needed as running counter)
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
RECV_EXPIRY_DAYS = 10        # received clues expire after 10 days
EXCHANGE_CREDIT = 210
EXCHANGE_DURATION_DAYS = 1
VISIT_CREDIT = 30
MAX_VISITS_IN_PER_WEEK = 10
MAX_VISITS_OUT_PER_DAY = 10     # game cap: at most 10 outgoing visits per day
VISITED_CREDIT = 30

# U-shaped Beta-Binomial parameters for outgoing visit behavior.
# α = β < 1 → U-shape: players mostly visit all available friends OR none at all.
# With α=β=0.3: P(visit none) ≈ 44%, P(visit all) ≈ 44%, P(partial) ≈ 12%.
# E[visits | n_avail] = n_avail × α/(α+β) = n_avail × 0.5
VISIT_ALPHA = 0.3
VISIT_BETA  = 0.3
GIFT_CREDIT_GIVER = 20
DELETE_CREDIT = 5
GIFT_RECV_CREDITS = (15, 10, 5)
DAILY_WALLET_CAP = 300
AMBIANCE_BONUS = 0.15        # fixed +15% for all players

# Clue type probability distributions
UNIFORM_PROBS = np.array([1.0 / N_TYPES] * N_TYPES)
# Type 7 is 10pp higher: solve 6p + (p+0.10) = 1 => p = 9/70, p7 = 16/70
NONUNIFORM_PROBS = np.array([9/70] * 6 + [16/70])

# Typical operator bonus (2×E2-5★ + Room Lv.3): 2×20% + 11% = 51%
DEFAULT_OPERATOR_BONUS = 0.51


# ============================================================
# STRATEGIES
# ============================================================

class Strategy(Enum):
    ALTRUISTIC       = "Altruistic"        # gift every clue except the one completing the 7-type set
    ALTRUISTIC_SAFE  = "Altruistic_Safe"   # same but also keeps clues when exactly 2 types missing
    SELFISH          = "Selfish"           # never gift; delete duplicates near cap (+5 each)
    SELFISH_TYPE7    = "Selfish_Type7"     # gift only type-7 duplicates; delete types 1-6 like Selfish
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
    recv_log: list = field(default_factory=list)   # (day_received, clue_type); sorted by day
    clue_queue: list = field(default_factory=list) # clues paused due to cap

    wallet: float = 0.0
    total_spent: float = 0.0
    total_wasted: float = 0.0

    recv_count_today: int = 0
    visits_in_this_week: int = 0
    pending_visited_credit: float = 0.0
    exchange_days_left: int = 0

    exchange_count: int = 0
    gifts_given: int = 0
    gifts_received: int = 0
    clues_deleted: int = 0
    recv_expired: int = 0    # number of received clues that expired unused

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
        visit_alpha: float = VISIT_ALPHA,
        visit_beta: float = VISIT_BETA,
        operator_bonus: float = DEFAULT_OPERATOR_BONUS,
    ):
        self.n = len(strategies)
        self.clue_probs = clue_probs.copy()
        self.shop_capacity = shop_capacity
        self.n_days = n_days
        self.visit_alpha = visit_alpha
        self.visit_beta = visit_beta
        # λ_operator = (24h / 20h) × (1 + operator_bonus + ambiance_bonus)
        self.lambda_operator = (24 / CLUE_BASE_HOURS) * (1 + operator_bonus + AMBIANCE_BONUS)
        self.rng = np.random.default_rng(seed)
        self.current_day = 0  # set at start of each _step; used by _do_gift

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
        self.current_day = day

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

        # Expire received clues (10-day limit)
        for p in self.players:
            self._expire_recv(p, day)

        # Generate new clues → queue (never discard)
        for p in self.players:
            t_daily = int(self.rng.choice(N_TYPES, p=self.clue_probs))
            p.clue_queue.append(t_daily)
            n_op = int(self.rng.poisson(self.lambda_operator))
            for t in self.rng.choice(N_TYPES, size=n_op, p=self.clue_probs):
                p.clue_queue.append(int(t))

        # Drain queue into inventory (gifting may free space for more)
        for p in self.players:
            self._drain_queue(p)

        # Selfish / Selfish_Type7: delete duplicates once per day, then drain again
        for p in self.players:
            if p.strategy in (Strategy.SELFISH, Strategy.SELFISH_TYPE7):
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
    def _expire_recv(self, p: Player, current_day: int):
        """Remove received clues older than RECV_EXPIRY_DAYS."""
        new_log = []
        for (d, t) in p.recv_log:
            if current_day - d >= RECV_EXPIRY_DAYS:
                p.recv_clues[t] = max(0, p.recv_clues[t] - 1)
                p.recv_expired += 1
            else:
                new_log.append((d, t))
        p.recv_log = new_log

    def _drain_queue(self, p: Player):
        """Move queued clues into inventory one by one."""
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
            # Gift everything EXCEPT the single clue that completes the 7-type set.
            # Keep only if: only copy of this type AND it gives a complete set.
            completing = (p.all_clues[clue_type] == 1 and p.has_complete_set)
            if not completing:
                self._gift_random(p, clue_type)

        elif p.strategy == Strategy.ALTRUISTIC_SAFE:
            # Gift everything EXCEPT clues belonging to the last 1-2 missing types.
            # n_missing is computed after adding this clue to self_clues.
            # Keep if: only copy of this type (was missing) AND ≤1 type still missing
            # (meaning this clue was one of the 2 needed to complete the set).
            n_missing = int(np.sum(p.all_clues == 0))
            keep = (p.all_clues[clue_type] == 1) and (n_missing <= 1)
            if not keep:
                self._gift_random(p, clue_type)

        elif p.strategy == Strategy.SELFISH:
            pass  # deletion handled separately

        elif p.strategy == Strategy.SELFISH_TYPE7:
            # Gift type-7 duplicates only (index 6); types 0-5 kept and deleted like Selfish.
            if clue_type == N_TYPES - 1 and p.all_clues[clue_type] >= 2:
                self._gift_random(p, clue_type)
            # types 0-5: deletion handled separately (same threshold as Selfish)

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
        """Gift to a friend missing this type (all_clues == 0); fall back to random."""
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
        target.recv_log.append((self.current_day, clue_type))
        target.gifts_received += 1
        if target.recv_count_today < len(GIFT_RECV_CREDITS):
            target.earn(GIFT_RECV_CREDITS[target.recv_count_today])
        target.recv_count_today += 1

    def _start_exchange(self, p: Player):
        """Consume 1 of each type (self_clues first, then recv_clues)."""
        for t in range(N_TYPES):
            if p.self_clues[t] > 0:
                p.self_clues[t] -= 1
            else:
                p.recv_clues[t] -= 1
                # Remove the oldest recv_log entry of this type
                for i, (d, rt) in enumerate(p.recv_log):
                    if rt == t:
                        p.recv_log.pop(i)
                        break
        p.exchange_days_left = EXCHANGE_DURATION_DAYS

    def _do_visits(self, p: Player):
        candidates = [
            q for q in self.players
            if q.pid != p.pid
            and q.exchange_active
            and q.visits_in_this_week < MAX_VISITS_IN_PER_WEEK
        ]
        if not candidates:
            return
        n_avail = len(candidates)
        # U-shaped Beta-Binomial: visit all or none on most days, rarely partial.
        # visit_prob ~ Beta(α, β), n_visits ~ Binomial(n_avail, visit_prob)
        visit_prob = float(self.rng.beta(self.visit_alpha, self.visit_beta))
        n_visits = min(int(self.rng.binomial(n_avail, visit_prob)), MAX_VISITS_OUT_PER_DAY)
        self.rng.shuffle(candidates)
        for target in candidates[:n_visits]:
            p.earn(VISIT_CREDIT)
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
                'recv_expired': p.recv_expired,
                'queue_remaining': len(p.clue_queue),
            }
        results['_group'] = {
            'credits_per_day': sum(
                v['credits_per_day'] for k, v in results.items() if k != '_group'
            ),
        }
        return results
