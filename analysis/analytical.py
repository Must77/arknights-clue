"""
Analytical calculations for the Arknights clue gifting model.
Covers: coupon collector, individual strategy analysis, social optimum estimates.
"""

import math
import numpy as np
from fractions import Fraction
from itertools import product


# ============================================================
# COUPON COLLECTOR
# ============================================================

def expected_draws_uniform(k: int) -> float:
    """E[draws to collect all k types under uniform distribution] = k * H_k"""
    H_k = sum(Fraction(1, i) for i in range(1, k + 1))
    return float(k * H_k)


def expected_draws_nonuniform(probs: list, n_samples: int = 200_000, seed: int = 0) -> float:
    """
    E[draws to collect all types] under non-uniform distribution.
    Uses Monte Carlo since no closed-form is tractable for general distributions.
    """
    rng = np.random.default_rng(seed)
    probs = np.array(probs)
    k = len(probs)
    totals = []
    for _ in range(n_samples):
        seen = set()
        draws = 0
        while len(seen) < k:
            t = rng.choice(k, p=probs)
            seen.add(t)
            draws += 1
        totals.append(draws)
    return float(np.mean(totals))


def expected_duplicates(k: int) -> float:
    """E[duplicate clues per cycle] = E[total draws] - k"""
    return expected_draws_uniform(k) - k


def cycle_length_days(clues_per_day: float = 1.2, k: int = 7) -> float:
    return expected_draws_uniform(k) / clues_per_day


# ============================================================
# INDIVIDUAL STRATEGY ANALYSIS
# ============================================================

def credits_per_day_selfish(k: int = 7, clues_per_day: float = 1.2,
                             exchange_credit: int = 210) -> float:
    """
    Strategy s=1 (never gift, solo).
    Only income: exchange credits.
    Warning: at cap=10 with 7 types + duplicates, generation stalls unless exchange triggered.
    Under selfish, duplicates pile up. Generation stalls if cap reached before exchange.
    """
    # Worst case: generation stalls at cap.
    # Expected clues before cap hit depends on cycle: ~18.15 clues needed, cap=10.
    # Player would need 10 clues before stalling; but exchange requires all 7 types.
    # Probability of having all 7 types in first 10 draws:
    # This is the coupon collector with cap — complex.
    # For simplicity: if player triggers exchange as soon as possible (has all 7 in first 10),
    # they're fine. Otherwise they stall.
    # Approximation: assume player gets lucky enough to complete set before cap.
    T = cycle_length_days(clues_per_day, k)
    return exchange_credit / T


def credits_per_day_optimal(k: int = 7, clues_per_day: float = 1.2,
                             exchange_credit: int = 210,
                             gift_credit: int = 20) -> float:
    """
    Strategy S* (gift all duplicates, solo — no friends).
    Income: exchange credits + gifting credits for duplicates.
    """
    T = cycle_length_days(clues_per_day, k)
    n_dup = expected_duplicates(k)
    exchange_per_day = exchange_credit / T
    gifting_per_day = n_dup * gift_credit / T
    return exchange_per_day + gifting_per_day


def cost_of_gifting_unique(k: int = 7, clues_per_day: float = 1.2,
                            exchange_credit: int = 210,
                            probs: list = None) -> dict:
    """
    Estimate the cost (in credits) of gifting away a unique clue (type you have only 1 of).
    Under uniform distribution: expected additional draws needed = k (geometric, p=1/k).
    """
    if probs is None:
        probs = [1.0 / k] * k

    T = cycle_length_days(clues_per_day, k)
    exchange_rate = exchange_credit / T  # credits/day from exchange

    results = {}
    for type_idx, p in enumerate(probs):
        # Expected additional draws to re-collect type t
        expected_extra_draws = 1.0 / p
        # Expected extra days
        extra_days = expected_extra_draws / clues_per_day
        # Expected credit cost from delayed exchange
        delay_cost = extra_days * exchange_rate
        net = 20 - delay_cost  # net benefit of gifting unique clue
        results[type_idx] = {
            'p': p,
            'expected_extra_draws': round(expected_extra_draws, 2),
            'extra_days': round(extra_days, 2),
            'delay_cost_credits': round(delay_cost, 2),
            'net_gift_benefit': round(net, 2),
            'worth_gifting': net > 0,
        }
    return results


def social_benefit_of_gifting_unique(receiver_missing: int,
                                     k: int = 7, clues_per_day: float = 1.2,
                                     exchange_credit: int = 210) -> dict:
    """
    Social benefit when giver donates a unique clue to a receiver missing `m` types.
    Assumption: the gifted type is one of the missing types.
    """
    T = cycle_length_days(clues_per_day, k)
    exchange_rate = exchange_credit / T  # credits/day from exchange

    # Expected draws to collect 1 specific type given m types missing,
    # under uniform distribution: E[draws for that type] = k / 1 (geometric with p=1/k)
    # But receiver has m types missing; each draw hits any of them with prob m/k
    # Expected draws to collect all m: sum_{j=1}^{m} k/j = k * H_m
    # By gifting the target type, receiver saves k/m draws (the contribution of that type)
    # = (1/m) * k draws saved
    saved_draws = k / receiver_missing  # under uniform
    saved_days = saved_draws / clues_per_day
    receiver_benefit = saved_days * exchange_rate

    # Giver's cost (same as cost_of_gifting_unique for uniform)
    giver_cost_draws = k  # expected extra draws to recollect
    giver_cost_days = giver_cost_draws / clues_per_day
    giver_cost_credits = giver_cost_days * exchange_rate

    social_net = receiver_benefit - giver_cost_credits + 20  # giver still gets +20
    return {
        'receiver_missing_m': receiver_missing,
        'receiver_benefit_credits': round(receiver_benefit, 2),
        'giver_cost_credits': round(giver_cost_credits, 2),
        'giver_gets_20_from_gift': 20,
        'social_net': round(social_net, 2),
        'socially_beneficial': social_net > 0,
    }


# ============================================================
# PRINT SUMMARY
# ============================================================

def print_analytical_summary():
    print("=" * 60)
    print("ANALYTICAL RESULTS — ARKNIGHTS CLUE GIFTING MODEL")
    print("=" * 60)

    # 1. Coupon collector
    E_uniform = expected_draws_uniform(7)
    E_nonuniform = expected_draws_nonuniform(NONUNIFORM_PROBS := [0.1]*6 + [0.4])
    T_uniform = E_uniform / 1.2
    T_nonuniform = E_nonuniform / 1.2

    print("\n--- Coupon Collector ---")
    print(f"Uniform (1/7 each):    E[draws] = {E_uniform:.4f}, E[cycle] = {T_uniform:.2f} days")
    print(f"Nonuniform (p7=0.4):   E[draws] = {E_nonuniform:.4f}, E[cycle] = {T_nonuniform:.2f} days")
    print(f"Uniform duplicates/cycle: {E_uniform - 7:.4f}")
    print(f"Nonuniform duplicates/cycle: {E_nonuniform - 7:.4f}")

    # 2. Strategy comparison (solo, uniform)
    solo_selfish = credits_per_day_selfish()
    solo_optimal = credits_per_day_optimal()
    print("\n--- Solo Player, Uniform Distribution ---")
    print(f"Selfish (s=1): {solo_selfish:.2f} credits/day  (exchange only)")
    print(f"Optimal (S*):  {solo_optimal:.2f} credits/day  (exchange + gifting duplicates)")
    print(f"Gain from S* over s=1: {solo_optimal - solo_selfish:.2f} credits/day")

    # 3. Cost of gifting unique clues (uniform)
    print("\n--- Cost of Gifting a Unique Clue (Uniform, Solo) ---")
    costs = cost_of_gifting_unique()
    # All types identical under uniform, show type 0
    c = costs[0]
    print(f"  Expected extra draws needed: {c['expected_extra_draws']}")
    print(f"  Expected extra days:         {c['extra_days']:.2f}")
    print(f"  Delay cost in credits:       {c['delay_cost_credits']:.2f}")
    print(f"  Gift reward:                 +20")
    print(f"  Net benefit of gifting:      {c['net_gift_benefit']:.2f}  (negative = bad)")
    print(f"  Worth gifting unique?        {c['worth_gifting']}")

    # 4. Social benefit of gifting unique clue
    print("\n--- Social Benefit of Gifting Unique Clue to Receiver Missing m Types ---")
    print(f"  {'m':>4} | {'Receiver benefit':>18} | {'Giver cost':>12} | {'Social net':>12} | {'Worth it?':>10}")
    print(f"  {'-'*4}-+-{'-'*18}-+-{'-'*12}-+-{'-'*12}-+-{'-'*10}")
    for m in range(1, 8):
        r = social_benefit_of_gifting_unique(m)
        print(f"  {m:>4} | {r['receiver_benefit_credits']:>18.2f} | "
              f"{r['giver_cost_credits']:>12.2f} | {r['social_net']:>12.2f} | "
              f"{'YES' if r['socially_beneficial'] else 'no':>10}")

    print("\n--- Key Result ---")
    print("  Gifting a unique clue is ONLY socially beneficial when receiver is missing m=1 type.")
    print("  For m>=2, social cost > social benefit.")
    print("  Therefore: S* (gift all duplicates, keep uniques) ≈ both NE and social optimum.")

    # 5. Visit credit analysis
    print("\n--- Visit Credits (Independent of Gifting Strategy) ---")
    print(f"  Max outgoing visits/day: 10 × 30 = 300 credits/day")
    print(f"  Max incoming visits/week: 10 × 30 = 300 credits/week ≈ 42.9 credits/day")
    print(f"  (Incoming is independent of exchange frequency due to weekly cap)")
    print(f"  Outgoing depends on how many friends have active exchanges.")


if __name__ == '__main__':
    NONUNIFORM_PROBS = [0.1] * 6 + [0.4]
    print_analytical_summary()
