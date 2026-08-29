'use strict';
/**
 * Card Chess (카드 체스) — a GameEngine subclass (see core/engine.js).
 *
 * The Genius death match: 5x5 board, 5 identical pieces per side, and five
 * Onitama-style movement cards (rook / bishop / attacker / knight / jumper).
 * Black (player 1) drafts all five cards 2-2-1 before the game; white
 * (player 0) moves first. Playing a card swaps it with the single
 * sitting-out wait card. Capture all enemy pieces to win.
 *
 * State: { board: [{owner, facing}|null]*25,
 *          cards: [[c,c],[c,c]],   // each pair kept sorted (canonical)
 *          waitCard: c,            // the single sitting-out card
 *          turn: 0|1, winner: null|0|1|2, reason: string|null,
 *          reps: {positionKey: count} }   // threefold-repetition bookkeeping
 *
 * winner 2 means a draw (reason 'stalemate' | 'repetition'). The reused
 * negamax agent only knows win/lose terminals, so in search a draw scores
 * as a loss for the side whose move created it — the AI plays to avoid
 * draws. Documented convention; identical in both mirrors.
 *
 * Moves: { card, from, to }. Board squares are indexed row-major 0..24 with
 * row 0 at the top; player 0 (white) starts on the bottom row facing up,
 * player 1 (black) on the top row facing down.
 * Facing: 0 = up (-row), 1 = right, 2 = down, 3 = left.
 *
 * Mirrors py/card_chess.py line for line; both must stay rule-identical.
 */
const CardChess = (() => {
  const N = 5;

  const CARDS = ['rook', 'bishop', 'attacker', 'knight', 'jumper'];
  const KOR = { rook: '룩', bishop: '비숍', attacker: '어태커',
                knight: '나이트', jumper: '점퍼', queen: '퀸' };

  const DIRS = [[-1, 0], [0, 1], [1, 0], [0, -1]];  // facing 0..3 = up/right/down/left
  const ORTHO = [[-1, 0], [0, 1], [1, 0], [0, -1]];
  const DIAG = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
  const ALL8 = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
  const KNIGHT = [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]];

  // default draft so the engine can start headless (UI always passes one)
  const DEFAULT_DRAFT = { cards: [['bishop', 'rook'], ['attacker', 'knight']],
                          waitCard: 'jumper' };

  // search heuristics (starting points, roughly tuned by self-play)
  const MATERIAL = 100;
  const CARD_VAL = { attacker: 10, bishop: 8, jumper: 4,
                     knight: 12, queen: 16, rook: 8 };
  const MOBILITY = 2;     // per destination a held card offers
  const FACE_BONUS = 3;   // per piece with at least one enemy ahead of its facing

  // display metadata rendered by the UI's rules dialog
  const rules = {
    title: 'Card Chess 카드 체스',
    sections: [
      {
        heading: 'Setup',
        items: [
          '5×5 board, 5 identical pieces per side. White fills the bottom row, ' +
          'black the top row, every piece facing the enemy (the <b>yellow arrow</b>).',
          '<b>Black alone drafts</b> the five movement cards before the game: ' +
          '2 to itself, 2 to white, 1 to the wait slot. <b>White moves first.</b>',
        ],
      },
      {
        heading: 'Your turn',
        items: [
          'Play one of your two cards: move one of your pieces to a square that ' +
          'card allows. Landing on an enemy piece captures it (no drops).',
          'Your played card goes to the <b>wait slot</b> and the waiting card joins ' +
          'your hand — you always hold exactly two.',
        ],
      },
      {
        heading: 'Cards',
        table: {
          headers: ['Card', 'Moves'],
          rows: [
            ['Rook 룩', '1 step orthogonally'],
            ['Bishop 비숍', '1 step diagonally'],
            ['Attacker 어태커', '1 or 2 straight ahead (2 only if the square ahead ' +
             'is empty), or 1 diagonally ahead — follows the facing arrow'],
            ['Knight 나이트', 'chess knight jump'],
            ['Jumper 점퍼', 'leap over any adjacent piece (either colour), landing ' +
             'directly beyond; the leapt piece is not captured'],
            ['Queen 퀸', '1 step any direction — the Jumper becomes the Queen ' +
             'the moment only 2 pieces remain on the board'],
          ],
        },
      },
      {
        heading: 'Facing & rotation',
        items: [
          'Only the Attacker moves relative to facing, but every piece always shows one.',
          'A piece that lands on the far edge it is facing <b>turns 180°</b> — any ' +
          "card's move can trigger this, and later flips back are possible.",
        ],
      },
      {
        heading: 'Game end',
        items: [
          'Capture all enemy pieces to win — the only win condition.',
          'No legal move with either card = stalemate (draw).',
          'The same full position (board, facings, cards, side to move) ' +
          'occurring three times = draw.',
        ],
      },
    ],
  };

  class CardChess extends GameEngine {
    constructor() {
      super();
      // constants + display metadata the UI reads off the engine
      Object.assign(this, { N, CARDS, KOR, DIRS, ALL8, rules });
    }

    initialState(first = 0, draft = null) {
      const d = draft || DEFAULT_DRAFT;
      const board = Array(N * N).fill(null);
      for (let c = 0; c < N; c++) {
        board[(N - 1) * N + c] = { owner: 0, facing: 0 };  // white, facing up
        board[c] = { owner: 1, facing: 2 };                // black, facing down
      }
      const st = {
        board,
        cards: [d.cards[0].slice().sort(), d.cards[1].slice().sort()],
        waitCard: d.waitCard,
        turn: first, winner: null, reason: null,
        reps: {},
      };
      st.reps[this.posKey(st)] = 1;
      return st;
    }

    // piece objects are never mutated (rotation replaces them), so shallow copy is safe
    cloneState(st) {
      return {
        board: st.board.slice(),
        cards: [st.cards[0].slice(), st.cards[1].slice()],
        waitCard: st.waitCard,
        turn: st.turn, winner: st.winner, reason: st.reason,
        reps: Object.assign({}, st.reps),
      };
    }

    /** Full-position key for threefold repetition (A7): board incl. facings
     *  + card distribution incl. wait card + side to move. */
    posKey(st) {
      let b = '';
      for (const p of st.board) b += p === null ? '.' : 'abcdefgh'[p.owner * 4 + p.facing];
      return b + '|' + st.cards[0].map(c => c[0]).join('')
               + '|' + st.cards[1].map(c => c[0]).join('')
               + '|' + st.waitCard[0] + '|' + st.turn;
    }

    /** Destination squares for the piece at idx moving with `card`.
     *  Universal filter: on-board, not occupied by own piece (§2.4). */
    cardDests(st, idx, card) {
      const board = st.board;
      const { owner, facing } = board[idx];
      const r = Math.floor(idx / N), c = idx % N;
      const out = [];
      const tryTo = (nr, nc) => {
        if (nr >= 0 && nr < N && nc >= 0 && nc < N) {
          const t = board[nr * N + nc];
          if (t === null || t.owner !== owner) out.push(nr * N + nc);
        }
      };
      if (card === 'rook') {
        for (const [dr, dc] of ORTHO) tryTo(r + dr, c + dc);
      } else if (card === 'bishop') {
        for (const [dr, dc] of DIAG) tryTo(r + dr, c + dc);
      } else if (card === 'queen') {
        for (const [dr, dc] of ALL8) tryTo(r + dr, c + dc);
      } else if (card === 'knight') {
        for (const [dr, dc] of KNIGHT) tryTo(r + dr, c + dc);
      } else if (card === 'attacker') {
        // facing-dependent: 1 fwd (capture ok, A1), 2 fwd (only if the
        // square 1 fwd is empty — either colour blocks), 1 diag-fwd
        const [fr, fc] = DIRS[facing];
        tryTo(r + fr, c + fc);
        if (r + fr >= 0 && r + fr < N && c + fc >= 0 && c + fc < N
            && board[(r + fr) * N + (c + fc)] === null) {
          tryTo(r + 2 * fr, c + 2 * fc);
        }
        for (const side of [(facing + 1) % 4, (facing + 3) % 4]) {
          const [sr, sc] = DIRS[side];
          tryTo(r + fr + sr, c + fc + sc);
        }
      } else if (card === 'jumper') {
        // leap over any occupied neighbour (either colour, A2) and land
        // directly beyond; the leapt piece survives (A3)
        for (const [dr, dc] of ALL8) {
          const mr = r + dr, mc = c + dc;
          if (mr >= 0 && mr < N && mc >= 0 && mc < N && board[mr * N + mc] !== null) {
            tryTo(r + 2 * dr, c + 2 * dc);
          }
        }
      }
      return out;
    }

    legalMoves(st) {
      const player = st.turn, out = [];
      for (const card of st.cards[player]) {
        for (let i = 0; i < N * N; i++) {
          const p = st.board[i];
          if (p !== null && p.owner === player) {
            for (const to of this.cardDests(st, i, card)) out.push({ card, from: i, to });
          }
        }
      }
      return out;
    }

    hasMovesFor(st, player) {
      for (const card of st.cards[player]) {
        for (let i = 0; i < N * N; i++) {
          const p = st.board[i];
          if (p !== null && p.owner === player && this.cardDests(st, i, card).length) return true;
        }
      }
      return false;
    }

    /** The 180° rotation rule (A4/A5): after landing, a piece on the far
     *  edge in its current facing direction flips its facing. */
    rotateIfAtFacingEdge(st, idx) {
      const { owner, facing } = st.board[idx];
      const r = Math.floor(idx / N), c = idx % N;
      const [dr, dc] = DIRS[facing];
      if (!(r + dr >= 0 && r + dr < N && c + dc >= 0 && c + dc < N)) {
        st.board[idx] = { owner, facing: (facing + 2) % 4 };
      }
    }

    /** Queen upgrade (A8): at exactly 2 pieces total, the jumper card
     *  immediately becomes the queen wherever it sits. */
    upgradeJumperToQueen(st) {
      for (const pair of st.cards) {
        const i = pair.indexOf('jumper');
        if (i >= 0) { pair[i] = 'queen'; pair.sort(); }
      }
      if (st.waitCard === 'jumper') st.waitCard = 'queen';
    }

    applyMove(st, mv) {
      const player = st.turn;
      const board = st.board;
      const cap = board[mv.to];
      board[mv.to] = board[mv.from];
      board[mv.from] = null;
      if (cap !== null) {
        // a capture makes every earlier position unrepeatable
        st.reps = {};
      }
      this.rotateIfAtFacingEdge(st, mv.to);
      // card exchange: played card to the wait slot, wait card joins the pair
      const pair = st.cards[player];
      pair.splice(pair.indexOf(mv.card), 1);
      pair.push(st.waitCard);
      pair.sort();
      st.waitCard = mv.card;
      let total = 0;
      for (const p of board) if (p !== null) total++;
      if (total === 2) this.upgradeJumperToQueen(st);
      if (!board.some(p => p !== null && p.owner === 1 - player)) {
        st.winner = player; st.reason = 'capture-all';
        return;
      }
      st.turn = 1 - player;
      const key = this.posKey(st);
      const n = (st.reps[key] || 0) + 1;
      st.reps[key] = n;
      if (n >= 3) {
        st.winner = 2; st.reason = 'repetition';
        return;
      }
      // stalemate (A6): the player to move has no legal move with either card
      if (!this.hasMovesFor(st, st.turn)) { st.winner = 2; st.reason = 'stalemate'; }
    }

    countDests(st, player) {
      let n = 0;
      for (const card of st.cards[player]) {
        for (let i = 0; i < N * N; i++) {
          const p = st.board[i];
          if (p !== null && p.owner === player) n += this.cardDests(st, i, card).length;
        }
      }
      return n;
    }

    /** True if any enemy piece lies strictly ahead of idx's facing. */
    enemyAhead(st, idx) {
      const { owner, facing } = st.board[idx];
      const r = Math.floor(idx / N), c = idx % N;
      const [dr, dc] = DIRS[facing];
      for (let j = 0; j < N * N; j++) {
        const p = st.board[j];
        if (p !== null && p.owner !== owner) {
          if (dr * (Math.floor(j / N) - r) + dc * (j % N - c) > 0) return true;
        }
      }
      return false;
    }

    /** Material-dominant heuristic; mobility makes the search reason about
     *  the card-exchange cycle, facing about the rotation rule. */
    evaluate(st, me) {
      let s = 0;
      for (let i = 0; i < N * N; i++) {
        const p = st.board[i];
        if (p === null) continue;
        const r = Math.floor(i / N), c = i % N;
        let v = MATERIAL + 2 * (2 - Math.max(Math.abs(r - 2), Math.abs(c - 2)));
        if (this.enemyAhead(st, i)) v += FACE_BONUS;
        s += p.owner === me ? v : -v;
      }
      for (const pl of [0, 1]) {
        let cv = 0;
        for (const cd of st.cards[pl]) cv += CARD_VAL[cd];
        cv += MOBILITY * this.countDests(st, pl);
        s += pl === me ? cv : -cv;
      }
      return s;
    }

    // captures first — helps alpha-beta cut early
    orderMoves(st, moves) {
      return moves.sort((a, b) =>
        (st.board[a.to] !== null ? -1 : 0) - (st.board[b.to] !== null ? -1 : 0));
    }

    /** All 30 unconstrained 2/2/1 assignments (A9) as draft objects. */
    allDrafts(drafter = 1) {
      const out = [];
      for (let i = 0; i < 5; i++) {
        for (let j = i + 1; j < 5; j++) {
          const own = [CARDS[i], CARDS[j]];
          const rest = CARDS.filter(cd => !own.includes(cd));
          for (let k = 0; k < 3; k++) {
            const opp = rest.filter((_, m) => m !== k);
            const cards = [null, null];
            cards[drafter] = own;
            cards[1 - drafter] = opp;
            out.push({ cards: [cards[0], cards[1]], waitCard: rest[k] });
          }
        }
      }
      return out;
    }
  }

  return CardChess;
})();

/**
 * Black's draft policy (§3.5): score each of the 30 assignments with a
 * shallow negamax from white's opening position (drafter value = -best)
 * and pick the best, with the same Gaussian-margin mistake model the move
 * search uses. Mirrors choose_draft in py/card_chess.py. Needs the global
 * Negamax agent (core/negamax.js) loaded.
 */
function chooseCardChessDraft(engine, opts = {}) {
  const maxDepth = opts.maxDepth ?? 3;
  const timeMs = opts.timeMs ?? 150;
  const marginMean = opts.marginMean ?? 0;
  const marginStd = opts.marginStd ?? 0;
  const scored = [];
  for (const d of engine.allDrafts(1)) {
    const st = engine.initialState(0, d);
    const stats = {};
    Negamax.chooseMove(engine, st, { maxDepth, timeMs, stats });
    scored.push([d, -(stats.best || 0)]);
  }
  scored.sort((a, b) => b[1] - a[1]);
  if (marginMean > 0 || marginStd > 0) {
    const u = 1 - Math.random(), v = Math.random();
    const margin = Math.abs(marginMean
      + marginStd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v));
    const pool = scored.filter(([, sc]) => sc >= scored[0][1] - margin);
    return pool[Math.floor(Math.random() * pool.length)][0];
  }
  return scored[0][0];
}
