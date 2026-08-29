"""Calibrate the stochastic difficulty levels via self-play.

For every move the tuned agent makes, choose_move reports its regret: how far
the move it played scored below the best move it saw (in the game's own
evaluation units). We bucket regrets into small mistakes and piece-sized
blunders and report how often each happens, as "once every N turns".

    python3 tune.py --depth 2 --mean 30 --std 15 --games 30
    python3 tune.py --game card-chess --depth 2 --mean 150 --std 60
"""

import argparse
import random
import time

import negamax
from card_chess import CardChess
from twelve_janggi import TwelveJanggi

# per game: engine + regret thresholds on its evaluation scale
# twelve-janggi: man = 10, minister = 30, general = 34
# card-chess:    every piece = ~100 (plus small positional terms)
GAMES = {
    'twelve-janggi': dict(engine=TwelveJanggi, small=8, big=25,
                          small_label='man-sized mistakes',
                          big_label='minister-sized blunders'),
    'card-chess':    dict(engine=CardChess, small=20, big=80,
                          small_label='positional mistakes',
                          big_label='piece-sized blunders'),
}


def run(game, depth, mean, std, games, time_ms, max_plies):
    cfg = GAMES[game]
    engine = cfg['engine']()
    small, big = cfg['small'], cfg['big']
    regrets = []
    plies_total = 0
    t0 = time.time()
    for g in range(games):
        if hasattr(engine, 'all_drafts'):
            st = engine.initial_state(0, random.choice(engine.all_drafts(1)))
        else:
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
    n_small = sum(small <= r < big for r in regrets)
    n_big = sum(r >= big for r in regrets)
    every = lambda k: f'1 in {n / k:.1f}' if k else 'never'
    print(f'{game} depth={depth} mean={mean} std={std}: {games} games, {n} moves, '
          f'avg {plies_total / games:.0f} plies, {time.time() - t0:.0f}s')
    print(f'  {cfg["small_label"]:24s} (regret {small}..{big}): '
          f'{n_small:4d}  ({100 * n_small / n:.1f}%, {every(n_small)} turns)')
    print(f'  {cfg["big_label"]:24s} (regret >= {big}):   '
          f'{n_big:4d}  ({100 * n_big / n:.1f}%, {every(n_big)} turns)')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--game', choices=GAMES, default='twelve-janggi')
    ap.add_argument('--depth', type=int, required=True)
    ap.add_argument('--mean', type=float, required=True)
    ap.add_argument('--std', type=float, required=True)
    ap.add_argument('--games', type=int, default=30)
    ap.add_argument('--time-ms', type=int, default=10_000)
    ap.add_argument('--max-plies', type=int, default=120)
    args = ap.parse_args()
    run(args.game, args.depth, args.mean, args.std, args.games,
        args.time_ms, args.max_plies)


if __name__ == '__main__':
    main()
