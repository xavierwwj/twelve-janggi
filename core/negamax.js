'use strict';
/**
 * Generic negamax agent for two-player, zero-sum, turn-based games.
 *
 * Works with ANY engine object implementing the engine API (see README):
 *   cloneState(state) -> state
 *   legalMoves(state) -> move[]           // legal moves for state.turn
 *   applyMove(state, move) -> void        // mutates: advances turn, sets winner
 *   evaluate(state, player) -> number     // finite heuristic from player's view
 *   orderMoves?(state, moves) -> move[]   // optional: best-first ordering hint
 *
 * State requirements: state.turn is 0 or 1; state.winner is null while the
 * game is running, else the winning player's number. Moves are opaque to
 * this module — only the engine ever inspects them.
 */
const Negamax = (() => {
  const WIN_SCORE = 100000;

  function gaussian(mean, std) {
    const u = 1 - Math.random(), v = Math.random();
    return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /**
   * Pick a move via alpha-beta negamax with time-limited iterative deepening.
   * opts: { maxDepth=8, timeMs=1000, marginMean=0, marginStd=0, stats }
   *
   * Stochastic play (Boltzmann-style mistakes): each call samples a margin
   * from |Normal(marginMean, marginStd)| and picks uniformly among root moves
   * scoring within that margin of the best. The mean sets the typical mistake
   * size, the spread sets how often unusually big or small ones occur; small
   * mistakes stay frequent, big ones rare. Forced wins are immune: any losing
   * or mate-missing move scores ~WIN_SCORE below the best and never enters
   * the pool. Both 0 (default) = deterministic best play.
   *
   * Pass `stats: {}` to receive { margin, best, chosen, regret } for tuning.
   */
  function chooseMove(game, state, opts = {}) {
    const maxDepth = opts.maxDepth ?? 8;
    const timeMs = opts.timeMs ?? 1000;
    const marginMean = opts.marginMean ?? 0;
    const marginStd = opts.marginStd ?? 0;
    const stochastic = marginMean > 0 || marginStd > 0;
    const margin = stochastic ? Math.abs(gaussian(marginMean, marginStd)) : 0;
    const order = game.orderMoves ? game.orderMoves.bind(game) : (s, ms) => ms;

    const rootMoves = game.legalMoves(state);
    if (!rootMoves.length) return null;
    const deadline = performance.now() + timeMs;
    let nodes = 0;

    function search(s, depth, alpha, beta, ply) {
      if ((++nodes & 1023) === 0 && performance.now() > deadline) throw 'timeout';
      let best = -WIN_SCORE * 2;
      for (const mv of order(s, game.legalMoves(s))) {
        const child = game.cloneState(s);
        game.applyMove(child, mv);
        let sc;
        if (child.winner !== null) sc = child.winner === s.turn ? WIN_SCORE - ply : -(WIN_SCORE - ply);
        else if (depth <= 1) sc = -game.evaluate(child, child.turn);
        else sc = -search(child, depth - 1, -beta, -alpha, ply + 1);
        if (sc > best) best = sc;
        if (best > alpha) alpha = best;
        if (alpha >= beta) break;
      }
      return best;
    }

    let bestMove = rootMoves[0];
    let bestScored = null;  // [move, score] pairs from the deepest completed depth
    try {
      for (let depth = 1; depth <= maxDepth; depth++) {
        const scored = [];
        let alpha = -WIN_SCORE * 2;
        for (const mv of order(state, rootMoves.slice())) {
          const child = game.cloneState(state);
          game.applyMove(child, mv);
          let sc;
          if (child.winner !== null) sc = child.winner === state.turn ? WIN_SCORE - 1 : -(WIN_SCORE - 1);
          else if (depth <= 1) sc = -game.evaluate(child, child.turn);
          // stochastic play needs exact root scores, so it forgoes the root
          // alpha bound (a bounded fail-low would collapse the random pool)
          else sc = -search(child, depth - 1, -WIN_SCORE * 2, stochastic ? WIN_SCORE * 2 : -alpha, 1);
          scored.push([mv, sc]);
          if (sc > alpha) alpha = sc;
        }
        scored.sort((a, b) => b[1] - a[1]);
        bestMove = scored[0][0];
        bestScored = scored;
        if (scored[0][1] >= WIN_SCORE - maxDepth) break;  // forced win found
      }
    } catch (e) {
      if (e !== 'timeout') throw e;
    }

    let chosen = bestMove;
    let chosenScore = bestScored ? bestScored[0][1] : 0;
    if (stochastic && bestScored) {
      const top = bestScored[0][1];
      const pool = bestScored.filter(([, sc]) => sc >= top - margin);
      const pick = pool[Math.floor(Math.random() * pool.length)];
      chosen = pick[0];
      chosenScore = pick[1];
    }
    if (opts.stats && bestScored) {
      opts.stats.margin = margin;
      opts.stats.best = bestScored[0][1];
      opts.stats.chosen = chosenScore;
      opts.stats.regret = bestScored[0][1] - chosenScore;
    }
    return chosen;
  }

  return { chooseMove, WIN_SCORE };
})();
