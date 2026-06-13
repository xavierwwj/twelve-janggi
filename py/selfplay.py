"""Pit two agents against each other — the seed of an RL training loop.

Everything here goes through the generic engine API, so pointing it at a new
game means changing one import. Example:

    python3 selfplay.py --games 20 --p0 easy --p1 normal
"""

import argparse
import time

import negamax
import twelve_janggi as engine

LEVELS = {
    # mirrors the presets in index.html
    'easy':   dict(max_depth=2,  time_ms=300,  random_margin=14),
    'normal': dict(max_depth=5,  time_ms=800,  random_margin=6),
    'hard':   dict(max_depth=12, time_ms=2000),
    # fast variants for batch experiments
    'blitz':  dict(max_depth=4,  time_ms=80),
    'random': dict(max_depth=1,  time_ms=50, random_margin=10_000),
}


def play_game(p0_opts, p1_opts, first=0, max_plies=300):
    """Returns (winner, reason, plies); winner None means hit the ply cap."""
    st = engine.initial_state(first)
    plies = 0
    while st['winner'] is None and plies < max_plies:
        opts = p0_opts if st['turn'] == 0 else p1_opts
        mv = negamax.choose_move(engine, st, **opts)
        engine.apply_move(st, mv)
        plies += 1
    return st['winner'], st['reason'], plies


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--games', type=int, default=10)
    ap.add_argument('--p0', choices=LEVELS, default='blitz', help='agent for player 0 (Green)')
    ap.add_argument('--p1', choices=LEVELS, default='blitz', help='agent for player 1 (Red)')
    ap.add_argument('--max-plies', type=int, default=300)
    args = ap.parse_args()

    wins = {0: 0, 1: 0, None: 0}
    t0 = time.time()
    for g in range(args.games):
        first = g % 2  # alternate who moves first
        winner, reason, plies = play_game(LEVELS[args.p0], LEVELS[args.p1],
                                          first=first, max_plies=args.max_plies)
        wins[winner] += 1
        tag = {0: 'p0', 1: 'p1', None: 'cap'}[winner]
        print(f'game {g + 1:3d}: first=p{first} -> {tag:3s} ({reason}, {plies} plies)')
    dt = time.time() - t0
    print(f'\np0 ({args.p0}): {wins[0]}  |  p1 ({args.p1}): {wins[1]}  |  '
          f'ply-capped: {wins[None]}  |  {dt:.1f}s')


if __name__ == '__main__':
    main()
