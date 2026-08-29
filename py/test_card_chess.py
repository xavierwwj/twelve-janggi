"""Unit tests for Card Chess — the blueprint's §7 checklist.

    python3 -m unittest test_card_chess -v
"""

import random
import unittest

import negamax
from card_chess import CARDS, CardChess, choose_draft

E = CardChess()
N = CardChess.N


def sq(r, c):
    return r * N + c


def mk(pieces, cards, wait, turn=0):
    """Craft a state: pieces = {(r, c): (owner, facing)}."""
    st = E.initial_state(turn)
    st['board'] = [None] * (N * N)
    for (r, c), p in pieces.items():
        st['board'][sq(r, c)] = p
    st['cards'] = [sorted(cards[0]), sorted(cards[1])]
    st['wait_card'] = wait
    st['reps'] = {E.pos_key(st): 1}
    return st


def dests(st, r, c, card):
    return sorted(E.card_dests(st, sq(r, c), card))


class TestSetup(unittest.TestCase):
    def test_initial_position(self):                              # checklist 1
        st = E.initial_state()
        self.assertEqual(st['turn'], 0)
        for c in range(N):
            self.assertEqual(st['board'][sq(4, c)], (0, 0))  # white faces up
            self.assertEqual(st['board'][sq(0, c)], (1, 2))  # black faces down
        self.assertEqual(sum(p is not None for p in st['board']), 10)
        self.assertEqual(sorted(st['cards'][0] + st['cards'][1] + [st['wait_card']]),
                         sorted(CARDS))

    def test_card_cycle_first_turns(self):                        # checklist 2
        d = {'cards': [['rook', 'bishop'], ['attacker', 'knight']],
             'wait_card': 'jumper'}
        st = E.initial_state(0, d)
        E.apply_move(st, {'card': 'rook', 'from': sq(4, 0), 'to': sq(3, 0)})
        # white receives the draft leftover; rook now waits
        self.assertEqual(st['cards'][0], ['bishop', 'jumper'])
        self.assertEqual(st['wait_card'], 'rook')
        E.apply_move(st, {'card': 'knight', 'from': sq(0, 0), 'to': sq(2, 1)})
        # black receives the card white just played
        self.assertEqual(st['cards'][1], ['attacker', 'rook'])
        self.assertEqual(st['wait_card'], 'knight')


class TestSimpleCards(unittest.TestCase):
    def test_rook_bishop_center_edges_blocking(self):             # checklist 3
        st = mk({(2, 2): (0, 0), (0, 0): (1, 2)},
                [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        self.assertEqual(dests(st, 2, 2, 'rook'),
                         sorted([sq(1, 2), sq(3, 2), sq(2, 1), sq(2, 3)]))
        self.assertEqual(dests(st, 2, 2, 'bishop'),
                         sorted([sq(1, 1), sq(1, 3), sq(3, 1), sq(3, 3)]))
        # own piece blocks; enemy is capturable; edges pruned
        st2 = mk({(0, 0): (0, 0), (0, 1): (0, 0), (1, 0): (1, 2)},
                 [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        self.assertEqual(dests(st2, 0, 0, 'rook'), [sq(1, 0)])  # capture only
        self.assertEqual(dests(st2, 0, 0, 'bishop'), [sq(1, 1)])

    def test_knight(self):                                        # checklist 6
        pieces = {(2, 2): (0, 0)}
        # crowd every adjacent square — the knight jumps over them
        for dr, dc in CardChess.ALL8:
            pieces[(2 + dr, 2 + dc)] = (1, 2)
        st = mk(pieces, [['knight', 'rook'], ['bishop', 'attacker']], 'jumper')
        self.assertEqual(len(dests(st, 2, 2, 'knight')), 8)
        st2 = mk({(0, 0): (0, 0)}, [['knight', 'rook'], ['bishop', 'attacker']], 'jumper')
        self.assertEqual(dests(st2, 0, 0, 'knight'), sorted([sq(1, 2), sq(2, 1)]))


class TestAttacker(unittest.TestCase):                            # checklist 4
    CARDSET = [['attacker', 'rook'], ['bishop', 'knight']]

    def test_all_four_facings(self):
        for facing, (fr, fc) in enumerate(CardChess.DIRS):
            st = mk({(2, 2): (0, facing)}, self.CARDSET, 'jumper')
            want = {sq(2 + fr, 2 + fc), sq(2 + 2 * fr, 2 + 2 * fc)}
            for side in ((facing + 1) % 4, (facing + 3) % 4):
                sr, sc = CardChess.DIRS[side]
                want.add(sq(2 + fr + sr, 2 + fc + sc))
            self.assertEqual(set(dests(st, 2, 2, 'attacker')), want,
                             f'facing {facing}')

    def test_two_forward_blocked_by_either_colour(self):
        for blocker_owner in (0, 1):
            st = mk({(4, 2): (0, 0), (3, 2): (blocker_owner, 0)},
                    self.CARDSET, 'jumper')
            self.assertNotIn(sq(2, 2), dests(st, 4, 2, 'attacker'),
                             f'blocker owner {blocker_owner}')

    def test_one_forward_capture_allowed_A1(self):
        st = mk({(4, 2): (0, 0), (3, 2): (1, 2)}, self.CARDSET, 'jumper')
        self.assertIn(sq(3, 2), dests(st, 4, 2, 'attacker'))
        # but own piece one ahead is not a destination
        st2 = mk({(4, 2): (0, 0), (3, 2): (0, 0)}, self.CARDSET, 'jumper')
        self.assertNotIn(sq(3, 2), dests(st2, 4, 2, 'attacker'))


class TestRotation(unittest.TestCase):                            # checklist 5
    def test_flip_on_facing_edge_any_card_A4(self):
        # rook move to the faced edge flips
        st = mk({(1, 2): (0, 0), (4, 4): (1, 2)},
                [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        E.apply_move(st, {'card': 'rook', 'from': sq(1, 2), 'to': sq(0, 2)})
        self.assertEqual(st['board'][sq(0, 2)], (0, 2))
        # knight move to the faced edge flips too
        st = mk({(2, 1): (0, 0), (4, 4): (1, 2)},
                [['knight', 'bishop'], ['rook', 'attacker']], 'jumper')
        E.apply_move(st, {'card': 'knight', 'from': sq(2, 1), 'to': sq(0, 2)})
        self.assertEqual(st['board'][sq(0, 2)], (0, 2))

    def test_no_flip_on_unfaced_edge(self):
        # lands on the bottom edge while facing up: no flip
        st = mk({(3, 2): (0, 0), (0, 0): (1, 2)},
                [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        E.apply_move(st, {'card': 'rook', 'from': sq(3, 2), 'to': sq(4, 2)})
        self.assertEqual(st['board'][sq(4, 2)], (0, 0))

    def test_reflip_walking_back_A5(self):
        def play(st, frm, to):
            for card in list(st['cards'][st['turn']]):
                if to in E.card_dests(st, frm, card):
                    E.apply_move(st, {'card': card, 'from': frm, 'to': to})
                    return
            raise AssertionError('no held card allows this move')

        st = mk({(1, 2): (0, 0), (4, 4): (1, 2)},
                [['rook', 'knight'], ['bishop', 'attacker']], 'jumper')
        play(st, sq(1, 2), sq(0, 2))   # white reaches the faced top edge
        self.assertEqual(st['board'][sq(0, 2)][1], 2)   # now faces down
        play(st, sq(4, 4), sq(3, 3))
        play(st, sq(0, 2), sq(2, 3))   # knight back toward home
        play(st, sq(3, 3), sq(4, 3))
        play(st, sq(2, 3), sq(3, 4))
        play(st, sq(4, 3), sq(4, 2))
        # white walks onto the bottom edge, which it now faces: flips again
        play(st, sq(3, 4), sq(4, 4))
        self.assertEqual(st['board'][sq(4, 4)][1], 0)

    def test_attacker_moveset_changes_after_flip(self):
        st = mk({(1, 2): (0, 0), (4, 4): (1, 2)},
                [['attacker', 'rook'], ['knight', 'bishop']], 'jumper')
        E.apply_move(st, {'card': 'rook', 'from': sq(1, 2), 'to': sq(0, 2)})
        # flipped piece attacks downward now
        self.assertEqual(set(dests(st, 0, 2, 'attacker')),
                         {sq(1, 2), sq(2, 2), sq(1, 1), sq(1, 3)})


class TestJumper(unittest.TestCase):                              # checklist 7
    CARDSET = [['jumper', 'rook'], ['bishop', 'knight']]

    def test_requires_occupied_neighbour(self):
        st = mk({(2, 2): (0, 0), (0, 0): (1, 2)}, self.CARDSET, 'attacker')
        self.assertEqual(dests(st, 2, 2, 'jumper'), [])

    def test_all_eight_directions(self):
        pieces = {(2, 2): (0, 0)}
        for dr, dc in CardChess.ALL8:
            pieces[(2 + dr, 2 + dc)] = (1, 2)
        st = mk(pieces, self.CARDSET, 'attacker')
        want = sorted(sq(2 + 2 * dr, 2 + 2 * dc) for dr, dc in CardChess.ALL8)
        self.assertEqual(dests(st, 2, 2, 'jumper'), want)

    def test_over_own_piece_A2_and_leapt_survives_A3(self):
        st = mk({(2, 2): (0, 0), (2, 3): (0, 0), (4, 4): (1, 2)},
                self.CARDSET, 'attacker')
        self.assertEqual(dests(st, 2, 2, 'jumper'), [sq(2, 4)])
        E.apply_move(st, {'card': 'jumper', 'from': sq(2, 2), 'to': sq(2, 4)})
        self.assertEqual(st['board'][sq(2, 3)], (0, 0))  # leapt piece survives

    def test_landing_capture_offboard_and_own_block(self):
        st = mk({(2, 2): (0, 0), (2, 3): (1, 2), (2, 4): (1, 2),   # enemy landing
                 (1, 2): (1, 2),                                    # leap north lands (0,2)
                 (0, 2): (0, 0),                                    # ... on own piece: illegal
                 (2, 1): (1, 2)},                                   # leap west lands (2,0)
                self.CARDSET, 'attacker')
        d = dests(st, 2, 2, 'jumper')
        self.assertIn(sq(2, 4), d)        # landing on enemy = capture
        self.assertNotIn(sq(0, 2), d)     # landing on own piece illegal
        self.assertIn(sq(2, 0), d)
        # neighbour on the edge: landing would be off-board -> illegal
        st2 = mk({(2, 3): (0, 0), (2, 4): (1, 2)}, self.CARDSET, 'attacker')
        self.assertEqual(dests(st2, 2, 3, 'jumper'), [])


class TestQueenUpgrade(unittest.TestCase):                        # checklist 8
    def test_fires_at_two_total_in_each_location(self):
        for loc in ('p0', 'p1', 'wait'):
            cards = {'p0': [['jumper', 'rook'], ['bishop', 'knight']],
                     'p1': [['attacker', 'rook'], ['jumper', 'knight']],
                     'wait': [['attacker', 'rook'], ['bishop', 'knight']]}[loc]
            wait = 'jumper' if loc == 'wait' else ('attacker' if loc == 'p0' else 'bishop')
            st = mk({(2, 2): (0, 0), (2, 3): (1, 2), (0, 0): (1, 2)}, cards, wait)
            E.apply_move(st, {'card': cards[0][1], 'from': sq(2, 2), 'to': sq(2, 3)})
            self.assertIsNone(st['winner'])
            all_cards = st['cards'][0] + st['cards'][1] + [st['wait_card']]
            self.assertIn('queen', all_cards, loc)
            self.assertNotIn('jumper', all_cards, loc)

    def test_capture_with_jumper_itself(self):
        # jumper leaps over the enemy at (2,3) and captures at (2,4);
        # 2 pieces remain, so the card enters the wait slot as the queen
        st = mk({(2, 2): (0, 0), (2, 3): (1, 2), (2, 4): (1, 2)},
                [['jumper', 'rook'], ['bishop', 'knight']], 'attacker')
        E.apply_move(st, {'card': 'jumper', 'from': sq(2, 2), 'to': sq(2, 4)})
        self.assertEqual(st['wait_card'], 'queen')

    def test_queen_moves(self):
        st = mk({(2, 2): (0, 0), (0, 0): (1, 2)},
                [['queen', 'rook'], ['bishop', 'knight']], 'attacker')
        self.assertEqual(len(dests(st, 2, 2, 'queen')), 8)

    def test_not_at_three_total(self):
        st = mk({(2, 2): (0, 0), (0, 0): (1, 2), (0, 2): (1, 2), (4, 4): (1, 2)},
                [['jumper', 'rook'], ['bishop', 'knight']], 'attacker')
        E.apply_move(st, {'card': 'rook', 'from': sq(2, 2), 'to': sq(2, 3)})
        self.assertIn('jumper', st['cards'][0] + st['cards'][1] + [st['wait_card']])


class TestGameEnd(unittest.TestCase):
    def test_capture_all_win(self):                               # checklist 9
        st = mk({(2, 2): (0, 0), (2, 3): (1, 2), (4, 0): (0, 0)},
                [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        E.apply_move(st, {'card': 'rook', 'from': sq(2, 2), 'to': sq(2, 3)})
        self.assertEqual(st['winner'], 0)
        self.assertEqual(st['reason'], 'capture-all')

    def test_stalemate_draw_A6(self):                             # checklist 10
        # black's lone piece sits in the corner facing the edge it would need:
        # attacker has no on-board forward moves, jumper has no neighbours
        st = mk({(4, 4): (1, 2), (0, 0): (0, 0), (0, 2): (0, 0)},
                [['rook', 'bishop'], ['attacker', 'jumper']], 'knight', turn=0)
        E.apply_move(st, {'card': 'rook', 'from': sq(0, 0), 'to': sq(1, 0)})
        self.assertEqual(st['winner'], 2)
        self.assertEqual(st['reason'], 'stalemate')

    def test_repetition_draw_A7(self):                            # checklist 11
        st = mk({(4, 0): (0, 0), (0, 4): (1, 2)},
                [['queen', 'rook'], ['bishop', 'knight']], 'attacker', turn=0)
        mv = {'card': 'rook', 'from': sq(4, 0), 'to': sq(3, 0)}
        child = E.clone_state(st)
        E.apply_move(child, mv)
        key = E.pos_key(child)
        self.assertEqual(child['reps'][key], 1)
        # same position reached for the third time -> draw
        st['reps'][key] = 2
        E.apply_move(st, mv)
        self.assertEqual(st['winner'], 2)
        self.assertEqual(st['reason'], 'repetition')

    def test_repetition_keys_distinguish_cards(self):
        st = mk({(4, 0): (0, 0), (0, 4): (1, 2)},
                [['queen', 'rook'], ['bishop', 'knight']], 'attacker', turn=0)
        a = E.clone_state(st)
        E.apply_move(a, {'card': 'rook', 'from': sq(4, 0), 'to': sq(3, 0)})
        b = E.clone_state(st)
        E.apply_move(b, {'card': 'queen', 'from': sq(4, 0), 'to': sq(3, 0)})
        self.assertNotEqual(E.pos_key(a), E.pos_key(b))

    def test_reps_cleared_on_capture(self):
        st = mk({(2, 2): (0, 0), (2, 3): (1, 2), (0, 0): (1, 2)},
                [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        E.apply_move(st, {'card': 'rook', 'from': sq(2, 2), 'to': sq(2, 3)})
        self.assertEqual(len(st['reps']), 1)  # only the new position


class TestSearch(unittest.TestCase):                              # checklist 12
    def test_mate_in_one(self):
        st = mk({(2, 2): (0, 0), (2, 3): (1, 2), (4, 0): (0, 0)},
                [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        mv = negamax.choose_move(E, st, max_depth=3, time_ms=2000)
        self.assertEqual((mv['from'], mv['to']), (sq(2, 2), sq(2, 3)))

    def test_avoids_hanging_itself(self):
        # white's lone piece must not step where black's rook can take it
        st = mk({(2, 2): (0, 0), (0, 2): (1, 2)},
                [['rook', 'bishop'], ['knight', 'attacker']], 'jumper')
        mv = negamax.choose_move(E, st, max_depth=3, time_ms=2000)
        child = E.clone_state(st)
        E.apply_move(child, mv)
        if child['winner'] is None:
            reply = negamax.choose_move(E, child, max_depth=3, time_ms=2000)
            grand = E.clone_state(child)
            E.apply_move(grand, reply)
            self.assertNotEqual(grand['winner'], 1)

    def test_random_selfplay_invariants(self):
        rng = random.Random(7)
        for g in range(20):
            draft = E.all_drafts(1)[rng.randrange(30)]
            st = E.initial_state(0, draft)
            pieces_before = 10
            last_turn = None
            for ply in range(400):
                if st['winner'] is not None:
                    break
                moves = E.legal_moves(st)
                self.assertTrue(moves, 'legalMoves empty on non-terminal state')
                self.assertNotEqual(st['turn'], last_turn)
                last_turn = st['turn']
                E.apply_move(st, moves[rng.randrange(len(moves))])
                n = sum(p is not None for p in st['board'])
                self.assertLessEqual(n, pieces_before)
                pieces_before = n
                held = sorted(st['cards'][0] + st['cards'][1] + [st['wait_card']])
                held = ['jumper' if c == 'queen' else c for c in held]
                self.assertEqual(sorted(held), sorted(CARDS))

    def test_draft_helper(self):
        drafts = E.all_drafts(1)
        self.assertEqual(len(drafts), 30)
        self.assertEqual(len({(tuple(d['cards'][0]), tuple(d['cards'][1]), d['wait_card'])
                              for d in drafts}), 30)
        d = choose_draft(E, max_depth=2, time_ms=100)
        self.assertEqual(len(d['cards'][1]), 2)


if __name__ == '__main__':
    unittest.main()
