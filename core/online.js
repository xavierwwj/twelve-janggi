'use strict';
/**
 * Online 2-player transport for any game in this repo — the client side of
 * py/relay_server.py. The relay knows no rules: both browsers run the same
 * engine and exchange opaque payloads ({type:'move', ...}, {type:'draft',
 * ...}) through an ordered per-room event log. Every event — including your
 * own, echoed back — is applied via the same onEvent stream, so both clients
 * stay in lockstep and a reload can rebuild the game by replaying the log.
 *
 * const s = new OnlineSession(RELAY_URL, 'card-chess', 'card-chess-online-v1');
 *   await s.quick()  |  await s.create() -> code  |  await s.join(code)
 *   s.start({ onMatched(seat), onEvents(evs), onStatus(txt) })
 *   s.send(payload); s.leave();
 * OnlineSession.saved(url, game, key) -> resumable session or null.
 */
class OnlineSession {
  constructor(serverUrl, game, saveKey) {
    this.url = serverUrl.replace(/\/$/, '');
    this.game = game;
    this.saveKey = saveKey;
    this.room = null;
    this.token = null;
    this.seat = null;
    this.since = 0;
    this.code = null;
    this.stopped = false;
    // one id per tab so two tabs of the same browser can quick-match each other
    this.client = sessionStorage.getItem('online-client') ||
      Math.random().toString(36).slice(2);
    sessionStorage.setItem('online-client', this.client);
  }

  static saved(serverUrl, game, saveKey) {
    try {
      const d = JSON.parse(localStorage.getItem(saveKey));
      if (!d || d.game !== game) return null;
      const s = new OnlineSession(serverUrl, game, saveKey);
      Object.assign(s, { room: d.room, token: d.token, seat: d.seat });
      return s;
    } catch (e) { return null; }
  }

  async _post(path, body) {
    const res = await fetch(this.url + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data;
  }

  _adopt(d) {
    this.room = d.room;
    this.token = d.token;
    if (d.seat !== null && d.seat !== undefined) this.seat = d.seat;
    this._save();
    return d;
  }

  _save() {
    try {
      localStorage.setItem(this.saveKey, JSON.stringify(
        { game: this.game, room: this.room, token: this.token, seat: this.seat }));
    } catch (e) { /* private mode — online play just won't survive reloads */ }
  }

  async quick() { return this._adopt(await this._post('/api/quick', { game: this.game, client: this.client })); }
  async create() { const d = this._adopt(await this._post('/api/create', { game: this.game })); this.code = d.code; return d; }
  async join(code) { return this._adopt(await this._post('/api/join', { code })); }

  async send(payload) {
    return this._post('/api/send', { room: this.room, token: this.token, payload });
  }

  /** Begin the poll loop. Calls onMatched(seat) once seats are known, then
   *  onEvents(evs) per batch, in order (a reconnect replays the whole log in
   *  one batch); onStatus gets connection notes. */
  start(handlers) {
    this.handlers = handlers;
    this.stopped = false;
    this._loop();
  }

  async _loop() {
    let told = this.seat !== null;
    while (!this.stopped) {
      try {
        const waiting = told ? '' : '&waiting=1';
        const res = await fetch(this.url +
          `/api/poll?room=${this.room}&token=${this.token}&since=${this.since}${waiting}`);
        const d = await res.json();
        if (d.error) { this.handlers.onStatus?.('error: ' + d.error); return; }
        if (d.seat !== null && d.seat !== undefined) this.seat = d.seat;
        if (!told && d.status === 'playing') {
          told = true;
          this._save();
          this.handlers.onMatched?.(this.seat);
        }
        if (d.events && d.events.length) {
          this.since = d.events[d.events.length - 1].seq + 1;
          this.handlers.onEvents?.(d.events);
        }
        this.handlers.onStatus?.(d.status === 'waiting' ? 'waiting'
          : d.opp_online ? 'connected' : 'opponent offline');
      } catch (e) {
        this.handlers.onStatus?.('reconnecting…');
        await new Promise(r => setTimeout(r, 2000));
      }
    }
  }

  leave() {
    this.stopped = true;
    try { localStorage.removeItem(this.saveKey); } catch (e) { /* ignore */ }
  }
}
