"""Generic negamax agent for any engine implementing the API in engine_api.py.

Mirrors core/negamax.js line for line. Alpha-beta pruning with time-limited
iterative deepening; moves are opaque — only the engine inspects them.
"""

import random
import time

WIN_SCORE = 100_000


class _Timeout(Exception):
    pass


def choose_move(engine, state, max_depth=8, time_ms=1000,
                margin_mean=0, margin_std=0, stats=None):
    """Pick a move for state['turn'].

    Stochastic play (Boltzmann-style mistakes): each call samples a margin
    from |Normal(margin_mean, margin_std)| and picks uniformly among root
    moves scoring within that margin of the best. The mean sets the typical
    mistake size, the spread sets how often unusually big or small ones
    occur; small mistakes stay frequent, big ones rare. Forced wins are
    immune: any losing or mate-missing move scores ~WIN_SCORE below the best
    and never enters the pool. Both 0 (default) = deterministic best play.

    Pass `stats={}` to receive margin / best / chosen / regret for tuning.
    """
    stochastic = margin_mean > 0 or margin_std > 0
    margin = abs(random.gauss(margin_mean, margin_std)) if stochastic else 0
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
                    # stochastic play needs exact root scores, so it forgoes the
                    # root alpha bound (a bounded fail-low would collapse the pool)
                    sc = -search(child, depth - 1, -WIN_SCORE * 2,
                                 (WIN_SCORE * 2) if stochastic else -alpha, 1)
                scored.append((mv, sc))
                if sc > alpha:
                    alpha = sc
            scored.sort(key=lambda x: -x[1])
            best_move, best_scored = scored[0][0], scored
            if scored[0][1] >= WIN_SCORE - max_depth:
                break  # forced win found
    except _Timeout:
        pass

    chosen, chosen_score = best_move, best_scored[0][1] if best_scored else 0
    if stochastic and best_scored:
        top = best_scored[0][1]
        pool = [(mv, sc) for mv, sc in best_scored if sc >= top - margin]
        chosen, chosen_score = random.choice(pool)
    if stats is not None and best_scored:
        stats['margin'] = margin
        stats['best'] = best_scored[0][1]
        stats['chosen'] = chosen_score
        stats['regret'] = best_scored[0][1] - chosen_score
    return chosen
