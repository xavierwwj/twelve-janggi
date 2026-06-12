"""Twelve Janggi (십이장기) rules engine.

Rules per The Genius: Black Garnet (a Dobutsu Shogi variant):
  - 4x3 board. Player 0 sits at the bottom (rows count down toward 0),
    player 1 at the top. Each player's territory is the row closest to them.
  - Pieces: wang 王 (any direction), jang 將 (orthogonal), sang 相 (diagonal),
    ja 子 (forward only), hu 侯 (promoted ja: any direction except diagonally
    backward).
  - A ja that moves into the opponent's territory promotes to hu.
  - Captured pieces join the capturer's hand (hu reverts to ja) and may be
    dropped on any empty square outside the opponent's territory.
  - Win by capturing the enemy wang, or by moving your own wang into the
    opponent's territory and surviving one opposing turn. A player with no
    legal move loses (house rule; effectively unreachable in normal play).

Moves are tuples: ('m', from_idx, to_idx) or ('d', piece_type, to_idx).
Board squares are indexed row-major, 0..11, row 0 at the top.
"""

ROWS, COLS = 4, 3

# Move directions for player 0 (bottom side, forward = -1 row).
# Player 1's directions are these negated.
MOVES = {
    'wang': ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)),
    'jang': ((-1, 0), (1, 0), (0, -1), (0, 1)),
    'sang': ((-1, -1), (-1, 1), (1, -1), (1, 1)),
    'ja':   ((-1, 0),),
    'hu':   ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0)),
}


def goal_row(owner):
    """The opponent-territory row that `owner` wants to reach."""
    return 0 if owner == 0 else ROWS - 1


class Game:
    def __init__(self, first=0):
        self.board = [None] * (ROWS * COLS)  # entries: (type, owner) tuples

        def put(r, c, t, o):
            self.board[r * COLS + c] = (t, o)

        put(3, 0, 'sang', 0); put(3, 1, 'wang', 0); put(3, 2, 'jang', 0); put(2, 1, 'ja', 0)
        put(0, 2, 'sang', 1); put(0, 1, 'wang', 1); put(0, 0, 'jang', 1); put(1, 1, 'ja', 1)
        self.hands = [[], []]
        self.turn = first
        self.pending_try = None  # player whose wang sits in enemy territory awaiting survival
        self.winner = None
        self.reason = None       # 'capture' | 'reach' | 'stuck'

    def copy(self):
        g = Game.__new__(Game)
        g.board = list(self.board)
        g.hands = [list(self.hands[0]), list(self.hands[1])]
        g.turn = self.turn
        g.pending_try = self.pending_try
        g.winner = self.winner
        g.reason = self.reason
        return g

    @staticmethod
    def dirs(piece_type, owner):
        base = MOVES[piece_type]
        return base if owner == 0 else tuple((-r, -c) for r, c in base)

    def piece_moves(self, idx):
        p = self.board[idx]
        if p is None:
            return []
        t, owner = p
        r, c = divmod(idx, COLS)
        out = []
        for dr, dc in self.dirs(t, owner):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < ROWS and 0 <= nc < COLS):
                continue
            tgt = self.board[nr * COLS + nc]
            if tgt is not None and tgt[1] == owner:
                continue
            out.append(nr * COLS + nc)
        return out

    def legal_moves(self, player=None):
        player = self.turn if player is None else player
        moves = []
        for i, p in enumerate(self.board):
            if p is not None and p[1] == player:
                for to in self.piece_moves(i):
                    moves.append(('m', i, to))
        if self.hands[player]:
            forbidden = goal_row(player)
            empties = [i for i, p in enumerate(self.board)
                       if p is None and i // COLS != forbidden]
            for t in sorted(set(self.hands[player])):
                for to in empties:
                    moves.append(('d', t, to))
        return moves

    def has_move(self, player):
        if self.hands[player]:
            forbidden = goal_row(player)
            if any(p is None and i // COLS != forbidden for i, p in enumerate(self.board)):
                return True
        return any(p is not None and p[1] == player and self.piece_moves(i)
                   for i, p in enumerate(self.board))

    def apply(self, mv):
        """Apply a legal move and resolve promotion, the try rule, and wins."""
        player = self.turn
        king_captured = False
        if mv[0] == 'm':
            _, frm, to = mv
            p = self.board[frm]
            cap = self.board[to]
            self.board[to] = p
            self.board[frm] = None
            if cap is not None:
                if cap[0] == 'wang':
                    king_captured = True
                self.hands[player].append('ja' if cap[0] == 'hu' else cap[0])
            if p[0] == 'ja' and to // COLS == goal_row(player):
                self.board[to] = ('hu', player)
        else:
            _, t, to = mv
            self.hands[player].remove(t)
            self.board[to] = (t, player)

        if king_captured:
            self.winner, self.reason = player, 'capture'
            return
        # opponent's wang entered our territory last turn and we failed to take it
        if self.pending_try is not None and self.pending_try != player:
            self.winner, self.reason = self.pending_try, 'reach'
            return
        self.pending_try = None
        for i, p in enumerate(self.board):
            if p == ('wang', player) and i // COLS == goal_row(player):
                self.pending_try = player
                break
        self.turn = 1 - player
        if not self.has_move(self.turn):
            self.winner, self.reason = player, 'stuck'
