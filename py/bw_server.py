"""Black and White game server — stdlib only.

Authoritative over the hidden state: each client only ever receives its own
masked observation (see black_and_white.observe), so neither browser can see
the opponent's numbers. Two players are matched into a game; each round both
lock a tile before a deadline (the server auto-picks a random remaining tile
for anyone who misses it), then a short reveal phase shows colour + result.

Clients poll GET /api/state ~once a second; that polling also drives the
clock (rounds resolve and advance lazily on each request), so no background
thread is needed.

    python3 bw_server.py [port]      # default 8770, then open the printed URL

API:
  POST /api/join  {name}                  -> {game, player, token}
  GET  /api/state ?game&player&token      -> phase + time_left + observation
  POST /api/lock  {game, player, token, tile}
"""

import json
import os
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import black_and_white as bw

ROUND_SECONDS = 30
REVEAL_SECONDS = 4
DISCONNECT_SECONDS = 15   # clients poll ~1/s; this many seconds of silence = gone

UI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'games', 'black-and-white', 'index.html')

LOCK = threading.Lock()
GAMES = {}        # game_id -> game dict
WAITING = None    # game_id with one player awaiting an opponent


def new_game():
    now = time.time()
    return {
        'state': bw.initial_state(),
        'tokens': [secrets.token_hex(8), None],
        'names': ['', ''],
        'client_ids': [None, None],     # persistent per-browser id, to spot self-joins
        'last_seen': [now, 0.0],        # last time each player polled (heartbeat)
        'phase': 'waiting',             # waiting | playing | reveal | over | abandoned
        'deadline': 0.0,
        'reveal_until': 0.0,
        'rematch': [False, False],
    }


def alive(g, player):
    return time.time() - g['last_seen'][player] < DISCONNECT_SECONDS


def touch(g, player):
    g['last_seen'][player] = time.time()


def check_liveness(g):
    """Cancel an active game whose opponent has gone silent. Caller holds LOCK."""
    if g['phase'] in ('playing', 'reveal', 'over'):
        for p in (0, 1):
            if not alive(g, p):
                g['phase'] = 'abandoned'
                g['left'] = p
                return


def reset_for_rematch(g):
    """Re-deal the SAME game, keeping both players in their seats. No
    matchmaking, so neither player can be paired against themselves."""
    g['state'] = bw.initial_state()
    g['phase'] = 'playing'
    g['deadline'] = time.time() + ROUND_SECONDS
    g['reveal_until'] = 0.0
    g['rematch'] = [False, False]


def join(name, client_id=None):
    global WAITING
    name = (name or 'Player').strip()[:16] or 'Player'
    if WAITING and WAITING in GAMES and GAMES[WAITING]['phase'] == 'waiting':
        g = GAMES[WAITING]
        # only pair if the waiting creator is still here and isn't this same
        # browser — otherwise we'd be matched against an abandoned game or self
        same_browser = client_id is not None and g['client_ids'][0] == client_id
        if alive(g, 0) and not same_browser:
            gid = WAITING
            WAITING = None
            g['tokens'][1] = secrets.token_hex(8)
            g['names'][1] = name
            g['client_ids'][1] = client_id
            g['last_seen'][1] = time.time()
            g['phase'] = 'playing'
            g['deadline'] = time.time() + ROUND_SECONDS
            return {'game': gid, 'player': 1, 'token': g['tokens'][1]}
        GAMES.pop(WAITING, None)  # discard the stale / own waiting game
        WAITING = None
    gid = secrets.token_hex(6)
    g = new_game()
    g['names'][0] = name
    g['client_ids'][0] = client_id
    GAMES[gid] = g
    WAITING = gid
    return {'game': gid, 'player': 0, 'token': g['tokens'][0]}


def advance(g):
    """Progress a game as far as the wall clock allows. Caller holds LOCK."""
    now = time.time()
    st = g['state']
    if g['phase'] == 'playing':
        if not bw.both_locked(st) and now >= g['deadline']:
            leader = st['leader']
            if leader is None:                       # simultaneous round
                for p in (0, 1):
                    if st['locked'][p] is None:
                        st['locked'][p] = secrets.choice(st['hands'][p])
            elif st['locked'][leader] is None:       # leader missed leading
                st['locked'][leader] = secrets.choice(st['hands'][leader])
                if st['locked'][1 - leader] is None:  # responder now gets their own clock
                    g['deadline'] = now + ROUND_SECONDS
            else:                                    # responder missed responding
                resp = 1 - leader
                if st['locked'][resp] is None:
                    st['locked'][resp] = secrets.choice(st['hands'][resp])
        if bw.both_locked(st):
            bw.resolve_round(st)
            g['phase'] = 'reveal'
            g['reveal_until'] = now + REVEAL_SECONDS
    if g['phase'] == 'reveal' and now >= g['reveal_until']:
        if st['winner'] is not None:
            g['phase'] = 'over'
        else:
            g['phase'] = 'playing'
            g['deadline'] = now + ROUND_SECONDS


def view(g, gid, player):
    now = time.time()
    if g['phase'] == 'playing':
        time_left = max(0.0, g['deadline'] - now)
    elif g['phase'] == 'reveal':
        time_left = max(0.0, g['reveal_until'] - now)
    else:
        time_left = 0.0
    opp = 1 - player
    out = {
        'game': gid,
        'you': player,
        'phase': g['phase'],
        'opp_name': g['names'][opp] if g['phase'] != 'waiting' else None,
        'your_name': g['names'][player],
        'opp_joined': g['phase'] != 'waiting',
        'time_left': round(time_left, 1),
        'round_seconds': ROUND_SECONDS,
        'rematch_me': g['rematch'][player],
        'rematch_opp': g['rematch'][opp],
        'opp_left': g['phase'] == 'abandoned',
    }
    out.update(bw.observe(g['state'], player))
    return out


def authed(body_or_query):
    gid = body_or_query.get('game')
    try:
        player = int(body_or_query.get('player'))
    except (TypeError, ValueError):
        return None, None, 'bad player'
    token = body_or_query.get('token')
    g = GAMES.get(gid)
    if not g or player not in (0, 1) or g['tokens'][player] != token:
        return None, None, 'unauthorized'
    return g, player, None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _serve_ui(self):
        try:
            with open(UI_FILE, 'rb') as f:
                data = f.read()
        except OSError:
            self.send_error(404, 'UI not found')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split('?', 1)
        route = path[0]
        query = {}
        if len(path) > 1:
            for pair in path[1].split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    query[k] = v
        if route in ('/', '/index.html'):
            return self._serve_ui()
        if route == '/api/state':
            with LOCK:
                g, player, err = authed(query)
                if err:
                    return self._send({'error': err}, 400)
                touch(g, player)        # heartbeat
                check_liveness(g)       # cancel if the opponent has gone silent
                advance(g)
                return self._send(view(g, query['game'], player))
        self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(length) or b'{}')
        except (ValueError, json.JSONDecodeError):
            return self._send({'error': 'bad json'}, 400)

        if self.path == '/api/join':
            with LOCK:
                return self._send(join(body.get('name'), body.get('client')))

        if self.path == '/api/lock':
            with LOCK:
                g, player, err = authed(body)
                if err:
                    return self._send({'error': err}, 400)
                touch(g, player)
                check_liveness(g)
                advance(g)
                if g['phase'] != 'playing':
                    return self._send({'error': 'not accepting moves'}, 409)
                try:
                    bw.lock(g['state'], player, int(body.get('tile')))
                except (ValueError, TypeError) as e:
                    return self._send({'error': str(e)}, 400)
                st = g['state']
                # leader just led → start the responder's response clock fresh
                if st['leader'] is not None and player == st['leader'] \
                        and st['locked'][1 - st['leader']] is None:
                    g['deadline'] = time.time() + ROUND_SECONDS
                advance(g)  # may resolve immediately if both have now locked
                return self._send(view(g, body['game'], player))

        if self.path == '/api/rematch':
            with LOCK:
                g, player, err = authed(body)
                if err:
                    return self._send({'error': err}, 400)
                touch(g, player)
                check_liveness(g)
                if g['phase'] != 'over':
                    return self._send({'error': 'game not over'}, 409)
                g['rematch'][player] = True
                if all(g['rematch']):
                    reset_for_rematch(g)  # both agreed → re-deal the same game
                return self._send(view(g, body['game'], player))

        self.send_error(404)


def main():
    # explicit arg wins (local dev); else $PORT (hosts like Render set it); else default
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = int(os.environ.get('PORT', 8770))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'Black and White listening on port {port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
