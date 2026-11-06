#!/usr/bin/env python3
"""Mock do Gateway para testes de interface; não comunica com hardware."""
import json
import queue
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

INDEX = sys.argv[1]
PORT = int(sys.argv[2])
BENCH_CAPS = ["LER_SENSORES", "TEMPERATURA", "PRESSAO", "ALTITUDE", "CORRENTE", "DISTANCIA", "START", "PARE", "MOVER"]
SPEEDS = {"lenta": 800, "normal": 400, "rapida": 200}
LOCK = threading.Lock()
MODE = {
    "caps": list(BENCH_CAPS), "scenario": "ok", "gateway_down": False,
    "batch": "TEMPERATURA=23.45 C | PRESSAO=101325 Pa | ALTITUDE=28.10 m | CORRENTE=0.123 A | DISTANCIA=35.2 cm",
    "dist": "35.2 cm", "status": "standby", "step_delay": 0.02,
}
AGENTS = [
    {"agent_id": "esp32-01", "capabilities": ["LED_ON", "LED_OFF"], "status": "standby", "name": "Protótipo LED 01", "type": "led", "description": "Subagente ESP32 — LED"},
    {"agent_id": "esp32-02", "capabilities": ["LIGAR", "DESLIGAR"], "status": "standby", "name": "Agente 02 — Polias", "type": "industrial", "description": "Polias"},
    {"agent_id": "esp32-03", "capabilities": BENCH_CAPS, "status": "standby", "name": "Agente 03 — Bancada de Sensores", "type": "sensor_motor", "description": "Sensores e motor de passo"},
]
POSTS = []
GETS = {"agents": 0, "operations": 0}
CLIENTS = []
OPS = {}
ACTIVE = {}
RELEASE = threading.Event()


def agents():
    with LOCK:
        active = dict(ACTIVE)
    result = []
    for source in AGENTS:
        item = dict(source)
        if item["agent_id"] == "esp32-03":
            item["capabilities"] = list(MODE["caps"])
            item["status"] = MODE["status"]
        op_id = active.get(item["agent_id"])
        item.update({"operation_state": "in_operation" if op_id else "available", "last_seen": "0001-01-01T00:00:00Z"})
        if op_id:
            item["active_op_id"] = op_id
        result.append(item)
    return result


def broadcast(event):
    data = json.dumps(event, ensure_ascii=False)
    with LOCK:
        clients = list(CLIENTS)
    for client in clients:
        client.put(data)


def agent_state(agent_id, state, op_id):
    event = {"event": "agent_state_changed", "agent_id": agent_id, "operation_state": state, "op_id": op_id}
    if state == "in_operation":
        event["active_op_id"] = op_id
    broadcast(event)


def mover_result(args):
    if not isinstance(args, dict):
        return "", "MOVER requer args."
    direction, speed, steps = args.get("dir"), args.get("speed"), args.get("steps")
    if direction not in ("direita", "esquerda") or speed not in SPEEDS:
        return "", "Argumentos de MOVER inválidos."
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 30000:
        return "", "MOVER: steps fora do limite."
    return "Movimento INICIADO: %s, %d passos, %s." % (direction, steps, speed), ""


def result_for(agent_id, cmd, args):
    if cmd == "MOVER":
        return mover_result(args)
    if cmd == "LER_SENSORES":
        return MODE["batch"], ""
    if cmd == "TEMPERATURA": return "23.45 C", ""
    if cmd == "PRESSAO": return "101325 Pa", ""
    if cmd == "ALTITUDE": return "28.10 m", ""
    if cmd == "CORRENTE": return "0.123 A", ""
    if cmd == "DISTANCIA": return ("", "Sem eco.") if MODE["dist"] == "NOECHO" else (MODE["dist"], "")
    if cmd == "START": return "Motor de passo INICIADO.", ""
    if cmd == "PARE": return "Motor de passo PARADO.", ""
    if any(cmd in item["capabilities"] for item in AGENTS):
        return "ok:%s:%s" % (agent_id, cmd), ""
    return "", "Comando desconhecido."


def run_op(agent_id, op_id, cmd, args):
    base = {"agent_id": agent_id, "op_id": op_id}
    scenario = MODE["scenario"]
    delay = MODE["step_delay"]
    try:
        broadcast({**base, "event": "command_created", "command": cmd, **({"args": args} if args else {})})
        time.sleep(delay)
        broadcast({**base, "event": "wake_sent", "attempt": 1})
        if scenario == "silent":
            return
        time.sleep(delay)
        if scenario == "fail":
            broadcast({**base, "event": "operation_failed", "reason": "max_retries_exhausted"})
            OPS[op_id]["status"] = "failed"
            return
        broadcast({**base, "event": "auth_ok"})
        time.sleep(delay)
        broadcast({**base, "event": "command_sent"})
        if scenario == "hold":
            RELEASE.wait()
        time.sleep(delay)
        if scenario == "noretry":
            broadcast({**base, "event": "result_timeout", "attempt": 1})
            broadcast({**base, "event": "operation_failed", "reason": "result_unconfirmed_no_retry"})
            OPS[op_id]["status"] = "failed"
            return
        out, err = result_for(agent_id, cmd, args)
        if scenario == "stderr":
            out, err = "", "Falha no agente."
        broadcast({**base, "event": "result_received", "stdout": out, "stderr": err})
        OPS[op_id]["status"] = "completed"
    finally:
        with LOCK:
            if ACTIVE.get(agent_id) == op_id:
                del ACTIVE[agent_id]
        agent_state(agent_id, "available", op_id)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def json_response(self, code, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/dashboard", "/dashboard/"):
            body = open(INDEX, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/agents":
            GETS["agents"] += 1
            if MODE["gateway_down"]:
                return self.json_response(500, {"error": "down"})
            return self.json_response(200, agents())
        if path.startswith("/api/operations/"):
            GETS["operations"] += 1
            op_id = path.rsplit("/", 1)[1]
            if op_id not in OPS:
                return self.json_response(404, {"success": False})
            return self.json_response(200, {"success": True, "operation": {"id": op_id, **OPS[op_id]}})
        if path == "/api/events":
            client = queue.Queue()
            with LOCK:
                CLIENTS.append(client)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                self.wfile.write(b'data: {"event":"sse_connected"}\n\n')
                self.wfile.flush()
                while True:
                    try:
                        data = client.get(timeout=5)
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        continue
                    if data == "__DROP__":
                        break
                    self.wfile.write(("data: " + data + "\n\n").encode())
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                with LOCK:
                    if client in CLIENTS:
                        CLIENTS.remove(client)
            self.close_connection = True
            return
        if path == "/__mock/state":
            return self.json_response(200, {"posts": POSTS, "gets": GETS, "clients": len(CLIENTS), "active": ACTIVE, "mode": MODE})
        self.json_response(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if path.startswith("/api/agents/") and path.endswith("/command"):
            agent_id = path.split("/")[3]
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {}
            cmd = body.get("cmd", "")
            args = body.get("args")
            POSTS.append({"agent": agent_id, "cmd": cmd, "args": args, "keys": sorted(body.keys()), "at": time.time()})
            if MODE["scenario"] == "reject":
                return self.json_response(400, {"success": False, "message": "capability não suportada"})
            if MODE["scenario"] == "busy":
                return self.json_response(409, {"success": False, "error": "agent_busy", "message": "Agente ocupado: já existe uma operação ativa", "agent_id": agent_id, "active_op_id": "external-op", "operation_state": "in_operation"})
            agent = next((item for item in AGENTS if item["agent_id"] == agent_id), None)
            caps = MODE["caps"] if agent_id == "esp32-03" else (agent["capabilities"] if agent else [])
            if not agent or cmd not in caps:
                return self.json_response(400, {"success": False, "message": "capability não suportada"})
            with LOCK:
                active_op = ACTIVE.get(agent_id)
                if active_op:
                    return self.json_response(409, {"success": False, "error": "agent_busy", "message": "Agente ocupado: já existe uma operação ativa", "agent_id": agent_id, "active_op_id": active_op, "operation_state": "in_operation"})
                op_id = str(uuid.uuid4())
                ACTIVE[agent_id] = op_id
                OPS[op_id] = {"status": "pending"}
            agent_state(agent_id, "in_operation", op_id)
            if MODE["scenario"] == "fast":
                run_op(agent_id, op_id, cmd, args)
            else:
                threading.Thread(target=run_op, args=(agent_id, op_id, cmd, args), daemon=True).start()
            return self.json_response(202, {"success": True, "message": "Comando aceito e em processamento", "op_id": op_id, "agent_id": agent_id, "command": cmd, "args": args})
        if path == "/__mock/set":
            body = json.loads(raw or b"{}")
            if body.get("scenario") == "hold":
                RELEASE.clear()
            MODE.update(body)
            return self.json_response(200, MODE)
        if path == "/__mock/release":
            RELEASE.set()
            return self.json_response(200, {"ok": True})
        if path == "/__mock/emit":
            for client in list(CLIENTS):
                client.put(raw.decode())
            return self.json_response(200, {"ok": True})
        if path == "/__mock/drop":
            for client in list(CLIENTS):
                client.put("__DROP__")
            return self.json_response(200, {"ok": True})
        self.json_response(404, {"error": "not found"})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print("mock em http://127.0.0.1:%d" % PORT, flush=True)
    server.serve_forever()
