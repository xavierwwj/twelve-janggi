"""HTTP server for Twelve Janggi: serves the static UI and a small JSON API.

Stdlib only — run with `python3 server.py [port]` and open the printed URL.

API:
  GET  /api/state                     -> current game state
  POST /api/new   {mode, first, level} -> reset (mode: 'pvp'|'ai')
  POST /api/move  {from, to} | {drop, to} -> apply a human move
  POST /api/ai                        -> compute and apply the AI's move
"""

import json
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import ai
import game

ROOT = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()


class Session:
    def __init__(self):
        self.new('pvp', 0, 'normal')

    def new(self, mode, first, level):
        self.game = game.Game(first=first)
        self.mode = mode
        self.ai_player = 1 if mode == 'ai' else None
        self.level = level
        self.last = []


SESSION = Session()


def state_dict():
    g = SESSION.game
    return {
        'board': [None if p is None else {'type': p[0], 'owner': p[1]} for p in g.board],
        'hands': g.hands,
        'turn': g.turn,
        'winner': g.winner,
        'reason': g.reason,
        'mode': SESSION.mode,
        'ai_player': SESSION.ai_player,
        'level': SESSION.level,
        'last': SESSION.last,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/api/state':
            with LOCK:
                self._json(state_dict())
        else:
            super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(length) or b'{}')
        except (ValueError, json.JSONDecodeError):
            return self._json({'error': 'bad request'}, 400)

        with LOCK:
            if self.path == '/api/new':
                mode = body.get('mode')
                first = body.get('first')
                level = body.get('level')
                SESSION.new(
                    mode if mode in ('pvp', 'ai') else 'pvp',
                    first if first in (0, 1) else 0,
                    level if level in ai.LEVELS else 'normal',
                )
                self._json(state_dict())

            elif self.path == '/api/move':
                g = SESSION.game
                if g.winner is not None:
                    return self._json({'error': 'game over'}, 400)
                if SESSION.ai_player is not None and g.turn == SESSION.ai_player:
                    return self._json({'error': 'not your turn'}, 400)
                try:
                    if 'drop' in body:
                        mv = ('d', body['drop'], int(body['to']))
                    else:
                        mv = ('m', int(body['from']), int(body['to']))
                except (KeyError, TypeError, ValueError):
                    return self._json({'error': 'bad move'}, 400)
                if mv not in g.legal_moves():
                    return self._json({'error': 'illegal move'}, 400)
                g.apply(mv)
                SESSION.last = [mv[1], mv[2]] if mv[0] == 'm' else [mv[2]]
                self._json(state_dict())

            elif self.path == '/api/ai':
                g = SESSION.game
                if g.winner is not None or SESSION.ai_player is None or g.turn != SESSION.ai_player:
                    return self._json({'error': 'not the AI turn'}, 400)
                mv = ai.choose_move(g, SESSION.level)
                if mv is None:
                    return self._json({'error': 'no move'}, 500)
                g.apply(mv)
                SESSION.last = [mv[1], mv[2]] if mv[0] == 'm' else [mv[2]]
                self._json(state_dict())

            else:
                self._json({'error': 'not found'}, 404)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8943
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'Twelve Janggi: http://localhost:{port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
