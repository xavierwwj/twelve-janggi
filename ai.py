"""AI opponent for Twelve Janggi: negamax with alpha-beta pruning and
time-limited iterative deepening over the engine in game.py."""

import random
import time

from game import COLS, goal_row

VAL = {'ja': 10, 'sang': 30, 'jang': 34, 'hu': 46, 'wang': 0}
HAND_VAL = {'ja': 9, 'sang': 28, 'jang': 32}
WIN = 100_000

# level -> (max_depth, time_limit_seconds, random_margin)
LEVELS = {
    'easy':   (2,  0.5, 8),
    'normal': (6,  1.0, 0),
    'hard':   (12, 2.5, 0),
}


class _Timeout(Exception):
    pass


def evaluate(g, me):
    """Static score from `me`'s perspective. Kings score 0 here: king loss
    and the try rule are terminal states the search sees directly."""
    s = 0
    for i, p in enumerate(g.board):
        if p is None:
            continue
        t, owner = p
        v = VAL[t]
        if t == 'ja':
            adv = (3 - i // COLS) if owner == 0 else (i // COLS)
            v += 2 * adv
        s += v if owner == me else -v
    for owner in (0, 1):
        hv = sum(HAND_VAL[t] for t in g.hands[owner])
        s += hv if owner == me else -hv
    return s


def _order_key(g, mv):
    if mv[0] == 'm':
        cap = g.board[mv[2]]
        if cap is not None:
            return -(10_000 if cap[0] == 'wang' else VAL[cap[0]])
    return 0


def choose_move(g, level='normal'):
    max_depth, time_limit, margin = LEVELS.get(level, LEVELS['normal'])
    root_moves = g.legal_moves()
    if not root_moves:
        return None
    start = time.time()
    nodes = 0

    def negamax(state, depth, alpha, beta, ply):
        nonlocal nodes
        nodes += 1
        if nodes % 1024 == 0 and time.time() - start > time_limit:
            raise _Timeout
        best = -WIN * 2
        for mv in sorted(state.legal_moves(), key=lambda m: _order_key(state, m)):
            child = state.copy()
            child.apply(mv)
            if child.winner is not None:
                s = (WIN - ply) if child.winner == state.turn else -(WIN - ply)
            elif depth <= 1:
                s = -evaluate(child, child.turn)
            else:
                s = -negamax(child, depth - 1, -beta, -alpha, ply + 1)
            if s > best:
                best = s
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best

    best_move = root_moves[0]
    best_scored = None  # (move, score) list from the deepest completed search
    try:
        for depth in range(1, max_depth + 1):
            scored = []
            alpha = -WIN * 2
            for mv in sorted(root_moves, key=lambda m: _order_key(g, m)):
                child = g.copy()
                child.apply(mv)
                if child.winner is not None:
                    s = (WIN - 1) if child.winner == g.turn else -(WIN - 1)
                elif depth <= 1:
                    s = -evaluate(child, child.turn)
                else:
                    s = -negamax(child, depth - 1, -WIN * 2, -alpha, 1)
                scored.append((mv, s))
                if s > alpha:
                    alpha = s
            scored.sort(key=lambda x: -x[1])
            best_move, best_scored = scored[0][0], scored
            if scored[0][1] >= WIN - max_depth:
                break  # forced win found; no need to search deeper
    except _Timeout:
        pass

    if margin and best_scored:
        top = best_scored[0][1]
        pool = [mv for mv, s in best_scored if s >= top - margin]
        return random.choice(pool)
    return best_move
