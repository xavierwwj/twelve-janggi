"""Calibrate the stochastic difficulty levels via self-play.

For every move the tuned agent makes, choose_move reports its regret: how far
the move it played scored below the best move it saw (in evaluation units;
man = 10, minister = 30, general = 34). We bucket regrets into man-sized and
minister/general-sized mistakes and report how often each happens, as
"once every N turns".

    python3 tune.py --depth 2 --mean 30 --std 15 --games 30
"""

import argparse
import time

import negamax
import twelve_janggi as engine

MAN_CLASS = 8        # regret >= this counts as at least a man-sized mistake
MINISTER_CLASS = 25  # regret >= this counts as a minister/general-sized blunder


def run(depth, mean, std, games, time_ms, max_plies):
    regrets = []
    plies_total = 0
    t0 = time.time()
    for g in range(games):
        st = engine.initial_state(g % 2)
        plies = 0
        while st['winner'] is None and plies < max_plies:
            stats = {}
            mv = negamax.choose_move(engine, st, max_depth=depth, time_ms=time_ms,
                                     margin_mean=mean, margin_std=std, stats=stats)
            engine.apply_move(st, mv)
            if 'regret' in stats:
                regrets.append(stats['regret'])
            plies += 1
        plies_total += plies
    n = len(regrets)
    man = sum(MAN_CLASS <= r < MINISTER_CLASS for r in regrets)
    minister = sum(r >= MINISTER_CLASS for r in regrets)
    every = lambda k: f'1 in {n / k:.1f}' if k else 'never'
    print(f'depth={depth} mean={mean} std={std}: {games} games, {n} moves, '
          f'avg {plies_total / games:.0f} plies, {time.time() - t0:.0f}s')
    print(f'  man-sized mistakes      (regret {MAN_CLASS}..{MINISTER_CLASS}): '
          f'{man:4d}  ({100 * man / n:.1f}%, {every(man)} turns)')
    print(f'  minister-sized blunders (regret >= {MINISTER_CLASS}):   '
          f'{minister:4d}  ({100 * minister / n:.1f}%, {every(minister)} turns)')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--depth', type=int, required=True)
    ap.add_argument('--mean', type=float, required=True)
    ap.add_argument('--std', type=float, required=True)
    ap.add_argument('--games', type=int, default=30)
    ap.add_argument('--time-ms', type=int, default=10_000)
    ap.add_argument('--max-plies', type=int, default=120)
    args = ap.parse_args()
    run(args.depth, args.mean, args.std, args.games, args.time_ms, args.max_plies)


if __name__ == '__main__':
    main()
