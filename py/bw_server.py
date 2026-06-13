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

UI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'games', 'black-and-white', 'index.html')

LOCK = threading.Lock()
GAMES = {}        # game_id -> game dict
WAITING = None    # game_id with one player awaiting an opponent


def new_game():
    return {
        'state': bw.initial_state(),
        'tokens': [secrets.token_hex(8), None],
        'names': ['', ''],
        'phase': 'waiting',     # waiting | playing | reveal | over
        'deadline': 0.0,
        'reveal_until': 0.0,
    }


def join(name):
    global WAITING
    name = (name or 'Player').strip()[:16] or 'Player'
    if WAITING and WAITING in GAMES and GAMES[WAITING]['phase'] == 'waiting':
        g = GAMES[WAITING]
        gid = WAITING
        WAITING = None
        g['tokens'][1] = secrets.token_hex(8)
        g['names'][1] = name
        g['phase'] = 'playing'
        g['deadline'] = time.time() + ROUND_SECONDS
        return {'game': gid, 'player': 1, 'token': g['tokens'][1]}
    gid = secrets.token_hex(6)
    g = new_game()
    g['names'][0] = name
    GAMES[gid] = g
    WAITING = gid
    return {'game': gid, 'player': 0, 'token': g['tokens'][0]}


def advance(g):
    """Progress a game as far as the wall clock allows. Caller holds LOCK."""
    now = time.time()
    st = g['state']
    if g['phase'] == 'playing':
        if not bw.both_locked(st) and now >= g['deadline']:
            for p in (0, 1):
                if st['locked'][p] is None:
                    st['locked'][p] = secrets.choice(st['hands'][p])
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
                return self._send(join(body.get('name')))

        if self.path == '/api/lock':
            with LOCK:
                g, player, err = authed(body)
                if err:
                    return self._send({'error': err}, 400)
                advance(g)
                if g['phase'] != 'playing':
                    return self._send({'error': 'not accepting moves'}, 409)
                try:
                    bw.lock(g['state'], player, int(body.get('tile')))
                except (ValueError, TypeError) as e:
                    return self._send({'error': str(e)}, 400)
                advance(g)  # may resolve immediately if both have now locked
                return self._send(view(g, body['game'], player))

        self.send_error(404)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'Black and White: http://localhost:{port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
