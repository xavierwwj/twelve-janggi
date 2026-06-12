"""The generic engine API for two-player, zero-sum, turn-based games.

An *engine* is any module or object exposing the functions below. Agents
(negamax today, RL policies later) and tooling (self-play, tournaments)
depend only on this contract, never on a specific game. The JavaScript side
mirrors it exactly (core/negamax.js consumes it, games/*/engine.js provide it).

State requirements
------------------
A state is an opaque object owned by the engine, except for two fields agents
may read:
  state['turn']    : 0 or 1 — the player to move
  state['winner']  : None while the game is running, else the winning player

Moves are entirely opaque to agents: they come from legal_moves() and go back
into apply_move() uninspected.

Required functions
------------------
  initial_state(first=0) -> state
      A fresh game with `first` to move.

  clone_state(state) -> state
      A copy that can be mutated without affecting the original.

  legal_moves(state) -> list[move]
      All legal moves for state['turn']. Empty only if the engine never
      reaches that situation (terminal states must set 'winner' instead).

  apply_move(state, move) -> None
      Mutate `state`: perform the (assumed legal) move, advance 'turn',
      and set 'winner' (and any game-specific reason) when the game ends.

Required for search agents (negamax)
------------------------------------
  evaluate(state, player) -> float
      Finite heuristic score of a non-terminal state from `player`'s
      perspective (positive = good for `player`). Terminal outcomes are
      scored by the search itself, so wins/losses need no special values.

Optional
--------
  order_moves(state, moves) -> list[move]
      Best-first ordering hint to speed up alpha-beta cutoffs.

Future (RL) extensions — to be added per game when needed
---------------------------------------------------------
  encode_state(state, player) -> flat feature vector for a network
  move_index(state, move) / index_move(state, idx) -> fixed action indexing
"""

from typing import Any, List, Optional, Protocol


class GameEngine(Protocol):
    def initial_state(self, first: int = 0) -> Any: ...
    def clone_state(self, state: Any) -> Any: ...
    def legal_moves(self, state: Any) -> List[Any]: ...
    def apply_move(self, state: Any, move: Any) -> None: ...
    def evaluate(self, state: Any, player: int) -> float: ...
