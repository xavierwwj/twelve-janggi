"""Generic online-play relay for the perfect-information games — stdlib only.

Rules never live here: both browsers run the same JS engine and the relay
just pairs them into a room and forwards an ordered log of opaque JSON
payloads (moves, drafts, ...). Any GameEngine game gets online play from
this one server + core/online.js; the ordered log also lets a reconnecting
client replay the whole game from the start.

    python3 relay_server.py [port]      # default 8944

API (JSON bodies; CORS open so GitHub Pages can call a Render deployment):
  POST /api/quick  {game, client}        -> {room, token, status, seat?}
       pairs you with the next caller for the same game (random seats)
  POST /api/create {game}                -> {room, token, code}    private room
  POST /api/join   {code}                -> {room, token, seat, game}
  POST /api/send   {room, token, payload}-> {seq}
  GET  /api/poll   ?room&token&since     -> {status, seat, game, events, opp_online}
       long-polls up to ~20s; polling doubles as the liveness heartbeat
"""

import json
import random
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

POLL_HOLD_SECONDS = 20      # how long /api/poll may hang waiting for news
ONLINE_SECONDS = 10         # last poll within this = the player looks online
ROOM_TTL_SECONDS = 45 * 60  # idle rooms are deleted lazily

LOCK = threading.Lock()
ROOMS = {}      # room_id -> room dict
CODES = {}      # join code -> room_id
WAITING = {}    # game -> room_id with one quick-match player waiting


def new_room(game, code=None):
    room_id = secrets.token_hex(8)
    ROOMS[room_id] = {
        'game': game,
        'code': code,
        'tokens': [secrets.token_hex(8), None],
        'seats': None,            # [seat of joiner 0, seat of joiner 1], set on match
        'events': [],             # [{seq, seat, payload}]
        'last_seen': [time.time(), 0.0],
        'clients': [None, None],  # quick-match client ids (one per tab)
        'created': time.time(),
    }
    return room_id


def sweep():
    """Drop long-idle rooms. Caller holds LOCK."""
    now = time.time()
    for rid in [rid for rid, r in ROOMS.items()
                if now - max(r['last_seen'] + [r['created']]) > ROOM_TTL_SECONDS]:
        r = ROOMS.pop(rid)
        if r['code']:
            CODES.pop(r['code'], None)
        for g, w in list(WAITING.items()):
            if w == rid:
                del WAITING[g]


def player_of(room, token):
    return room['tokens'].index(token) if token in room['tokens'] else None


def matched(room):
    return room['tokens'][1] is not None


def assign_seats(room):
    s = random.randint(0, 1)
    room['seats'] = [s, 1 - s]


def room_view(room, player):
    return {
        'status': 'playing' if matched(room) else 'waiting',
        'game': room['game'],
        'seat': room['seats'][player] if room['seats'] else None,
        'opp_online': (matched(room)
                       and time.time() - room['last_seen'][1 - player] < ONLINE_SECONDS),
    }


def api_quick(body):
    game = body['game']
    client = body.get('client')
    with LOCK:
        sweep()
        rid = WAITING.get(game)
        room = ROOMS.get(rid)
        # a waiting room only counts if its creator is still polling
        if room and not matched(room) and time.time() - room['last_seen'][0] < ONLINE_SECONDS \
                and room['clients'][0] != client:
            del WAITING[game]
            room['tokens'][1] = secrets.token_hex(8)
            room['clients'][1] = client
            room['last_seen'][1] = time.time()
            assign_seats(room)
            return {'room': rid, 'token': room['tokens'][1],
                    **room_view(room, 1)}
        rid = new_room(game)
        ROOMS[rid]['clients'][0] = client
        WAITING[game] = rid
        return {'room': rid, 'token': ROOMS[rid]['tokens'][0],
                **room_view(ROOMS[rid], 0)}


def api_create(body):
    with LOCK:
        sweep()
        while True:
            code = '%04d' % random.randint(0, 9999)
            if code not in CODES:
                break
        rid = new_room(body['game'], code)
        CODES[code] = rid
        return {'room': rid, 'token': ROOMS[rid]['tokens'][0], 'code': code,
                **room_view(ROOMS[rid], 0)}


def api_join(body):
    with LOCK:
        rid = CODES.get(str(body['code']))
        room = ROOMS.get(rid)
        if room is None:
            return {'error': 'no such room code'}
        if matched(room):
            return {'error': 'room is full'}
        room['tokens'][1] = secrets.token_hex(8)
        room['last_seen'][1] = time.time()
        assign_seats(room)
        return {'room': rid, 'token': room['tokens'][1], **room_view(room, 1)}


def api_send(body):
    with LOCK:
        room = ROOMS.get(body.get('room'))
        player = room and player_of(room, body.get('token'))
        if player is None:
            return {'error': 'unknown room or token'}
        room['last_seen'][player] = time.time()
        seq = len(room['events'])
        room['events'].append({'seq': seq, 'seat': room['seats'][player],
                               'payload': body['payload']})
        return {'seq': seq}


def api_poll(params):
    rid = params.get('room')
    token = params.get('token')
    since = int(params.get('since', 0))
    still_waiting = params.get('waiting') == '1'   # client hasn't seen a match yet
    deadline = time.time() + POLL_HOLD_SECONDS
    while True:
        with LOCK:
            room = ROOMS.get(rid)
            player = room and player_of(room, token)
            if player is None:
                return {'error': 'unknown room or token'}
            room['last_seen'][player] = time.time()
            fresh = room['events'][since:]
            if fresh or time.time() > deadline or (still_waiting and matched(room)):
                return {**room_view(room, player), 'events': fresh}
        time.sleep(0.25)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._reply({})

    def do_GET(self):
        path, _, query = self.path.partition('?')
        params = dict(kv.split('=', 1) for kv in query.split('&') if '=' in kv)
        if path == '/api/poll':
            try:
                self._reply(api_poll(params))
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif path == '/api/health':
            self._reply({'ok': True, 'rooms': len(ROOMS)})
        else:
            self._reply({'error': 'not found'}, 404)

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            return self._reply({'error': 'bad json'}, 400)
        route = {'/api/quick': api_quick, '/api/create': api_create,
                 '/api/join': api_join, '/api/send': api_send}.get(self.path)
        if route is None:
            return self._reply({'error': 'not found'}, 404)
        try:
            self._reply(route(body))
        except KeyError as e:
            self._reply({'error': f'missing field {e}'}, 400)


def main():
    import os
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORT', 8944))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'relay server on http://0.0.0.0:{port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
