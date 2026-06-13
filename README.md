# Twelve Janggi 십이장기

**Twelve Janggi** (십이장기) from *The Genius: Black Garnet* — a Dobutsu Shogi variant on a 3×4 board. Play 2-player over-the-board on one device, or against a built-in AI. Works in any modern browser on phones and laptops; rules follow [The Genius wiki](https://the-genius-show.fandom.com/wiki/Twelve_Janggi).

The repo doubles as a small **framework for two-player turn-based games**: the rules engine, the search AI, and the UI are separate layers that talk through a documented API, in both JavaScript (for play) and Python (for experiments / future RL training).

## Play

The game is fully static — **open `index.html` in a browser** (or serve the folder with any static host). No backend. Saved games persist in localStorage.

On a phone, use the GitHub Pages deployment of this repo, and "Add to Home Screen" for an app-like experience.

- **2 Players** — over the board; the top player's pieces and tray are rotated 180° so you can lay a phone flat between you.
- **vs AI** — you play Green (초, bottom), the AI plays Red (홍, top). Pick who moves first and a level (Easy / Normal / Hard).

Buttons: `↺` menu · `↶` undo (in vs-AI it takes back the AI's reply and your move) · `?` rules. A game in progress, including its undo history, survives closing the page.

## Architecture

```
index.html                   UI for Twelve Janggi (rendering + input only)
core/negamax.js              generic negamax agent — works with ANY engine
games/twelve-janggi/engine.js  the Twelve Janggi engine (implements the API)

py/engine_api.py             the engine API contract (documented Protocol)
py/negamax.py                generic negamax agent (mirror of core/negamax.js)
py/twelve_janggi.py          engine (mirror of games/twelve-janggi/engine.js)
py/selfplay.py               agent-vs-agent harness — seed of an RL training loop
```

### The engine API

An **engine** is an object/module that owns all game knowledge. Agents and tooling only ever call:

| Function | Contract |
|----------|----------|
| `initialState(first)` | fresh game state with player `first` (0/1) to move |
| `cloneState(state)` | independent copy, safe to mutate |
| `legalMoves(state)` | all legal moves for `state.turn`; moves are **opaque** to callers |
| `applyMove(state, move)` | mutate: perform move, advance `turn`, set `winner` when the game ends |
| `evaluate(state, player)` | finite heuristic for non-terminal states, from `player`'s perspective |
| `orderMoves(state, moves)` | *(optional)* best-first hint for alpha-beta cutoffs |
| `name`, `rules` | display metadata: `rules` is a structured description (title + sections with items/tables) that the UI renders into its rules dialog, so game knowledge never leaks into UI code |

States expose exactly two fields to non-engine code: `turn` (0 or 1) and `winner` (`null`/`None` while running). Everything else — board shape, hands, special rules — is private to the engine.

### Agents

`core/negamax.js` / `py/negamax.py` implement minimax (negamax form) with alpha-beta pruning and time-limited iterative deepening, parameterised by `{maxDepth, timeMs, marginMean, marginStd}`. They contain **zero game knowledge** — point them at any engine implementing the API.

`marginMean`/`marginStd` make the agent deliberately fallible: each move it samples a tolerance from |Normal(mean, std)| and plays a random move scoring within that tolerance of the best — so small mistakes are frequent and big ones rare, and both the typical mistake size and its frequency are tunable. Forced wins are immune (losing moves score ~100000 below the best and never enter the pool). The in-game levels were calibrated by self-play with `py/tune.py`: **Easy** (depth 2, mean 52/std 21) blunders a minister/general roughly once every 7 turns; **Normal** (depth 5, mean 18/std 8) drops a man roughly once every 7 turns and bigger pieces almost never; **Hard** (depth 12) always plays its best move.

`py/selfplay.py` pits two agent configurations against each other through the same API:

```sh
cd py && python3 selfplay.py --games 20 --p0 blitz --p1 normal
cd py && python3 tune.py --depth 2 --mean 52 --std 21 --games 30   # measure mistake rates
```

### Adding a new game

1. Write `games/<name>/engine.js` implementing the six API functions (and `py/<name>.py` if you want Python-side experiments).
2. Write a UI page for it that calls the engine for state/moves and `Negamax.chooseMove(engine, state, opts)` for the computer player.
3. That's it — the agents and self-play tooling work unchanged.

### RL roadmap

Training belongs in Python (the `py/` mirror exists for exactly this): self-play with `twelve_janggi.py`, learn a policy/value net, then export the trained weights (JSON/ONNX) and run inference in the browser — the page stays static. The API will grow two per-game functions when needed: `encode_state(state, player)` (feature vector) and a fixed move indexing (`move_index`/`index_move`).

**Keep the JS and Python engines rule-identical** — they are deliberate line-for-line mirrors; any rule change must land in both.

## Rules

- 3×4 board. The row nearest each player is their **territory**. Each side starts with 相 · 王 · 將 on their territory row and a 子 in front of the king.

| Piece | Name | Movement |
|-------|------|----------|
| 王 | king (왕) | 1 step, any direction |
| 將 | general (장) | 1 step orthogonally |
| 相 | minister (상) | 1 step diagonally |
| 子 | man (자) | 1 step forward |
| 侯 | feudal lord (후) | 1 step any direction except diagonally backward |

The red dots on each tile show its move directions.

- Capturing an enemy piece puts it in your **hand** (a captured 侯 reverts to 子). On your turn you may **drop** a hand piece onto any empty square **outside the opponent's territory** instead of moving.
- A 子 that moves into the opponent's territory promotes to 侯.
- **Win conditions:**
  1. Capture the enemy 王.
  2. Move your own 王 into the opponent's territory and survive your opponent's next move.
  3. Your opponent has no legal move (house rule; practically unreachable).
