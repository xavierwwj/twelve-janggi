"""Generic negamax agent for any engine implementing the API in engine_api.py.

Mirrors core/negamax.js line for line. Alpha-beta pruning with time-limited
iterative deepening; moves are opaque — only the engine inspects them.
"""

import random
import time

WIN_SCORE = 100_000


class _Timeout(Exception):
    pass


def choose_move(engine, state, max_depth=8, time_ms=1000, random_margin=0):
    """Pick a move for state['turn'].

    random_margin > 0 picks uniformly among root moves scoring within that
    margin of the best (weaker, less predictable play).
    """
    order = getattr(engine, 'order_moves', lambda s, ms: ms)
    root_moves = engine.legal_moves(state)
    if not root_moves:
        return None
    deadline = time.monotonic() + time_ms / 1000.0
    nodes = 0

    def search(s, depth, alpha, beta, ply):
        nonlocal nodes
        nodes += 1
        if nodes % 1024 == 0 and time.monotonic() > deadline:
            raise _Timeout
        best = -WIN_SCORE * 2
        for mv in order(s, engine.legal_moves(s)):
            child = engine.clone_state(s)
            engine.apply_move(child, mv)
            if child['winner'] is not None:
                sc = (WIN_SCORE - ply) if child['winner'] == s['turn'] else -(WIN_SCORE - ply)
            elif depth <= 1:
                sc = -engine.evaluate(child, child['turn'])
            else:
                sc = -search(child, depth - 1, -beta, -alpha, ply + 1)
            if sc > best:
                best = sc
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best

    best_move = root_moves[0]
    best_scored = None  # (move, score) pairs from the deepest completed depth
    try:
        for depth in range(1, max_depth + 1):
            scored = []
            alpha = -WIN_SCORE * 2
            for mv in order(state, list(root_moves)):
                child = engine.clone_state(state)
                engine.apply_move(child, mv)
                if child['winner'] is not None:
                    sc = (WIN_SCORE - 1) if child['winner'] == state['turn'] else -(WIN_SCORE - 1)
                elif depth <= 1:
                    sc = -engine.evaluate(child, child['turn'])
                else:
                    # random_margin needs exact root scores, so it forgoes the
                    # root alpha bound (a bounded fail-low would collapse the pool)
                    sc = -search(child, depth - 1, -WIN_SCORE * 2,
                                 (WIN_SCORE * 2) if random_margin else -alpha, 1)
                scored.append((mv, sc))
                if sc > alpha:
                    alpha = sc
            scored.sort(key=lambda x: -x[1])
            best_move, best_scored = scored[0][0], scored
            if scored[0][1] >= WIN_SCORE - max_depth:
                break  # forced win found
    except _Timeout:
        pass

    if random_margin and best_scored:
        top = best_scored[0][1]
        pool = [mv for mv, sc in best_scored if sc >= top - random_margin]
        return random.choice(pool)
    return best_move
