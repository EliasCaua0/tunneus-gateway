#!/usr/bin/env python3
"""Testes do dashboard multiagente contra o mock; nenhum hardware é acionado."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.environ.get("DASHBOARD_INDEX", os.path.join(HERE, "..", "..", "web", "dashboard", "index.html"))
PORT = 18555
BASE = f"http://127.0.0.1:{PORT}"
SHOTS = os.environ.get("DASHBOARD_SHOTS", os.path.join(HERE, "shots"))
os.makedirs(SHOTS, exist_ok=True)
RESULTS = []


def check(name, condition, extra=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + (f" [{extra}]" if extra and not condition else ""), flush=True)


def api(path, body=None):
    request = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def setmode(**values):
    return api("/__mock/set", values)


def emit(value):
    return api("/__mock/emit", value if isinstance(value, dict) else {"raw": value})


def state():
    return api("/__mock/state")


def wait_op(page, agent, status):
    page.wait_for_function("""({agent,status}) => {
      const ps=S.panels.get(agent); if(!ps) return false;
      const op=ps.ops.get(ps.order[ps.order.length-1]);
      return op && op.status===status;
    }""", arg={"agent": agent, "status": status}, timeout=7000)


def open_page(context, agent=None):
    page = context.new_page()
    suffix = "?agent=" + agent if agent else ""
    page.goto(BASE + "/dashboard/" + suffix)
    page.wait_for_function("S.agents.size===3 && document.querySelectorAll('.agent-panel').length>0", timeout=5000)
    return page


process = subprocess.Popen([sys.executable, os.path.join(HERE, "mock_gateway.py"), INDEX, str(PORT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(0.7)

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context1 = browser.new_context(viewport={"width": 1440, "height": 1000})
        context2 = browser.new_context(viewport={"width": 1280, "height": 900})
        page1 = open_page(context1, "esp32-03")
        page2 = open_page(context2, "esp32-01")
        errors = []
        for page in (page1, page2):
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" and "Failed to load resource" not in message.text else None)

        check("lista todos os agentes registrados", page1.locator("[data-agent-choice]").count() == 3)
        check("seleção inicial por ?agent= é independente", page1.locator(".agent-panel").count() == 1 and page2.locator(".agent-panel").count() == 1 and page1.locator("#panel-esp32-03").count() == 1 and page2.locator("#panel-esp32-01").count() == 1)
        check("Agente 03 mantém cinco gráficos SVG", page1.locator("#panel-esp32-03 .chart-card").count() == 5 and page1.locator("#panel-esp32-03 .chart-plot svg").count() == 5)
        check("não usa armazenamento compartilhado", page1.evaluate("localStorage.length") == 0 and page2.evaluate("localStorage.length") == 0)
        check("SSE conecta nas duas guias", "conectado" in page1.inner_text("#sse-text") and "conectado" in page2.inner_text("#sse-text"))

        page1.locator("[data-agent-choice=esp32-01] input").check()
        page1.locator("[data-agent-choice=esp32-02] input").check()
        check("seleção múltipla abre painéis independentes", page1.locator(".agent-panel").count() == 3)
        check("seleção da outra guia não é alterada", page2.locator(".agent-panel").count() == 1 and page2.locator("#panel-esp32-02").count() == 0)

        setmode(scenario="hold", step_delay=0.02)
        before = len(state()["posts"])
        started = time.time()
        page1.click("#panel-esp32-03 [data-command=LER_SENSORES]")
        page2.click("#panel-esp32-01 [data-command=LED_ON]")
        page1.wait_for_function("S.panels.get('esp32-03').ops.size>0 && [...S.panels.get('esp32-03').ops.values()][0].stage==='cmd'", timeout=5000)
        page2.wait_for_function("S.panels.get('esp32-01').ops.size>0 && [...S.panels.get('esp32-01').ops.values()][0].stage==='cmd'", timeout=5000)
        active = state()["active"]
        posts = state()["posts"][before:]
        check("duas guias executam agentes diferentes simultaneamente", set(active) == {"esp32-01", "esp32-03"} and len(posts) == 2, json.dumps(active))
        print("TIMESTAMPS parallel_posts=" + json.dumps(posts, ensure_ascii=False), flush=True)
        check("nenhum Result antes da liberação dos agentes", "Nenhum Result" not in page1.inner_text("#panel-esp32-03 [data-f=result]") and page1.evaluate("[...S.panels.get('esp32-03').ops.values()][0].status") == "running" and page2.evaluate("[...S.panels.get('esp32-01').ops.values()][0].status") == "running")
        check("ocupado aparece em tempo real na outra guia", "ocupado" in page1.inner_text("[data-agent-choice=esp32-01]").lower() and "ocupado" in page1.inner_text("#panel-esp32-01").lower())
        check("comandos do agente ocupado ficam bloqueados, inclusive PARE", page1.is_disabled("#panel-esp32-01 [data-command=LED_ON]") and page1.is_disabled("#panel-esp32-03 [data-command=PARE]"))
        page1.screenshot(path=os.path.join(SHOTS, "multiagent_busy.png"), full_page=True)

        api("/__mock/release", {})
        wait_op(page1, "esp32-03", "confirmed")
        wait_op(page2, "esp32-01", "confirmed")
        page1.wait_for_function("S.agents.get('esp32-01').operation_state==='available' && S.agents.get('esp32-03').operation_state==='available'", timeout=5000)
        check("cada painel recebe somente seu Result", "TEMPERATURA=23.45" in page1.inner_text("#panel-esp32-03 [data-f=result]") and "ok:esp32-01:LED_ON" in page2.inner_text("#panel-esp32-01 [data-f=result]"))
        check("duração por operação é exibida", page1.inner_text("#panel-esp32-03 [data-f=duration]") != "—" and page2.inner_text("#panel-esp32-01 [data-f=duration]") != "—")
        print("TIMING parallel_ui_total_ms=%.3f" % ((time.time() - started) * 1000), flush=True)
        page1.screenshot(path=os.path.join(SHOTS, "multiagent_parallel.png"), full_page=True)

        setmode(scenario="busy")
        before = len(state()["posts"])
        page2.click("#panel-esp32-01 [data-command=LED_ON]")
        wait_op(page2, "esp32-01", "rejected")
        check("409 mostra recusa clara e operação ativa", "Agente ocupado" in page2.inner_text("#panel-esp32-01 [data-f=feedback]") and state()["posts"][-1]["cmd"] == "LED_ON")
        check("409 oferece retry sem repetir automaticamente", page2.locator("#panel-esp32-01 [data-f=retry]").is_visible() and len(state()["posts"]) == before + 1)
        check("retry fica bloqueado enquanto ocupado", page2.is_disabled("#panel-esp32-01 [data-f=retry]"))
        setmode(scenario="ok")
        emit({"event": "agent_state_changed", "agent_id": "esp32-01", "operation_state": "available", "op_id": "external-op"})
        page2.wait_for_function("!document.querySelector('#panel-esp32-01 [data-f=retry]').disabled", timeout=4000)
        page2.click("#panel-esp32-01 [data-f=retry]")
        wait_op(page2, "esp32-01", "confirmed")
        check("retry manual cria exatamente uma nova operação", len(state()["posts"]) == before + 2 and state()["posts"][-1]["cmd"] == "LED_ON")

        setmode(scenario="ok")
        previous = page1.evaluate("S.panels.get('esp32-03').order.length")
        page1.click("#panel-esp32-03 [data-command=LER_SENSORES]")
        page1.wait_for_function("previous => S.panels.get('esp32-03').order.length>previous", arg=previous, timeout=4000)
        wait_op(page1, "esp32-03", "confirmed")
        check("leitura conjunta atualiza cinco grandezas", page1.inner_text("#panel-esp32-03 [data-q=temperatura] [data-f=value]") == "23.45" and page1.inner_text("#panel-esp32-03 [data-q=pressao] [data-f=value]") == "1013.3" and page1.inner_text("#panel-esp32-03 [data-q=corrente] [data-f=value]") == "0.123")
        check("Result alimenta gráficos SVG", page1.locator("#panel-esp32-03 [data-q=temperatura] circle.point").count() >= 1)
        operation_id = page1.evaluate("[...S.panels.get('esp32-03').ops.values()].filter(o=>o.cmd==='LER_SENSORES').pop().id")
        sample_count = page1.evaluate("S.panels.get('esp32-03').samples.temperatura.length")
        emit({"event": "result_received", "agent_id": "esp32-03", "op_id": operation_id, "stdout": "TEMPERATURA=99 C", "stderr": ""})
        time.sleep(0.2)
        check("Result duplicado não duplica amostra nem altera valor", page1.evaluate("S.panels.get('esp32-03').samples.temperatura.length") == sample_count and page1.inner_text("#panel-esp32-03 [data-q=temperatura] [data-f=value]") == "23.45", json.dumps({"before": sample_count, "after": page1.evaluate("S.panels.get('esp32-03').samples.temperatura.length"), "value": page1.inner_text("#panel-esp32-03 [data-q=temperatura] [data-f=value]"), "op": page1.evaluate(f"S.panels.get('esp32-03').ops.get('{operation_id}')")}, default=str))

        emit({"event": "command_created", "agent_id": "esp32-02", "op_id": "external-02", "command": "LIGAR"})
        emit({"event": "result_received", "agent_id": "esp32-02", "op_id": "external-02", "stdout": "somente-02", "stderr": ""})
        page1.wait_for_function("S.panels.get('esp32-02').ops.has('external-02')", timeout=3000)
        check("evento externo atualiza apenas o painel correto", "somente-02" in page1.inner_text("#panel-esp32-02") and "somente-02" not in page1.inner_text("#panel-esp32-03") and page2.evaluate("S.panels.has('esp32-02')") is False)

        before = len(state()["posts"])
        page1.click("#panel-esp32-03 [data-command=START]")
        time.sleep(0.15)
        check("START exige confirmação e não envia no primeiro clique", len(state()["posts"]) == before and "Confirmar START" in page1.inner_text("#panel-esp32-03 [data-command=START]"))
        previous = page1.evaluate("S.panels.get('esp32-03').order.length")
        page1.click("#panel-esp32-03 [data-command=START]")
        page1.wait_for_function("previous => S.panels.get('esp32-03').order.length>previous", arg=previous, timeout=4000)
        wait_op(page1, "esp32-03", "confirmed")
        check("START confirmado mostra incerteza do movimento físico", "possivelmente em movimento" in page1.inner_text("#panel-esp32-03 [data-f=motor-note]"))
        previous = page1.evaluate("S.panels.get('esp32-03').order.length")
        page1.click("#panel-esp32-03 [data-command=PARE]")
        page1.wait_for_function("previous => S.panels.get('esp32-03').order.length>previous", arg=previous, timeout=4000)
        wait_op(page1, "esp32-03", "confirmed")
        check("PARE é enviado quando disponível", state()["posts"][-1]["cmd"] == "PARE")

        page1.fill("#panel-esp32-03 [data-f=steps]", "0")
        check("MOVER inválido é bloqueado", page1.is_disabled("#panel-esp32-03 [data-f=mover]"))
        page1.fill("#panel-esp32-03 [data-f=steps]", "50")
        page1.select_option("#panel-esp32-03 [data-f=dir]", "esquerda")
        page1.select_option("#panel-esp32-03 [data-f=speed]", "rapida")
        before = len(state()["posts"])
        page1.click("#panel-esp32-03 [data-f=mover]")
        time.sleep(0.15)
        page1.click("#panel-esp32-03 [data-f=mover]")
        wait_op(page1, "esp32-03", "confirmed")
        last_post = state()["posts"][-1]
        check("MOVER exige dois cliques e envia um único POST com args", len(state()["posts"]) == before + 1 and last_post["args"] == {"dir": "esquerda", "steps": 50, "speed": "rapida"}, json.dumps(last_post))

        setmode(scenario="noretry")
        before = len(state()["posts"])
        page1.click("#panel-esp32-03 [data-f=mover]")
        page1.click("#panel-esp32-03 [data-f=mover]")
        wait_op(page1, "esp32-03", "failed")
        check("MOVER sem Result não é reenviado", len(state()["posts"]) == before + 1 and "Não foi reenviado" in page1.inner_text("#panel-esp32-03 [data-f=feedback]"))

        setmode(scenario="fast")
        page1.click("#panel-esp32-03 [data-command=TEMPERATURA]")
        wait_op(page1, "esp32-03", "confirmed")
        check("eventos anteriores ao HTTP 202 não regridem a operação", "23.45" in page1.inner_text("#panel-esp32-03 [data-f=result]"))

        xss = '<img src=x onerror="window.__xss=1">'
        emit({"event": "command_created", "agent_id": "esp32-02", "op_id": "xss-02", "command": "LIGAR"})
        emit({"event": "result_received", "agent_id": "esp32-02", "op_id": "xss-02", "stdout": xss, "stderr": ""})
        time.sleep(0.25)
        check("Result é renderizado como texto, sem XSS", page1.evaluate("window.__xss") is None and page1.locator("#panel-esp32-02 img").count() == 0 and xss in page1.inner_text("#panel-esp32-02 [data-f=result]"))

        api("/__mock/drop", {})
        page1.wait_for_function("!S.sse", timeout=5000)
        check("queda de SSE é indicada", "desconectado" in page1.inner_text("#sse-text"))
        setmode(gateway_down=True)
        page1.evaluate("loadAgents()")
        page1.wait_for_function("S.gw===false", timeout=4000)
        check("Gateway indisponível bloqueia comandos", page1.is_disabled("#panel-esp32-03 [data-command=LER_SENSORES]"))
        setmode(gateway_down=False)
        page1.evaluate("loadAgents()")
        page1.wait_for_function("S.gw===true", timeout=4000)

        invalid = open_page(context2, "%3Cscript%3E")
        invalid.wait_for_function("S.selected.has('esp32-03')", timeout=4000)
        check("?agent= inválido usa seleção padrão segura", invalid.evaluate("S.selected.has('esp32-03')") is True)
        invalid.close()

        mobile_context = browser.new_context(viewport={"width": 390, "height": 800})
        mobile = open_page(mobile_context, "esp32-03")
        dimensions = mobile.evaluate("[document.documentElement.scrollWidth,innerWidth]")
        check("layout móvel não cria rolagem horizontal", dimensions[0] <= dimensions[1] + 1, str(dimensions))
        mobile.screenshot(path=os.path.join(SHOTS, "multiagent_mobile.png"), full_page=True)
        mobile_context.close()

        check("nenhum erro JavaScript durante os testes", not errors, "; ".join(errors))
        context1.close()
        context2.close()
        browser.close()
finally:
    process.terminate()

failures = [result for result in RESULTS if not result[1]]
print(f"\n{len(RESULTS)-len(failures)}/{len(RESULTS)} verificações passaram")
sys.exit(1 if failures else 0)
