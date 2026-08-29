"""Pit two agents against each other — the seed of an RL training loop.

Everything here goes through the generic engine API, so pointing it at a new
game means selecting it with --game. Examples:

    python3 selfplay.py --games 20 --p0 easy --p1 normal
    python3 selfplay.py --game card-chess --draft random --games 20
"""

import argparse
import random
import time

import negamax
from card_chess import CardChess
from twelve_janggi import TwelveJanggi

GAMES = {'twelve-janggi': TwelveJanggi, 'card-chess': CardChess}

# per game: margins live on each game's own evaluation scale
# (calibrated with tune.py)
LEVELS = {
    'twelve-janggi': {
        'easy':   dict(max_depth=2,  time_ms=300,  margin_mean=52, margin_std=21),
        'normal': dict(max_depth=5,  time_ms=800,  margin_mean=18, margin_std=8),
        'hard':   dict(max_depth=12, time_ms=2000),
        # fast variants for batch experiments
        'blitz':  dict(max_depth=4,  time_ms=80),
        'random': dict(max_depth=1,  time_ms=50, margin_mean=10_000),
    },
    'card-chess': {
        'easy':   dict(max_depth=2,  time_ms=300,  margin_mean=120, margin_std=50),
        'normal': dict(max_depth=4,  time_ms=800,  margin_mean=38,  margin_std=16),
        'hard':   dict(max_depth=8,  time_ms=2000),
        'blitz':  dict(max_depth=3,  time_ms=80),
        'random': dict(max_depth=1,  time_ms=50, margin_mean=10_000),
    },
}


def new_game(engine, first, draft_mode='default'):
    """initial_state, with a random card draft when the game has one."""
    if hasattr(engine, 'all_drafts') and draft_mode == 'random':
        return engine.initial_state(first, random.choice(engine.all_drafts(1)))
    return engine.initial_state(first)


def play_game(engine, p0_opts, p1_opts, first=0, max_plies=300, draft_mode='default'):
    """Returns (winner, reason, plies); winner None means hit the ply cap."""
    st = new_game(engine, first, draft_mode)
    plies = 0
    while st['winner'] is None and plies < max_plies:
        opts = p0_opts if st['turn'] == 0 else p1_opts
        mv = negamax.choose_move(engine, st, **opts)
        engine.apply_move(st, mv)
        plies += 1
    return st['winner'], st['reason'], plies


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--game', choices=GAMES, default='twelve-janggi')
    ap.add_argument('--games', type=int, default=10)
    ap.add_argument('--p0', default='blitz', help='agent for player 0')
    ap.add_argument('--p1', default='blitz', help='agent for player 1')
    ap.add_argument('--draft', choices=['default', 'random'], default='default',
                    help='card-chess: fixed default draft or a random one per game')
    ap.add_argument('--max-plies', type=int, default=300)
    args = ap.parse_args()

    engine = GAMES[args.game]()
    levels = LEVELS[args.game]
    # card chess: white always moves first; other games alternate the opener
    fixed_first = 0 if args.game == 'card-chess' else None

    wins = {0: 0, 1: 0, 2: 0, None: 0}
    t0 = time.time()
    for g in range(args.games):
        first = fixed_first if fixed_first is not None else g % 2
        winner, reason, plies = play_game(engine, levels[args.p0], levels[args.p1],
                                          first=first, max_plies=args.max_plies,
                                          draft_mode=args.draft)
        wins[winner] += 1
        tag = {0: 'p0', 1: 'p1', 2: 'draw', None: 'cap'}[winner]
        print(f'game {g + 1:3d}: first=p{first} -> {tag:4s} ({reason}, {plies} plies)')
    dt = time.time() - t0
    print(f'\np0 ({args.p0}): {wins[0]}  |  p1 ({args.p1}): {wins[1]}  |  '
          f'draws: {wins[2]}  |  ply-capped: {wins[None]}  |  {dt:.1f}s')


if __name__ == '__main__':
    main()
