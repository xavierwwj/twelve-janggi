# Twelve Janggi 십이장기

**Twelve Janggi** (십이장기) from *The Genius: Black Garnet* — a Dobutsu Shogi variant on a 3×4 board. Play 2-player over-the-board on one device, or against a built-in AI. Works in any modern browser on phones and laptops; rules follow [The Genius wiki](https://the-genius-show.fandom.com/wiki/Twelve_Janggi).

## Play

The game is fully static — **open `index.html` in a browser** (or serve the folder with any static host). No backend. Saved games persist in localStorage.

On a phone, use the GitHub Pages deployment of this repo, and "Add to Home Screen" for an app-like experience.

- **2 Players** — over the board; the top player's pieces and tray are rotated 180° so you can lay a phone flat between you.
- **vs AI** — you play Green (초, bottom), the AI plays Red (홍, top). Pick who moves first and a level (Easy / Normal / Hard).

Buttons: `↺` menu · `UNDO` take back a move (in vs-AI it takes back the AI's reply and your move) · `?` rules. A game in progress, including its undo history, survives closing the page.

The AI is minimax (negamax) with alpha-beta pruning. Easy and Normal make deliberate, self-play-calibrated mistakes — Easy blunders a big piece roughly once every 7 turns, Normal drops a man about as often but bigger pieces almost never; Hard always plays its best move.

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
