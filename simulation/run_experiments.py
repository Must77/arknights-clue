"""
Experiment runner for Arknights Clue Gifting Study (v5).

Changes from v4:
  - Visit model: U-shaped Beta-Binomial (α=β=0.3) replaces fixed daily_visits=2
    Players either visit all available friends or none; rarely partial visits.
    MAX_VISITS_OUT_PER_DAY=10 enforces game cap.

Experiments:
  E1: Solo baseline — all strategies, uniform vs nonuniform
  E2: Group size effect — N in {1,2,5,10,20,50}, all using S*, uniform
  E3: Homogeneous strategy comparison — all N players use same strategy (N=10)
  E4: Mixed strategies — what happens when one defects from S*?
  E5: Shop capacity sensitivity — S=300,400,600,800,∞
  E6: Distribution effect — uniform vs corrected nonuniform (p7=16/70)
  E7: Lambda sensitivity — compare λ ≈ 2.2 (no bonus) vs 3.0 (typical) vs 3.3 (high)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import json
from collections import defaultdict
from simulate import (
    Simulator, Strategy,
    UNIFORM_PROBS, NONUNIFORM_PROBS,
    N_TYPES, DEFAULT_OPERATOR_BONUS, AMBIANCE_BONUS, CLUE_BASE_HOURS,
    VISIT_ALPHA, VISIT_BETA,
)

N_RUNS = 30       # Monte Carlo runs per config
N_DAYS = 365      # simulation length
WARMUP = 30       # days to discard (transient)


def run_config(strategies, clue_probs, shop_capacity, n_runs=N_RUNS, n_days=N_DAYS,
               operator_bonus=DEFAULT_OPERATOR_BONUS,
               visit_alpha=VISIT_ALPHA, visit_beta=VISIT_BETA):
    """Run multiple seeds and return averaged per-player results."""
    all_results = defaultdict(lambda: defaultdict(list))

    for seed in range(n_runs):
        sim = Simulator(
            strategies=strategies,
            clue_probs=clue_probs,
            shop_capacity=shop_capacity,
            n_days=n_days,
            seed=seed,
            operator_bonus=operator_bonus,
            visit_alpha=visit_alpha,
            visit_beta=visit_beta,
        )
        res = sim.run()
        for pid, data in res.items():
            if pid == '_group':
                continue
            for k, v in data.items():
                if isinstance(v, str):
                    continue  # skip non-numeric fields (e.g., 'strategy')
                all_results[pid][k].append(float(v))

    # Average over runs
    averaged = {}
    for pid, metrics in all_results.items():
        averaged[pid] = {k: round(float(np.mean(v)), 3) for k, v in metrics.items()}
        averaged[pid]['strategy'] = res[pid]['strategy']

    # Group totals
    averaged['_group_credits_per_day'] = round(
        sum(averaged[pid]['credits_per_day'] for pid in averaged if pid != '_group_credits_per_day'),
        3
    )
    return averaged


def print_results(label, results, show_pids=False):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    for pid, data in sorted(results.items()):
        if pid == '_group_credits_per_day':
            continue
        strat = data.get('strategy', '?')
        cpd = data.get('credits_per_day', 0)
        exc = data.get('exchange_rate_per_day', 0)
        gg = data.get('gifts_given', 0)
        gr = data.get('gifts_received', 0)
        queued = data.get('queue_remaining', 0)
        pid_str = f"P{pid}" if show_pids else strat
        print(f"  [{pid_str:20s}] {cpd:7.2f} cr/day | "
              f"exch/day={exc:.4f} | gifts_out={gg:.1f} | gifts_in={gr:.1f} | queue={queued:.1f}")

    group_cpd = results.get('_group_credits_per_day', 0)
    print(f"  {'GROUP TOTAL':21s} {group_cpd:7.2f} cr/day")


# ============================================================
# E1: Solo baseline
# ============================================================

def experiment_e1():
    print("\n" + "=" * 60)
    print("E1: SOLO BASELINE (N=1, no friends)")
    print("    — comparing all strategies in isolation")
    print("=" * 60)

    for dist_name, probs in [("Uniform", UNIFORM_PROBS),
                              ("Nonuniform (p7=16/70)", NONUNIFORM_PROBS)]:
        print(f"\n  Distribution: {dist_name}")
        print(f"  {'Strategy':20s} {'cr/day':>8} {'exch/day':>10} {'gifts_out':>10} {'queue':>8}")
        print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")
        for strat in Strategy:
            res = run_config([strat], probs, shop_capacity=9999, n_days=N_DAYS)
            d = res[0]
            print(f"  {d['strategy']:20s} {d['credits_per_day']:>8.2f} "
                  f"{d['exchange_rate_per_day']:>10.4f} "
                  f"{d['gifts_given']:>10.1f} "
                  f"{d['queue_remaining']:>8.1f}")


# ============================================================
# E2: Group size effect (all using S*)
# ============================================================

def experiment_e2():
    print("\n" + "=" * 60)
    print("E2: GROUP SIZE EFFECT (all players use S*, uniform, shop=∞)")
    print("=" * 60)
    print(f"  {'N':>4} {'cr/day (per player)':>22} {'group cr/day':>15} {'exch/day':>10} {'gifts_in':>10} {'expired':>10}")
    print(f"  {'-'*4} {'-'*22} {'-'*15} {'-'*10} {'-'*10} {'-'*10}")

    for N in [1, 2, 5, 10, 20, 50]:
        strats = [Strategy.OPTIMAL] * N
        res = run_config(strats, UNIFORM_PROBS, shop_capacity=9999, n_days=N_DAYS)
        per_player = res[0]['credits_per_day']
        group_total = res['_group_credits_per_day']
        exc = res[0]['exchange_rate_per_day']
        gr = res[0]['gifts_received']
        exp = res[0].get('recv_expired', 0)
        print(f"  {N:>4} {per_player:>22.2f} {group_total:>15.2f} {exc:>10.4f} {gr:>10.1f} {exp:>10.1f}")


# ============================================================
# E3: Homogeneous strategy comparison (N=10)
# ============================================================

def experiment_e3():
    print("\n" + "=" * 60)
    print("E3: HOMOGENEOUS STRATEGIES (N=10, uniform, shop=∞)")
    print("=" * 60)
    print(f"  {'Strategy':20s} {'cr/day/player':>15} {'group cr/day':>15} {'exch/day':>10} {'expired/yr':>11}")
    print(f"  {'-'*20} {'-'*15} {'-'*15} {'-'*10} {'-'*11}")

    N = 10
    for strat in Strategy:
        strats = [strat] * N
        res = run_config(strats, UNIFORM_PROBS, shop_capacity=9999, n_days=N_DAYS)
        group = res['_group_credits_per_day']
        cpd = round(group / N, 2)
        exc = round(sum(res[pid].get('exchange_rate_per_day', 0) for pid in range(N)) / N, 4)
        exp = round(sum(res[pid].get('recv_expired', 0) for pid in range(N)) / N, 1)
        print(f"  {strat.value:20s} {cpd:>15.2f} {group:>15.2f} {exc:>10.4f} {exp:>11.1f}")


# ============================================================
# E4: Mixed strategies — one defects from S*
# ============================================================

def experiment_e4():
    print("\n" + "=" * 60)
    print("E4: MIXED STRATEGIES — 1 deviant in a group of 10 using S* (uniform, shop=∞)")
    print("    Shows incentive to deviate from S*")
    print("=" * 60)

    N = 10
    baseline = [Strategy.OPTIMAL] * N

    # Baseline
    res_base = run_config(baseline, UNIFORM_PROBS, shop_capacity=9999, n_days=N_DAYS)
    cpd_base = res_base[0]['credits_per_day']
    group_base = res_base['_group_credits_per_day']
    print(f"\n  Baseline (all S*): player={cpd_base:.2f} cr/day, group={group_base:.2f} cr/day")

    print(f"\n  {'Deviant strategy':20s} {'deviant cr/day':>16} {'others cr/day':>15} "
          f"{'group cr/day':>14} {'deviant gain':>13}")
    print(f"  {'-'*20} {'-'*16} {'-'*15} {'-'*14} {'-'*13}")

    for deviant_strat in Strategy:
        strats = [deviant_strat] + [Strategy.OPTIMAL] * (N - 1)
        res = run_config(strats, UNIFORM_PROBS, shop_capacity=9999, n_days=N_DAYS)
        deviant_cpd = res[0]['credits_per_day']
        others_cpd = res[1]['credits_per_day']  # any non-deviant
        group = res['_group_credits_per_day']
        gain = deviant_cpd - cpd_base
        print(f"  {deviant_strat.value:20s} {deviant_cpd:>16.2f} {others_cpd:>15.2f} "
              f"{group:>14.2f} {gain:>+13.2f}")


# ============================================================
# E5: Shop capacity sensitivity (N=10, all S*)
# ============================================================

def experiment_e5():
    print("\n" + "=" * 60)
    print("E5: SHOP CAPACITY SENSITIVITY (N=10, all S*, uniform)")
    print("=" * 60)
    print(f"  {'Shop capacity':>15} {'cr/day/player':>15} {'wasted/day':>12} {'group cr/day':>15}")
    print(f"  {'-'*15} {'-'*15} {'-'*12} {'-'*15}")

    N = 10
    strats = [Strategy.OPTIMAL] * N
    for shop_cap in [300, 400, 600, 800, 9999]:
        res = run_config(strats, UNIFORM_PROBS, shop_capacity=shop_cap, n_days=N_DAYS)
        cpd = res[0]['credits_per_day']
        wasted = round(res[0].get('total_wasted', 0) / N_DAYS, 2)
        group = res['_group_credits_per_day']
        cap_label = str(shop_cap) if shop_cap < 9999 else "∞"
        print(f"  {cap_label:>15} {cpd:>15.2f} {wasted:>12.2f} {group:>15.2f}")


# ============================================================
# E6: Nonuniform distribution effect
# ============================================================

def experiment_e6():
    print("\n" + "=" * 60)
    print("E6: DISTRIBUTION EFFECT (N=10, all S*, shop=∞)")
    print("=" * 60)
    print(f"  {'Distribution':25s} {'cr/day/player':>15} {'exch/day':>10} {'exch_cycle_days':>16}")
    print(f"  {'-'*25} {'-'*15} {'-'*10} {'-'*16}")

    N = 10
    strats = [Strategy.OPTIMAL] * N
    for dist_name, probs in [("Uniform (1/7 each)", UNIFORM_PROBS),
                              ("Nonuniform (p7=16/70)", NONUNIFORM_PROBS)]:
        res = run_config(strats, probs, shop_capacity=9999, n_days=N_DAYS)
        cpd = res[0]['credits_per_day']
        exc = res[0]['exchange_rate_per_day']
        cycle = round(1 / exc, 2) if exc > 0 else float('inf')
        print(f"  {dist_name:25s} {cpd:>15.2f} {exc:>10.4f} {cycle:>16.2f}")


# ============================================================
# E7: Lambda sensitivity (N=10, all S*, uniform)
# ============================================================

def experiment_e7():
    print("\n" + "=" * 60)
    print("E7: LAMBDA SENSITIVITY (N=10, all S*, uniform)")
    print("    operator_bonus varies; ambiance=15% fixed; lambda = 1 + 24/20*(1+bonus+0.15)")
    print("=" * 60)
    print(f"  {'Config':30s} {'op_bonus':>9} {'λ_total':>8} {'cr/day/player':>15} {'exch/day':>10}")
    print(f"  {'-'*30} {'-'*9} {'-'*8} {'-'*15} {'-'*10}")

    N = 10
    strats = [Strategy.OPTIMAL] * N
    configs = [
        ("No bonus (2×E0-4★+Lv3)",  0.04 + 0.11),   # 4% + 11% = 15%
        ("Low (2×E1-4★+Lv3)",       0.16 + 0.11),   # 16%+11%=27% (2×(8+2)%+11%)
        ("Typical (2×E2-5★+Lv3)",   0.51),            # DEFAULT_OPERATOR_BONUS
        ("High (2×E2-6★+Lv3)",      0.43 + 0.11),   # 2×(16+5)%+11%=53%
    ]
    for label, op_bonus in configs:
        lambda_op = (24 / CLUE_BASE_HOURS) * (1 + op_bonus + AMBIANCE_BONUS)
        lambda_total = 1.0 + lambda_op
        res = run_config(strats, UNIFORM_PROBS, shop_capacity=9999,
                         n_days=N_DAYS, operator_bonus=op_bonus)
        cpd = res[0]['credits_per_day']
        exc = res[0]['exchange_rate_per_day']
        print(f"  {label:30s} {op_bonus:>9.2f} {lambda_total:>8.2f} {cpd:>15.2f} {exc:>10.4f}")


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("Running Arknights Clue Gifting Experiments")
    print(f"N_RUNS={N_RUNS}, N_DAYS={N_DAYS}")

    experiment_e1()
    experiment_e2()
    experiment_e3()
    experiment_e4()
    experiment_e5()
    experiment_e6()
    experiment_e7()

    print("\n\nAll experiments complete.")
