# Twelve Janggi 십이장기

**Twelve Janggi** (십이장기) from *The Genius: Black Garnet* — a Dobutsu Shogi variant on a 3×4 board. Play 2-player over-the-board on one device, or against a built-in AI. Works in any modern browser on phones and laptops; rules follow [The Genius wiki](https://the-genius-show.fandom.com/wiki/Twelve_Janggi).

## Play

The game is fully static — **open `games/twelve-janggi/index.html` in a browser** (or serve the repo with any static host; the root `index.html` is a menu linking to all games). No backend. Saved games persist in localStorage.

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

# Card Chess 카드 체스

A third Genius death match in this repo: a 5×5 capture-everything duel where **five movement
cards** (Onitama-style) decide how your pieces move. Fully static like Twelve Janggi — **open
`games/card-chess/index.html`** or use the root menu. 2-player hot-seat and vs AI
(Easy / Normal / Hard) with UNDO, rules dialog, and localStorage persistence.

## Rules

- 5×5 board, 5 identical pieces per side: **white fills the bottom row, black the top row**,
  every piece **facing** the enemy (the yellow arrow is game state, not decoration).
- **Draft:** black alone assigns the five cards — Rook, Bishop, Attacker, Knight, Jumper —
  entirely as it pleases: 2 to itself, 2 to white, 1 to the wait slot (open information).
  As compensation, **white moves first**.
- **Your turn:** play one of your two cards and make one move that card allows with one of
  your pieces. Landing on an enemy captures it (no hands or drops). Your played card goes to
  the wait slot; the card that was waiting joins your hand — you always hold exactly two.

| Card | Moves |
|------|-------|
| Rook 룩 | 1 step orthogonally |
| Bishop 비숍 | 1 step diagonally |
| Attacker 어태커 | 1 or 2 straight ahead, or 1 diagonally ahead — relative to the piece's facing. The 2-ahead move needs an **empty** square 1 ahead (either colour blocks); capturing 1 ahead is fine |
| Knight 나이트 | chess knight jump (jumps over anything) |
| Jumper 점퍼 | leap over **any adjacent piece — yours or theirs** — landing directly beyond; the leapt piece is **not** captured |
| Queen 퀸 | 1 step in any direction — see upgrade below |

- **180° rotation:** a piece that lands on the far edge it is currently facing turns around
  (arrow and all). Any card's move triggers this, and since the trigger follows the *current*
  facing, a piece can flip back again later. Only the Attacker's moves depend on facing.
- **Queen upgrade:** the moment only 2 pieces remain on the board (1v1), the Jumper card
  immediately becomes the Queen — wherever it sits, even entering the wait slot after making
  the capture itself.
- **Game end:** capture all enemy pieces to win (the only win condition). No legal move with
  either card = stalemate, an immediate **draw**. The same full position (board + facings +
  card locations + side to move) occurring three times = **draw** by repetition.

The engine lives in `games/card-chess/engine.js` with a rule-identical Python mirror in
`py/card_chess.py` (`python3 -m unittest test_card_chess` covers the fine print above);
the same negamax agent as Twelve Janggi plays it, with Easy/Normal mistake margins
calibrated by `py/tune.py` self-play. In vs-AI, the AI drafts by scoring all 30 possible
card assignments with a shallow search.

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
