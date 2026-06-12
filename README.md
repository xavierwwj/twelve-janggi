# Twelve Janggi 십이장기

**Twelve Janggi** (십이장기) from *The Genius: Black Garnet* — a Dobutsu Shogi variant on a 3×4 board. Play 2-player over-the-board on one device, or against a built-in AI. Works in any modern browser on phones and laptops.

Rules follow [The Genius wiki](https://the-genius-show.fandom.com/wiki/Twelve_Janggi).

## Run

Python 3 only, no dependencies:

```sh
python3 server.py          # default port 8943
```

Then open <http://localhost:8943>. To play on your phone over the same Wi-Fi, open `http://<your-laptop-ip>:8943`.

## Modes

- **2 Players** — over the board; the top player's pieces and tray are rotated 180° so you can lay a phone flat between you.
- **vs AI** — you play Green (초, bottom), the AI plays Red (홍, top). Choose who moves first and an AI level (Easy / Normal / Hard).

## How to play

- Tap a piece to see its legal moves (green dot = move, red outline = capture), then tap the destination.
- Tap a captured piece in your tray, then tap an empty square to drop it.
- `↺` opens the menu, `?` shows the rules.

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

## Architecture

| File | Role |
|------|------|
| `game.py` | Pure rules engine — board state, legal moves, promotion, the try rule, win detection. |
| `ai.py` | AI opponent: negamax + alpha-beta pruning with time-limited iterative deepening over `game.py`. |
| `server.py` | Stdlib-only HTTP server: serves the static UI and a small JSON API (`/api/new`, `/api/move`, `/api/ai`, `/api/state`). |
| `index.html` | The entire UI — rendering, taps, and move hints; the server stays authoritative on rules. |

The server keeps one game in memory, so it hosts one match at a time (perfect for over-the-board or vs-AI play).
