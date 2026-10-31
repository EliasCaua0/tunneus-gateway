#!/usr/bin/env python3
"""Mock local do Tunneus Gateway (apenas para testar o dashboard).

NÃO fala com hardware nem com o Gateway real. Simula:
  GET  /api/agents, POST /api/agents/{id}/command, GET /api/operations/{id},
  GET  /api/events (SSE) e serve o index.html.
Controles de teste em /__mock/*.
"""
import json, sys, threading, time, uuid, queue
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

INDEX = sys.argv[1]
PORT = int(sys.argv[2])

BENCH_CAPS = ["LER_SENSORES", "TEMPERATURA", "PRESSAO", "ALTITUDE", "CORRENTE", "DISTANCIA", "START", "PARE", "MOVER"]
SPEEDS = {"lenta": 800, "normal": 400, "rapida": 200}   # espelha o firmware v4.4
MAX_STEPS = 30000
LOCK = threading.Lock()
MODE = {
    "caps": list(BENCH_CAPS),
    "scenario": "ok",          # ok | fail | silent | stderr | fast | reject | noretry
    "gateway_down": False,
    "batch": "TEMPERATURA=23.45 C | PRESSAO=101325 Pa | ALTITUDE=28.10 m | CORRENTE=0.123 A | DISTANCIA=35.2 cm",
    "dist": "35.2 cm",
    "status": "standby",
    "step_delay": 0.15,
}
POSTS = []          # comandos recebidos (para provar que só o mock foi usado)
GETS = {"agents": 0, "operations": 0}
CLIENTS = []        # filas SSE
OPS = {}


def agents():
    return [
        {"agent_id": "esp32-01", "last_ip": "", "capabilities": ["LED_ON", "LED_OFF"], "status": "standby",
         "name": "Protótipo LED 01", "type": "led", "icon": "💡", "description": "Subagente ESP32 — LED", "last_seen": "0001-01-01T00:00:00Z"},
        {"agent_id": "esp32-02", "capabilities": ["LIGAR", "ELEVAÇÃO A", "ELEVAÇÃO B", "DESLIGAR"], "status": "standby",
         "name": "Agente 02 — Polias", "type": "industrial", "icon": "⚙️", "description": "Polias", "last_seen": "0001-01-01T00:00:00Z"},
        {"agent_id": "esp32-03", "capabilities": MODE["caps"], "status": MODE["status"],
         "name": "Agente 03 — Bancada de Sensores", "type": "sensor", "icon": "🧪",
         "description": "Sensores e motor de passo (PCB da bancada)", "last_seen": "0001-01-01T00:00:00Z"},
    ]


def broadcast(ev):
    data = json.dumps(ev, ensure_ascii=False)
    for q in list(CLIENTS):
        q.put(data)


def mover_result(args):
    """Mesma validação do firmware v4.4: argumento inválido => stderr, nada se move."""
    if not isinstance(args, dict) or not args:
        return "", "MOVER requer args {dir, steps, speed}."
    d, sp, st = args.get("dir"), args.get("speed"), args.get("steps")
    if d not in ("direita", "esquerda"):
        return "", "MOVER: dir invalido (use direita ou esquerda)."
    if sp not in SPEEDS:
        return "", "MOVER: speed invalido (use lenta, normal ou rapida)."
    if isinstance(st, bool) or not isinstance(st, int):
        return "", "MOVER: steps deve ser um inteiro."
    if st < 1 or st > MAX_STEPS:
        return "", "MOVER: steps fora do limite (1 a %d)." % MAX_STEPS
    return "Movimento INICIADO: %s, %d passos, %s (%dus/pulso)." % (d, st, sp, SPEEDS[sp]), ""


def result_for(cmd, args=None):
    if cmd == "MOVER":
        return mover_result(args)
    if cmd == "LER_SENSORES":
        return MODE["batch"], ""
    if cmd == "TEMPERATURA": return "23.45 C", ""
    if cmd == "PRESSAO": return "101325 Pa", ""
    if cmd == "ALTITUDE": return "28.10 m", ""
    if cmd == "CORRENTE": return "0.123 A", ""
    if cmd == "DISTANCIA":
        if MODE["dist"] == "NOECHO":
            return "", "Distancia fora de alcance (sem eco do HC-SR04)."
        return MODE["dist"], ""
    if cmd == "START": return "Motor de passo INICIADO (padrao do exemplo: 400us/pulso).", ""
    if cmd == "PARE": return "Motor de passo PARADO (comando PARE do dashboard).", ""
    return "", "Comando desconhecido pelo agente."


def run_op(op_id, cmd, args=None):
    sc = MODE["scenario"]
    d = MODE["step_delay"]
    base = {"agent_id": "esp32-03", "op_id": op_id}
    if sc != "fast":
        time.sleep(d)
    broadcast({**base, "event": "command_created", "command": cmd, **({"args": args} if args else {})})
    if sc == "silent":
        time.sleep(d); broadcast({**base, "event": "wake_sent", "attempt": 1}); return
    time.sleep(d); broadcast({**base, "event": "wake_sent", "attempt": 1})
    if sc == "fail":
        for a in (1, 2):
            time.sleep(d); broadcast({**base, "event": "auth_timeout", "attempt": a})
        time.sleep(d); broadcast({**base, "event": "operation_failed", "reason": "max_retries_exhausted"})
        OPS[op_id]["status"] = "failed"; return
    time.sleep(d); broadcast({**base, "event": "auth_ok"})
    time.sleep(d); broadcast({**base, "event": "command_sent"})
    time.sleep(d)
    if sc == "noretry":
        # Gateway real: comando não idempotente entregue e sem resultado => não reenvia.
        broadcast({**base, "event": "result_timeout", "attempt": 1})
        time.sleep(d); broadcast({**base, "event": "operation_failed", "reason": "result_unconfirmed_no_retry"})
        OPS[op_id]["status"] = "failed"; return
    out, err = result_for(cmd, args)
    if sc == "stderr": out, err = "", "Comando desconhecido pelo agente."
    broadcast({**base, "event": "result_received", "stdout": out, "stderr": err})
    OPS[op_id]["status"] = "completed"


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silencia
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/dashboard", "/dashboard/"):
            body = open(INDEX, "rb").read()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if u.path == "/api/agents":
            GETS["agents"] += 1
            if MODE["gateway_down"]:
                return self._json(500, {"error": "down"})
            return self._json(200, agents())
        if u.path.startswith("/api/operations/"):
            GETS["operations"] += 1
            oid = u.path.rsplit("/", 1)[1]
            # Formato real do Gateway (api.GetOperation): { success, operation: {...} }
            if oid not in OPS:
                return self._json(404, {"success": False, "message": "Operação não encontrada"})
            return self._json(200, {"success": True, "operation": {"id": oid, **OPS[oid]}})
        if u.path == "/api/events":
            q = queue.Queue(); CLIENTS.append(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive"); self.end_headers()
            try:
                self.wfile.write(b'data: {"event":"sse_connected"}\n\n'); self.wfile.flush()
                while True:
                    try:
                        data = q.get(timeout=5)
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n"); self.wfile.flush(); continue
                    if data == "__DROP__":
                        break
                    self.wfile.write(("data: " + data + "\n\n").encode()); self.wfile.flush()
            except Exception:
                pass
            finally:
                if q in CLIENTS: CLIENTS.remove(q)
            self.close_connection = True
            return
        if u.path == "/__mock/state":
            return self._json(200, {"posts": POSTS, "gets": GETS, "clients": len(CLIENTS), "mode": MODE})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        if u.path.startswith("/api/agents/") and u.path.endswith("/command"):
            aid = u.path.split("/")[3]
            try: body = json.loads(raw) if raw else {}
            except Exception: body = {}
            cmd = body.get("cmd", "") if isinstance(body, dict) else ""
            args = body.get("args") if isinstance(body, dict) else None
            POSTS.append({"agent": aid, "cmd": cmd, "args": args, "keys": sorted(body.keys()) if isinstance(body, dict) else []})
            if MODE["scenario"] == "reject":
                return self._json(400, {"success": False, "message": "capability não suportada pelo agente"})
            if aid != "esp32-03" or cmd not in MODE["caps"]:
                return self._json(400, {"success": False, "message": "capability não suportada pelo agente"})
            op_id = str(uuid.uuid4())
            OPS[op_id] = {"status": "pending"}
            t = threading.Thread(target=run_op, args=(op_id, cmd, args), daemon=True)
            if MODE["scenario"] == "fast":
                run_op(op_id, cmd, args)     # eventos chegam ANTES da resposta HTTP
            else:
                t.start()
            return self._json(202, {"success": True, "message": "Comando aceito e em processamento",
                                    "op_id": op_id, "agent_id": aid, "command": cmd, "args": args})
        if u.path == "/__mock/set":
            body = json.loads(raw or b"{}")
            MODE.update(body); return self._json(200, MODE)
        if u.path == "/__mock/emit":
            body = raw.decode()
            for q in list(CLIENTS): q.put(body)
            return self._json(200, {"ok": True})
        if u.path == "/__mock/drop":
            for q in list(CLIENTS): q.put("__DROP__")
            return self._json(200, {"ok": True})
        self._json(404, {"error": "not found"})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    srv.daemon_threads = True
    print("mock em http://127.0.0.1:%d" % PORT, flush=True)
    srv.serve_forever()
