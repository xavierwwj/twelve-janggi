"""Twelve Janggi (십이장기) engine — implements the API in engine_api.py.

Mirrors games/twelve-janggi/engine.js line for line; both must stay
rule-identical. State is a plain dict (same shape as the JS state):
  {'board': [None | (type, owner)] * 12, 'hands': [[...], [...]],
   'turn': 0|1, 'pending_try': None|0|1, 'winner': None|0|1, 'reason': str|None}

Moves: {'from': i, 'to': j} | {'drop': piece_type, 'to': j}. Board squares
are indexed row-major 0..11 with row 0 at the top; player 0 sits at the
bottom. Rules per The Genius: Black Garnet — see README.
"""

ROWS, COLS = 4, 3

# move directions for player 0 (bottom, forward = -1 row)
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


def initial_state(first=0):
    board = [None] * (ROWS * COLS)

    def put(r, c, t, o):
        board[r * COLS + c] = (t, o)

    put(3, 0, 'sang', 0); put(3, 1, 'wang', 0); put(3, 2, 'jang', 0); put(2, 1, 'ja', 0)
    put(0, 2, 'sang', 1); put(0, 1, 'wang', 1); put(0, 0, 'jang', 1); put(1, 1, 'ja', 1)
    return {
        'board': board, 'hands': [[], []], 'turn': first,
        'pending_try': None,  # player whose wang sits in enemy territory awaiting survival
        'winner': None, 'reason': None,
    }


def clone_state(st):
    return {
        'board': list(st['board']),
        'hands': [list(st['hands'][0]), list(st['hands'][1])],
        'turn': st['turn'], 'pending_try': st['pending_try'],
        'winner': st['winner'], 'reason': st['reason'],
    }


def dirs_for(piece_type, owner):
    base = MOVES[piece_type]
    return base if owner == 0 else tuple((-r, -c) for r, c in base)


def piece_moves_at(st, idx):
    p = st['board'][idx]
    if p is None:
        return []
    t, owner = p
    r, c = divmod(idx, COLS)
    out = []
    for dr, dc in dirs_for(t, owner):
        nr, nc = r + dr, c + dc
        if not (0 <= nr < ROWS and 0 <= nc < COLS):
            continue
        tgt = st['board'][nr * COLS + nc]
        if tgt is not None and tgt[1] == owner:
            continue
        out.append(nr * COLS + nc)
    return out


def drop_idxs(st, player):
    forbidden = goal_row(player)
    return [i for i, p in enumerate(st['board'])
            if p is None and i // COLS != forbidden]


def legal_moves(st):
    player = st['turn']
    out = []
    for i, p in enumerate(st['board']):
        if p is not None and p[1] == player:
            for to in piece_moves_at(st, i):
                out.append({'from': i, 'to': to})
    if st['hands'][player]:
        empties = drop_idxs(st, player)
        for t in sorted(set(st['hands'][player])):
            for to in empties:
                out.append({'drop': t, 'to': to})
    return out


def has_move_for(st, player):
    if st['hands'][player] and drop_idxs(st, player):
        return True
    return any(p is not None and p[1] == player and piece_moves_at(st, i)
               for i, p in enumerate(st['board']))


def apply_move(st, mv):
    """Apply a legal move; resolves promotion, the try rule, and wins."""
    player = st['turn']
    king_captured = False
    if 'drop' in mv:
        st['hands'][player].remove(mv['drop'])
        st['board'][mv['to']] = (mv['drop'], player)
    else:
        p = st['board'][mv['from']]
        cap = st['board'][mv['to']]
        st['board'][mv['to']] = p
        st['board'][mv['from']] = None
        if cap is not None:
            if cap[0] == 'wang':
                king_captured = True
            st['hands'][player].append('ja' if cap[0] == 'hu' else cap[0])
        if p[0] == 'ja' and mv['to'] // COLS == goal_row(player):
            st['board'][mv['to']] = ('hu', player)

    if king_captured:
        st['winner'], st['reason'] = player, 'capture'
        return
    # opponent's wang entered our territory last turn and we failed to take it
    if st['pending_try'] is not None and st['pending_try'] != player:
        st['winner'], st['reason'] = st['pending_try'], 'reach'
        return
    st['pending_try'] = None
    for i, p in enumerate(st['board']):
        if p == ('wang', player) and i // COLS == goal_row(player):
            st['pending_try'] = player
            break
    st['turn'] = 1 - player
    if not has_move_for(st, st['turn']):
        st['winner'], st['reason'] = player, 'stuck'


# ---- search heuristics (part of the engine: game knowledge lives here) ----

VAL = {'ja': 10, 'sang': 30, 'jang': 34, 'hu': 46, 'wang': 0}
HAND_VAL = {'ja': 9, 'sang': 28, 'jang': 32}


def evaluate(st, me):
    """Kings score 0: king loss and the try rule are terminal states the
    search sees directly."""
    s = 0
    for i, p in enumerate(st['board']):
        if p is None:
            continue
        t, owner = p
        v = VAL[t]
        if t == 'ja':
            v += 2 * ((3 - i // COLS) if owner == 0 else (i // COLS))
        s += v if owner == me else -v
    for owner in (0, 1):
        hv = sum(HAND_VAL[t] for t in st['hands'][owner])
        s += hv if owner == me else -hv
    return s


def order_moves(st, moves):
    """Captures first, biggest victim first — helps alpha-beta cut early."""
    def key(mv):
        if 'drop' not in mv:
            cap = st['board'][mv['to']]
            if cap is not None:
                return -(10_000 if cap[0] == 'wang' else VAL[cap[0]])
        return 0
    return sorted(moves, key=key)


# ---- display metadata (mirrors games/twelve-janggi/engine.js `rules`) ----

RULES = {
    'title': 'Twelve Janggi 십이장기',
    'sections': [
        {'heading': 'Setup', 'items': [
            '3×4 board. The row nearest each player is their territory. Each side starts with '
            '相 · 王 · 將 on their territory row and a 子 in front of the king.']},
        {'heading': 'Pieces', 'table': {
            'headers': ['Piece', 'Name', 'Movement'],
            'rows': [
                ['王', 'king (왕)', '1 step, any direction'],
                ['將', 'general (장)', '1 step orthogonally'],
                ['相', 'minister (상)', '1 step diagonally'],
                ['子', 'man (자)', '1 step forward'],
                ['侯', 'feudal lord (후)', '1 step any direction except diagonally backward'],
            ]},
            'note': 'The red dots on each tile show its move directions.'},
        {'heading': 'Captures & drops', 'items': [
            'Moving onto an enemy piece captures it into your hand (a captured 侯 reverts to 子).',
            'Instead of moving, you may drop a hand piece onto any empty square '
            'outside the opponent\'s territory.',
            'A 子 that moves into the opponent\'s territory promotes to 侯.']},
        {'heading': 'Win conditions', 'ordered': True, 'items': [
            'Capture the enemy 王.',
            'Move your own 王 into the opponent\'s territory and survive your opponent\'s next move.',
            'Your opponent has no legal move.']},
    ],
}
