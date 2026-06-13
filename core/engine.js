'use strict';
/**
 * Abstract base class for two-player, zero-sum, turn-based game engines.
 *
 * A concrete engine owns all game knowledge; agents (negamax today, an RL
 * policy later) and tooling depend only on this interface, never on a
 * specific game. Subclass it and implement the five required methods:
 *
 *   initialState(first=0) -> state     fresh game, player `first` (0/1) to move
 *   cloneState(state)     -> state     independent copy, safe to mutate
 *   legalMoves(state)     -> move[]     all legal moves for state.turn
 *   applyMove(state, move)-> void       mutate: do move, advance turn, set winner
 *   evaluate(state, who)  -> number     finite heuristic from `who`'s view
 *
 * orderMoves is optional (identity by default) — override it with a
 * best-first hint to speed up alpha-beta cutoffs.
 *
 * State contract: every state exposes `turn` (0 or 1) and `winner` (null
 * while the game runs, else the winning player). Everything else — board
 * shape, hands, special rules — is private to the engine. Moves are opaque
 * to agents: they come out of legalMoves() and go back into applyMove()
 * uninspected. A concrete engine may add its own helpers and a `rules`
 * display-metadata object on top of this interface.
 *
 * Mirrors py/engine_api.py.
 */
class GameEngine {
  get name() { return this.constructor.name; }

  initialState(first = 0) { throw new Error(`${this.name}.initialState() not implemented`); }
  cloneState(state)       { throw new Error(`${this.name}.cloneState() not implemented`); }
  legalMoves(state)       { throw new Error(`${this.name}.legalMoves() not implemented`); }
  applyMove(state, move)  { throw new Error(`${this.name}.applyMove() not implemented`); }
  evaluate(state, player) { throw new Error(`${this.name}.evaluate() not implemented`); }

  // optional best-first ordering hint for alpha-beta; identity by default
  orderMoves(state, moves) { return moves; }
}
