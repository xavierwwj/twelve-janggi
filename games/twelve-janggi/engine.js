'use strict';
/**
 * Twelve Janggi (십이장기) engine — implements the generic engine API
 * (see README and core/negamax.js) plus a few UI helpers.
 *
 * Rules per The Genius: Black Garnet (a Dobutsu Shogi variant):
 *   - 3 columns x 4 rows. Player 0 sits at the bottom (high row numbers),
 *     player 1 at the top. The row nearest each player is their territory.
 *   - wang 王 any direction, jang 將 orthogonal, sang 相 diagonal,
 *     ja 子 forward only; ja promotes to hu 侯 (any direction except
 *     diagonally backward) on entering the opponent's territory.
 *   - Captured pieces join the capturer's hand (hu reverts to ja) and may
 *     be dropped on any empty square outside the opponent's territory.
 *   - Win by capturing the enemy wang, or by moving your own wang into the
 *     opponent's territory and surviving one opposing turn. A player with
 *     no legal move loses.
 *
 * Moves: {from, to} | {drop: pieceType, to}. Board squares are indexed
 * row-major 0..11 with row 0 at the top.
 */
const TwelveJanggi = (() => {
  const ROWS = 4, COLS = 3;

  const HANJA = { wang: '王', jang: '將', sang: '相', ja: '子', hu: '侯' };
  const KOR   = { wang: '왕', jang: '장', sang: '상', ja: '자', hu: '후' };

  // move directions for player 0 (bottom, forward = -1 row)
  const MOVES = {
    wang: [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]],
    jang: [[-1,0],[1,0],[0,-1],[0,1]],
    sang: [[-1,-1],[-1,1],[1,-1],[1,1]],
    ja:   [[-1,0]],
    hu:   [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,0]],
  };

  const goalRow = owner => owner === 0 ? 0 : ROWS - 1;

  function initialState(first) {
    const board = Array(ROWS * COLS).fill(null);
    const put = (r, c, type, owner) => board[r * COLS + c] = { type, owner };
    put(3, 0, 'sang', 0); put(3, 1, 'wang', 0); put(3, 2, 'jang', 0); put(2, 1, 'ja', 0);
    put(0, 2, 'sang', 1); put(0, 1, 'wang', 1); put(0, 0, 'jang', 1); put(1, 1, 'ja', 1);
    return {
      board, hands: [[], []], turn: first,
      pendingTry: null,   // player whose wang sits in enemy territory awaiting survival
      winner: null, reason: null,
    };
  }

  // piece objects are never mutated (promotion replaces them), so shallow copy is safe
  function cloneState(st) {
    return {
      board: st.board.slice(),
      hands: [st.hands[0].slice(), st.hands[1].slice()],
      turn: st.turn, pendingTry: st.pendingTry,
      winner: st.winner, reason: st.reason,
    };
  }

  function dirsFor(type, owner) {
    return owner === 0 ? MOVES[type] : MOVES[type].map(([r, c]) => [-r, -c]);
  }

  function pieceMovesAt(st, idx) {
    const p = st.board[idx];
    if (!p) return [];
    const r = Math.floor(idx / COLS), c = idx % COLS, out = [];
    for (const [dr, dc] of dirsFor(p.type, p.owner)) {
      const nr = r + dr, nc = c + dc;
      if (nr < 0 || nr >= ROWS || nc < 0 || nc >= COLS) continue;
      const t = st.board[nr * COLS + nc];
      if (t && t.owner === p.owner) continue;
      out.push(nr * COLS + nc);
    }
    return out;
  }

  function dropIdxs(st, player) {
    const out = [];
    for (let i = 0; i < ROWS * COLS; i++) {
      if (!st.board[i] && Math.floor(i / COLS) !== goalRow(player)) out.push(i);
    }
    return out;
  }

  function legalMoves(st) {
    const player = st.turn, out = [];
    for (let i = 0; i < ROWS * COLS; i++) {
      const p = st.board[i];
      if (p && p.owner === player) {
        for (const to of pieceMovesAt(st, i)) out.push({ from: i, to });
      }
    }
    if (st.hands[player].length) {
      const empties = dropIdxs(st, player);
      for (const type of new Set(st.hands[player])) {
        for (const to of empties) out.push({ drop: type, to });
      }
    }
    return out;
  }

  function hasMoveFor(st, player) {
    if (st.hands[player].length && dropIdxs(st, player).length) return true;
    return st.board.some((p, i) => p && p.owner === player && pieceMovesAt(st, i).length);
  }

  function applyMove(st, mv) {
    const player = st.turn;
    let kingCaptured = false;
    if (mv.drop) {
      const h = st.hands[player];
      h.splice(h.indexOf(mv.drop), 1);
      st.board[mv.to] = { type: mv.drop, owner: player };
    } else {
      const p = st.board[mv.from], cap = st.board[mv.to];
      st.board[mv.to] = p;
      st.board[mv.from] = null;
      if (cap) {
        if (cap.type === 'wang') kingCaptured = true;
        st.hands[player].push(cap.type === 'hu' ? 'ja' : cap.type);
      }
      if (p.type === 'ja' && Math.floor(mv.to / COLS) === goalRow(player)) {
        st.board[mv.to] = { type: 'hu', owner: player };
      }
    }

    if (kingCaptured) { st.winner = player; st.reason = 'capture'; return; }
    // opponent's wang entered our territory last turn and we failed to take it
    if (st.pendingTry !== null && st.pendingTry !== player) {
      st.winner = st.pendingTry; st.reason = 'reach'; return;
    }
    st.pendingTry = null;
    for (let i = 0; i < ROWS * COLS; i++) {
      const p = st.board[i];
      if (p && p.type === 'wang' && p.owner === player && Math.floor(i / COLS) === goalRow(player)) {
        st.pendingTry = player;
        break;
      }
    }
    st.turn = 1 - player;
    if (!hasMoveFor(st, st.turn)) { st.winner = player; st.reason = 'stuck'; }
  }

  /* ---- search heuristics (part of the engine: game knowledge lives here) ---- */

  const VAL = { ja: 10, sang: 30, jang: 34, hu: 46, wang: 0 };
  const HAND_VAL = { ja: 9, sang: 28, jang: 32 };

  // kings score 0: king loss and the try rule are terminal states the search sees directly
  function evaluate(st, me) {
    let s = 0;
    for (let i = 0; i < ROWS * COLS; i++) {
      const p = st.board[i];
      if (!p) continue;
      let v = VAL[p.type];
      if (p.type === 'ja') {
        v += 2 * (p.owner === 0 ? 3 - Math.floor(i / COLS) : Math.floor(i / COLS));
      }
      s += p.owner === me ? v : -v;
    }
    for (const owner of [0, 1]) {
      let hv = 0;
      for (const t of st.hands[owner]) hv += HAND_VAL[t];
      s += owner === me ? hv : -hv;
    }
    return s;
  }

  // captures first, biggest victim first — helps alpha-beta cut early
  function orderMoves(st, moves) {
    const key = mv => {
      if (!mv.drop) {
        const cap = st.board[mv.to];
        if (cap) return -(cap.type === 'wang' ? 10000 : VAL[cap.type]);
      }
      return 0;
    };
    return moves.sort((a, b) => key(a) - key(b));
  }

  /* ---- display metadata (engine API: game knowledge stays in the engine) ---- */

  const rules = {
    title: 'Twelve Janggi 십이장기',
    sections: [
      {
        heading: 'Setup',
        items: [
          '3×4 board. The row nearest each player is their <b>territory</b>. Each side starts with ' +
          '相 · 王 · 將 on their territory row and a 子 in front of the king.',
        ],
      },
      {
        heading: 'Pieces',
        table: {
          headers: ['Piece', 'Name', 'Movement'],
          rows: [
            ['王', 'king (왕)', '1 step, any direction'],
            ['將', 'general (장)', '1 step orthogonally'],
            ['相', 'minister (상)', '1 step diagonally'],
            ['子', 'man (자)', '1 step forward'],
            ['侯', 'feudal lord (후)', '1 step any direction except diagonally backward'],
          ],
        },
        note: 'The red dots on each tile show its move directions.',
      },
      {
        heading: 'Captures & drops',
        items: [
          'Moving onto an enemy piece captures it into your <b>hand</b> (a captured 侯 reverts to 子).',
          'Instead of moving, you may <b>drop</b> a hand piece onto any empty square ' +
          '<b>outside the opponent\'s territory</b>.',
          'A 子 that moves into the opponent\'s territory promotes to 侯.',
        ],
      },
      {
        heading: 'Win conditions',
        ordered: true,
        items: [
          'Capture the enemy 王.',
          'Move your own 王 into the opponent\'s territory and survive your opponent\'s next move.',
          'Your opponent has no legal move.',
        ],
      },
    ],
  };

  return {
    name: 'Twelve Janggi',
    // engine API
    initialState, cloneState, legalMoves, applyMove, evaluate, orderMoves,
    // display metadata
    rules,
    // UI helpers
    ROWS, COLS, MOVES, HANJA, KOR, goalRow, pieceMovesAt, dropIdxs,
  };
})();
