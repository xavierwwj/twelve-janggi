"""Card Chess (카드 체스) — a GameEngine subclass (see engine_api.py).

The Genius death match: 5x5 board, 5 identical pieces per side, and five
Onitama-style movement cards (rook / bishop / attacker / knight / jumper).
Black (player 1) drafts all five cards 2-2-1 before the game; white
(player 0) moves first. Playing a card swaps it with the single
sitting-out wait card. Capture all enemy pieces to win.

Mirrors games/card-chess/engine.js line for line; both must stay
rule-identical. State is a plain dict (same shape as the JS state):
  {'board': [None | (owner, facing)] * 25,
   'cards': [[c, c], [c, c]],      # each pair kept sorted (canonical)
   'wait_card': c,                 # the single sitting-out card
   'turn': 0|1, 'winner': None|0|1|2, 'reason': str|None,
   'reps': {position_key: count}}  # threefold-repetition bookkeeping

winner 2 means a draw (reason 'stalemate' | 'repetition'). The reused
negamax agent only knows win/lose terminals, so in search a draw scores
as a loss for the side whose move created it — the AI plays to avoid
draws. Documented convention; identical in both mirrors.

Moves: {'card': c, 'from': i, 'to': j}. Board squares are indexed
row-major 0..24 with row 0 at the top; player 0 (white) starts on the
bottom row facing up, player 1 (black) on the top row facing down.
Facing: 0 = up (-row), 1 = right, 2 = down, 3 = left.
"""

from engine_api import GameEngine

CARDS = ('rook', 'bishop', 'attacker', 'knight', 'jumper')


class CardChess(GameEngine):
    N = 5

    DIRS = ((-1, 0), (0, 1), (1, 0), (0, -1))  # facing 0..3 = up/right/down/left
    ORTHO = ((-1, 0), (0, 1), (1, 0), (0, -1))
    DIAG = ((-1, -1), (-1, 1), (1, -1), (1, 1))
    ALL8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    KNIGHT = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))

    # default draft so headless tooling can run without a draft phase
    DEFAULT_DRAFT = {'cards': [['bishop', 'rook'], ['attacker', 'knight']],
                     'wait_card': 'jumper'}

    # search heuristics (starting points, roughly tuned by self-play)
    MATERIAL = 100
    CARD_VAL = {'attacker': 10, 'bishop': 8, 'jumper': 4,
                'knight': 12, 'queen': 16, 'rook': 8}
    MOBILITY = 2     # per destination a held card offers
    FACE_BONUS = 3   # per piece with at least one enemy ahead of its facing

    def initial_state(self, first=0, draft=None):
        d = draft if draft is not None else self.DEFAULT_DRAFT
        board = [None] * (self.N * self.N)
        for c in range(self.N):
            board[(self.N - 1) * self.N + c] = (0, 0)  # white, facing up
            board[c] = (1, 2)                          # black, facing down
        st = {
            'board': board,
            'cards': [sorted(d['cards'][0]), sorted(d['cards'][1])],
            'wait_card': d['wait_card'],
            'turn': first, 'winner': None, 'reason': None,
            'reps': {},
        }
        st['reps'][self.pos_key(st)] = 1
        return st

    def clone_state(self, st):
        return {
            'board': list(st['board']),
            'cards': [list(st['cards'][0]), list(st['cards'][1])],
            'wait_card': st['wait_card'],
            'turn': st['turn'], 'winner': st['winner'], 'reason': st['reason'],
            'reps': dict(st['reps']),
        }

    def pos_key(self, st):
        """Full-position key for threefold repetition (A7): board incl.
        facings + card distribution incl. wait card + side to move."""
        b = ''.join('.' if p is None else 'abcdefgh'[p[0] * 4 + p[1]]
                    for p in st['board'])
        return (b + '|' + ''.join(c[0] for c in st['cards'][0])
                  + '|' + ''.join(c[0] for c in st['cards'][1])
                  + '|' + st['wait_card'][0] + '|' + str(st['turn']))

    def card_dests(self, st, idx, card):
        """Destination squares for the piece at idx moving with `card`.
        Universal filter: on-board, not occupied by own piece (§2.4)."""
        N = self.N
        board = st['board']
        owner, facing = board[idx]
        r, c = divmod(idx, N)
        out = []

        def try_to(nr, nc):
            if 0 <= nr < N and 0 <= nc < N:
                t = board[nr * N + nc]
                if t is None or t[0] != owner:
                    out.append(nr * N + nc)

        if card == 'rook':
            for dr, dc in self.ORTHO:
                try_to(r + dr, c + dc)
        elif card == 'bishop':
            for dr, dc in self.DIAG:
                try_to(r + dr, c + dc)
        elif card == 'queen':
            for dr, dc in self.ALL8:
                try_to(r + dr, c + dc)
        elif card == 'knight':
            for dr, dc in self.KNIGHT:
                try_to(r + dr, c + dc)
        elif card == 'attacker':
            # facing-dependent: 1 fwd (capture ok, A1), 2 fwd (only if the
            # square 1 fwd is empty — either colour blocks), 1 diag-fwd
            fr, fc = self.DIRS[facing]
            try_to(r + fr, c + fc)
            if (0 <= r + fr < N and 0 <= c + fc < N
                    and board[(r + fr) * N + (c + fc)] is None):
                try_to(r + 2 * fr, c + 2 * fc)
            for side in ((facing + 1) % 4, (facing + 3) % 4):
                sr, sc = self.DIRS[side]
                try_to(r + fr + sr, c + fc + sc)
        elif card == 'jumper':
            # leap over any occupied neighbour (either colour, A2) and land
            # directly beyond; the leapt piece survives (A3)
            for dr, dc in self.ALL8:
                mr, mc = r + dr, c + dc
                if 0 <= mr < N and 0 <= mc < N and board[mr * N + mc] is not None:
                    try_to(r + 2 * dr, c + 2 * dc)
        return out

    def legal_moves(self, st):
        player = st['turn']
        out = []
        for card in st['cards'][player]:
            for i, p in enumerate(st['board']):
                if p is not None and p[0] == player:
                    for to in self.card_dests(st, i, card):
                        out.append({'card': card, 'from': i, 'to': to})
        return out

    def has_moves_for(self, st, player):
        for card in st['cards'][player]:
            for i, p in enumerate(st['board']):
                if p is not None and p[0] == player and self.card_dests(st, i, card):
                    return True
        return False

    def rotate_if_at_facing_edge(self, st, idx):
        """The 180° rotation rule (A4/A5): after landing, a piece on the far
        edge in its current facing direction flips its facing."""
        N = self.N
        owner, facing = st['board'][idx]
        r, c = divmod(idx, N)
        dr, dc = self.DIRS[facing]
        if not (0 <= r + dr < N and 0 <= c + dc < N):
            st['board'][idx] = (owner, (facing + 2) % 4)

    def upgrade_jumper_to_queen(self, st):
        """Queen upgrade (A8): at exactly 2 pieces total, the jumper card
        immediately becomes the queen wherever it sits."""
        for pair in st['cards']:
            if 'jumper' in pair:
                pair[pair.index('jumper')] = 'queen'
                pair.sort()
        if st['wait_card'] == 'jumper':
            st['wait_card'] = 'queen'

    def apply_move(self, st, mv):
        player = st['turn']
        board = st['board']
        cap = board[mv['to']]
        board[mv['to']] = board[mv['from']]
        board[mv['from']] = None
        if cap is not None:
            # a capture makes every earlier position unrepeatable
            st['reps'] = {}
        self.rotate_if_at_facing_edge(st, mv['to'])
        # card exchange: played card to the wait slot, wait card joins the pair
        pair = st['cards'][player]
        pair.remove(mv['card'])
        pair.append(st['wait_card'])
        pair.sort()
        st['wait_card'] = mv['card']
        total = sum(1 for p in board if p is not None)
        if total == 2:
            self.upgrade_jumper_to_queen(st)
        if not any(p is not None and p[0] == 1 - player for p in board):
            st['winner'], st['reason'] = player, 'capture-all'
            return
        st['turn'] = 1 - player
        key = self.pos_key(st)
        n = st['reps'].get(key, 0) + 1
        st['reps'][key] = n
        if n >= 3:
            st['winner'], st['reason'] = 2, 'repetition'
            return
        # stalemate (A6): the player to move has no legal move with either card
        if not self.has_moves_for(st, st['turn']):
            st['winner'], st['reason'] = 2, 'stalemate'

    def count_dests(self, st, player):
        n = 0
        for card in st['cards'][player]:
            for i, p in enumerate(st['board']):
                if p is not None and p[0] == player:
                    n += len(self.card_dests(st, i, card))
        return n

    def enemy_ahead(self, st, idx):
        """True if any enemy piece lies strictly ahead of idx's facing."""
        N = self.N
        owner, facing = st['board'][idx]
        r, c = divmod(idx, N)
        dr, dc = self.DIRS[facing]
        for j, p in enumerate(st['board']):
            if p is not None and p[0] != owner:
                jr, jc = divmod(j, N)
                if dr * (jr - r) + dc * (jc - c) > 0:
                    return True
        return False

    def evaluate(self, st, me):
        """Material-dominant heuristic; mobility makes the search reason
        about the card-exchange cycle, facing about the rotation rule."""
        N = self.N
        s = 0
        for i, p in enumerate(st['board']):
            if p is None:
                continue
            r, c = divmod(i, N)
            v = self.MATERIAL + 2 * (2 - max(abs(r - 2), abs(c - 2)))
            if self.enemy_ahead(st, i):
                v += self.FACE_BONUS
            s += v if p[0] == me else -v
        for pl in (0, 1):
            cv = sum(self.CARD_VAL[cd] for cd in st['cards'][pl])
            cv += self.MOBILITY * self.count_dests(st, pl)
            s += cv if pl == me else -cv
        return s

    def order_moves(self, st, moves):
        """Captures first — helps alpha-beta cut early."""
        return sorted(moves, key=lambda mv: -1 if st['board'][mv['to']] is not None else 0)

    def all_drafts(self, drafter=1):
        """All 30 unconstrained 2/2/1 assignments (A9) as draft dicts."""
        out = []
        for i in range(5):
            for j in range(i + 1, 5):
                own = [CARDS[i], CARDS[j]]
                rest = [cd for cd in CARDS if cd not in own]
                for k in range(3):
                    opp = [rest[m] for m in range(3) if m != k]
                    cards = [None, None]
                    cards[drafter] = own
                    cards[1 - drafter] = opp
                    out.append({'cards': [cards[0], cards[1]], 'wait_card': rest[k]})
        return out


def choose_draft(engine, max_depth=3, time_ms=150, margin_mean=0, margin_std=0):
    """Black's draft policy (§3.5): score each of the 30 assignments with a
    shallow negamax from white's opening position (drafter value = -best)
    and pick the best, with the same Gaussian-margin mistake model the
    move search uses. Mirrors chooseDraft in games/card-chess/engine.js."""
    import random
    import negamax
    scored = []
    for d in engine.all_drafts(1):
        st = engine.initial_state(0, d)
        stats = {}
        negamax.choose_move(engine, st, max_depth=max_depth, time_ms=time_ms,
                            stats=stats)
        scored.append((d, -stats.get('best', 0)))
    scored.sort(key=lambda x: -x[1])
    if margin_mean > 0 or margin_std > 0:
        margin = abs(random.gauss(margin_mean, margin_std))
        pool = [x for x in scored if x[1] >= scored[0][1] - margin]
        return random.choice(pool)[0]
    return scored[0][0]


# display metadata (mirrors games/card-chess/engine.js `rules`)
CardChess.RULES = {
    'title': 'Card Chess 카드 체스',
    'sections': [
        {'heading': 'Setup', 'items': [
            '5×5 board, 5 identical pieces per side. White fills the bottom row, '
            'black the top row, every piece facing the enemy (the yellow arrow).',
            'Black alone drafts the five movement cards before the game: '
            '2 to itself, 2 to white, 1 to the wait slot. White moves first.']},
        {'heading': 'Your turn', 'items': [
            'Play one of your two cards: move one of your pieces to a square that '
            'card allows. Landing on an enemy piece captures it (no drops).',
            'Your played card goes to the wait slot and the waiting card joins '
            'your hand — you always hold exactly two.']},
        {'heading': 'Cards', 'table': {
            'headers': ['Card', 'Moves'],
            'rows': [
                ['Rook 룩', '1 step orthogonally'],
                ['Bishop 비숍', '1 step diagonally'],
                ['Attacker 어태커', '1 or 2 straight ahead (2 only if the square ahead '
                 'is empty), or 1 diagonally ahead — follows the facing arrow'],
                ['Knight 나이트', 'chess knight jump'],
                ['Jumper 점퍼', 'leap over any adjacent piece (either colour), landing '
                 'directly beyond; the leapt piece is not captured'],
                ['Queen 퀸', '1 step any direction — the Jumper becomes the Queen '
                 'the moment only 2 pieces remain on the board'],
            ]}},
        {'heading': 'Facing & rotation', 'items': [
            'Only the Attacker moves relative to facing, but every piece always '
            'shows one.',
            'A piece that lands on the far edge it is facing turns 180° — any '
            "card's move can trigger this, and later flips back are possible."]},
        {'heading': 'Game end', 'items': [
            'Capture all enemy pieces to win — the only win condition.',
            'No legal move with either card = stalemate (draw).',
            'The same full position (board, facings, cards, side to move) '
            'occurring three times = draw.']},
    ],
}
