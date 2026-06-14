"""Black and White (흑과 백) — game logic.

The Genius death match: a *simultaneous*, *hidden-information* game. This is
deliberately NOT a GameEngine subclass — that interface (engine_api.py) is for
perfect-information, alternating-turn games driven by negamax. Here both
players move at once and never see each other's exact numbers, so the logic
is split into mutate-the-truth functions (server-only) and `observe()`, which
returns the masked view a single player is allowed to see.

Each player holds tiles 0..8 — even are black (0,2,4,6,8), odd are white
(1,3,5,7). Over 9 rounds both secretly play one tile; the higher number wins
a point, ties score nothing. Only each tile's COLOUR (parity) and the round
result are ever revealed; exact numbers stay hidden, even afterward. Most
points after 9 rounds wins; equal points is a draw.

Full (server-side) state — never sent to a client as-is:
  {'hands': [[..], [..]],      # remaining tiles per player
   'scores': [int, int],
   'round': 1..9,              # current round number (1-based)
   'locked': [tile|None, tile|None],   # tiles chosen this round
   'history': [{'tiles': [t0, t1], 'winner': 0|1|None}, ...],
   'winner': None | 0 | 1 | 'draw'}
"""

ROUNDS = 9
TILES = tuple(range(9))  # 0..8


def color(tile):
    return 'black' if tile % 2 == 0 else 'white'


def initial_state():
    return {
        'hands': [list(TILES), list(TILES)],
        'scores': [0, 0],
        'round': 1,
        'locked': [None, None],
        'history': [],
        'winner': None,
        # who must lock first this round: the previous round's winner, or None
        # in round 1 and after a tie (both play simultaneously then).
        'leader': None,
    }


def can_lock(state, player):
    """Whether `player` may lock right now. In a led round the responder must
    wait until the leader has committed (then they see the leader's colour)."""
    if state['locked'][player] is not None:
        return False
    leader = state['leader']
    if leader is None or player == leader:
        return True
    return state['locked'][leader] is not None  # responder waits for the leader


def lock(state, player, tile):
    """Record `player`'s tile for the current round. Raises ValueError on an
    illegal choice (game over, not your turn, not in hand, or already locked)."""
    if state['winner'] is not None:
        raise ValueError('game over')
    if state['locked'][player] is not None:
        raise ValueError('already locked this round')
    if not can_lock(state, player):
        raise ValueError('wait for your opponent to lead')
    if tile not in state['hands'][player]:
        raise ValueError('tile not in hand')
    state['locked'][player] = tile


def both_locked(state):
    return state['locked'][0] is not None and state['locked'][1] is not None


def resolve_round(state):
    """Score the current round from both locked tiles, advance, and decide the
    game if it is now settled. Assumes both players have locked."""
    t0, t1 = state['locked']
    state['hands'][0].remove(t0)
    state['hands'][1].remove(t1)
    winner = 0 if t0 > t1 else 1 if t1 > t0 else None
    if winner is not None:
        state['scores'][winner] += 1
    state['history'].append({'tiles': [t0, t1], 'winner': winner})
    state['locked'] = [None, None]
    state['round'] = len(state['history']) + 1
    state['leader'] = winner  # next round: the winner leads (None after a tie)
    _decide(state)


def _decide(state):
    s0, s1 = state['scores']
    remaining = ROUNDS - len(state['history'])
    if s0 > s1 + remaining:          # opponent can no longer catch up
        state['winner'] = 0
    elif s1 > s0 + remaining:
        state['winner'] = 1
    elif remaining == 0:
        state['winner'] = 0 if s0 > s1 else 1 if s1 > s0 else 'draw'


def observe(state, player):
    """The masked view player `player` is allowed to see. The opponent's past
    tiles appear only as colours; their current locked tile, only as a flag."""
    opp = 1 - player
    history = []
    for h in state['history']:
        mine, theirs = h['tiles'][player], h['tiles'][opp]
        if h['winner'] is None:
            result = 'tie'
        elif h['winner'] == player:
            result = 'win'
        else:
            result = 'lose'
        history.append({'your_tile': mine, 'opp_color': color(theirs), 'result': result})

    if state['winner'] in (player,):
        outcome = 'you'
    elif state['winner'] == opp:
        outcome = 'opp'
    else:
        outcome = state['winner']  # 'draw' or None

    # the committed tile is reported separately (you_locked), not in the hand
    locked_tile = state['locked'][player]
    hand = sorted(t for t in state['hands'][player] if t != locked_tile)

    leader = state['leader']
    leader_view = 'you' if leader == player else ('opp' if leader is not None else None)
    # as the responder, you see the leader's colour once they've committed
    leader_color = None
    if leader is not None and player != leader and state['locked'][leader] is not None:
        leader_color = color(state['locked'][leader])

    return {
        'your_hand': hand,
        'your_score': state['scores'][player],
        'opp_score': state['scores'][opp],
        'round': state['round'],
        'rounds': ROUNDS,
        'you_locked': state['locked'][player],          # your tile, or None
        'opp_locked': state['locked'][opp] is not None,  # boolean only
        'history': history,
        'winner': outcome,                               # 'you'|'opp'|'draw'|None
        'leader': leader_view,                           # 'you'|'opp'|None
        'your_turn': can_lock(state, player),            # may you lock right now
        'leader_color': leader_color,                    # opp's colour if responding
    }
