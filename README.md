# Twelve Janggi 십이장기

**Twelve Janggi** (십이장기) from *The Genius: Black Garnet* — a Dobutsu Shogi variant on a 3×4 board. Play 2-player over-the-board on one device, or against a built-in AI. Works in any modern browser on phones and laptops; rules follow [The Genius wiki](https://the-genius-show.fandom.com/wiki/Twelve_Janggi).

## Play

The game is fully static — **open `games/twelve-janggi/index.html` in a browser** (or serve the repo with any static host; the root `index.html` is a menu linking to both games). No backend. Saved games persist in localStorage.

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

---

# Black and White 흑과 백

A second Genius death match in this repo (S2/S4): a **simultaneous, hidden-information** game. Unlike Twelve Janggi it can't be played hot-seat — both players choose at the same time and must not see each other's tile — so it runs on a small **game server** that holds the hidden state and sends each player only their own view.

## Run it locally

Python 3, stdlib only:

```sh
python3 py/bw_server.py            # default port 8770
```

Open the printed URL on two devices (or two browser tabs); each taps **Find a game** to be matched, then play. On phones, both devices use `http://<your-laptop-ip>:8770` over the same Wi-Fi.

## Host it online (Render, free)

To play over the internet rather than same Wi-Fi, deploy `bw_server.py` to [Render](https://render.com) — the repo includes a `render.yaml` blueprint:

1. Push this repo to GitHub (already done).
2. In the Render dashboard: **New + → Blueprint**, connect this repo, **Apply**. It reads `render.yaml` and creates a free web service named `black-and-white`.
3. When it's live, open the service's `*.onrender.com` URL on two devices.
4. Optional: paste that URL into `BW_URL` in the root `index.html` so the landing page links to it.

The free tier sleeps after ~15 min idle (first visit then cold-starts in ~30–60s) and keeps games in memory, so a game lost to a sleep just needs a rejoin — fine for casual play. The server reads Render's `$PORT` automatically.

## Rules

- You each hold 9 tiles, **0–8**. Even numbers are **black** (0,2,4,6,8), odd are **white** (1,3,5,7).
- Over **9 rounds** the **higher number wins** the round (+1 point); ties score nothing. You lock one tile before a countdown — a random remaining tile is auto-played if you don't.
- **Round 1** is locked in simultaneously. After that the **winner of the previous round must choose first**, and the **loser sees that tile's colour before responding** — the edge that compensates for being behind. A tie makes the next round simultaneous again.
- You only ever see the opponent's tile **colour**, never their exact number — even afterward. Track what they've spent to deduce what's left.
- Most points after 9 rounds wins; reaching **5** clinches it; equal points is a draw. You can **resign** at any time to concede.

## Why it isn't on GitHub Pages

Pages serves static files only, and a hidden-information game needs a server to be authoritative (a client can't hold the full state without leaking the opponent's tiles). So Twelve Janggi is on Pages; Black and White runs from `bw_server.py`.

An AI opponent is planned but not built yet — negamax doesn't apply here (simultaneous + hidden info calls for a randomized / game-theoretic agent), so it will be a separate agent type. `py/black_and_white.py` already holds the rules and the `observe()` masking it will use.
