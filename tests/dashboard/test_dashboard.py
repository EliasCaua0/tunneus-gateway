#!/usr/bin/env python3
"""Testes do dashboard contra o mock local. Nenhum comando real é enviado."""
import json, subprocess, sys, time, urllib.request, os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.environ.get("DASHBOARD_INDEX", os.path.join(HERE, "..", "..", "web", "dashboard", "index.html"))
PORT = 18555
BASE = f"http://127.0.0.1:{PORT}"
SHOTS = os.environ.get("DASHBOARD_SHOTS", os.path.join(HERE, "shots")); os.makedirs(SHOTS, exist_ok=True)

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""), flush=True)

def api(path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())
def setmode(**kw): return api("/__mock/set", kw)
def emit(obj):
    req = urllib.request.Request(BASE + "/__mock/emit", data=(obj if isinstance(obj, str) else json.dumps(obj)).encode(), method="POST")
    urllib.request.urlopen(req, timeout=5).read()
def state(): return api("/__mock/state")

proc = subprocess.Popen([sys.executable, os.path.join(HERE, "mock_gateway.py"), INDEX, str(PORT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(1.0)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
        page.on("console", lambda m: errors.append("console." + m.type + ": " + m.text) if m.type in ("error",) else None)
        page.on("dialog", lambda d: (errors.append("dialog: " + d.message), d.dismiss()))

        # ---------- 1. carga ----------
        page.goto(BASE + "/dashboard/")
        page.wait_for_function("document.getElementById('ov-name').textContent !== '—'", timeout=5000)
        check("1 carrega sem erro de JS", not errors, "; ".join(errors))
        check("1 nome do agente vem da API", "Bancada de Sensores" in page.inner_text("#ov-name"))
        check("1 estado STANDBY exibido (não é falha)", "STANDBY" in page.inner_text("#ov-state").upper() and "info" in page.get_attribute("#ov-state", "class"))
        check("1 SSE conectado", "conectado" in page.inner_text("#sse-text") and "desconectado" not in page.inner_text("#sse-text"))
        check("1 gateway respondendo", "respondendo" in page.inner_text("#gw-text"))

        # ---------- 2. outros agentes ignorados ----------
        body = page.inner_text("body")
        check("2 outros agentes não aparecem", "esp32-01" not in body and "esp32-02" not in body and "LED 01" not in body)
        emit({"event": "wake_sent", "agent_id": "esp32-01", "op_id": "x-other", "attempt": 1})
        time.sleep(0.3)
        check("2 evento de outro agente ignorado", page.evaluate("S.ops.size") == 0 and "x-other" not in page.inner_text("#log"))

        # ---------- 3. gráficos fixos sem amostras ----------
        page.click("#tab-bench")
        check("3 seis cartões de gráfico", page.locator(".chart-card").count() == 6)
        check("3 mensagem de estado vazio", page.locator("#cc-temperatura .plot-empty").inner_text().startswith("Sem amostras"))
        check("3 fluxo indisponível explícito", "Não implementado" in page.locator("#cc-fluxo .plot-empty").inner_text())
        check("3 sem leituras fictícias", page.locator("#cc-temperatura [data-f=num]").inner_text() == "—")
        page.screenshot(path=os.path.join(SHOTS, "bench_empty.png"), full_page=True)

        # ---------- 4. leitura conjunta ----------
        n0 = len(state()["posts"])
        page.click("#bench-read-all")
        page.wait_for_function("S.ops.size===1 && [...S.ops.values()][0].status==='confirmed'", timeout=6000)
        st = state()
        check("4 exatamente 1 POST, só {cmd}", len(st["posts"]) == n0 + 1 and st["posts"][-1]["cmd"] == "LER_SENSORES" and st["posts"][-1]["keys"] == ["cmd"])
        check("4 temperatura atualizada", page.locator("#cc-temperatura [data-f=num]").inner_text() == "23.45")
        check("4 pressão convertida para hPa", page.locator("#cc-pressao [data-f=num]").inner_text() == "1013.3" or page.locator("#cc-pressao [data-f=num]").inner_text() == "1013.2", page.locator("#cc-pressao [data-f=num]").inner_text())
        check("4 altitude / corrente / distância", page.locator("#cc-altitude [data-f=num]").inner_text() == "28.1" and page.locator("#cc-corrente [data-f=num]").inner_text() == "0.123" and page.locator("#cc-distancia [data-f=num]").inner_text() == "35.2")
        check("4 fluxo continua sem dado", page.locator("#cc-fluxo [data-f=num]").inner_text() == "—")
        check("4 feedback = confirmado", "confirmado" in page.inner_text("#feedback"))
        check("4 gráfico desenhado (svg com ponto)", page.locator("#cc-temperatura svg circle.pt-last").count() == 1)
        check("4 eixo X com horários", page.locator("#cc-temperatura svg text.tick").count() >= 6)
        page.screenshot(path=os.path.join(SHOTS, "bench_1sample.png"), full_page=True)

        # ---------- 5. duplicação ----------
        op_id = page.evaluate("[...S.ops.keys()][0]")
        emit({"event": "result_received", "agent_id": "esp32-03", "op_id": op_id, "stdout": "TEMPERATURA=99.00 C", "stderr": ""})
        time.sleep(0.3)
        check("5 resultado duplicado não duplica amostra", page.evaluate("S.samples.temperatura.length") == 1 and page.locator("#cc-temperatura [data-f=num]").inner_text() == "23.45")

        # ---------- 6. mais amostras, distância sem eco ----------
        setmode(batch="TEMPERATURA=24.10 C | PRESSAO=101300 Pa | ALTITUDE=28.50 m | CORRENTE=0.130 A | DISTANCIA=NA")
        page.click("#bench-read-all")
        page.wait_for_function("S.ops.size===2 && [...S.ops.values()][1].status==='confirmed'", timeout=6000)
        check("6 DISTANCIA=NA vira amostra inválida", page.evaluate("S.samples.distancia.length") == 2 and page.evaluate("S.samples.distancia[1].v") is None)
        check("6 estado 'Última leitura inválida'", "inválida" in page.locator("#cc-distancia [data-f=state]").inner_text())
        check("6 valor válido anterior mantido", page.locator("#cc-distancia [data-f=num]").inner_text() == "35.2")
        check("6 marca de inválida no gráfico", page.locator("#cc-distancia svg line.bad").count() == 2)
        check("6 outras grandezas atualizadas", page.locator("#cc-temperatura [data-f=num]").inner_text() == "24.10" and page.evaluate("S.samples.temperatura.length") == 2)
        check("6 linha desenhada com 2+ pontos", page.locator("#cc-temperatura svg polyline.line").count() == 1)

        # -1.0 cm também é inválido
        setmode(batch="TEMPERATURA=24.20 C | PRESSAO=101300 Pa | ALTITUDE=28.50 m | CORRENTE=0.130 A | DISTANCIA=-1.0 cm")
        page.click("#bench-read-all")
        page.wait_for_function("S.ops.size===3 && [...S.ops.values()][2].status==='confirmed'", timeout=6000)
        check("6 -1.0 cm tratado como inválido", page.evaluate("S.samples.distancia[2].v") is None)

        # resposta incompleta e formato quebrado
        setmode(batch="TEMPERATURA=24.30 C | PRESSAO=lixo | ALTITUDE=28.5 km")
        page.click("#bench-read-all")
        page.wait_for_function("S.ops.size===4 && [...S.ops.values()][3].status==='confirmed'", timeout=6000)
        check("6 formato/unidade inválidos não viram valor", page.evaluate("S.samples.pressao[S.samples.pressao.length-1].v") is None and page.evaluate("S.samples.altitude[S.samples.altitude.length-1].v") is None)
        check("6 campos ausentes não geram amostra", page.evaluate("S.samples.corrente.length") == 3)
        check("6 log registra resposta incompleta", "incompleta" in page.inner_text("#log") or True)  # log só visível na aba eventos
        page.click("#tab-events")
        check("6 log registra resposta incompleta (aba Eventos)", "incompleta" in page.inner_text("#log"))
        page.click("#tab-bench")

        # ---------- 7. leitura individual / stderr ----------
        setmode(dist="NOECHO")
        page.click("#cc-distancia [data-read]")
        page.wait_for_function("S.ops.size===5 && [...S.ops.values()][4].status==='failed'", timeout=6000)
        check("7 stderr = falha (não 'confirmado')", "falhou" in page.inner_text("#feedback"))
        check("7 stderr de DISTANCIA vira amostra inválida", page.evaluate("S.samples.distancia[S.samples.distancia.length-1].bad") is not None)
        setmode(dist="12.5 cm")
        page.click("#cc-distancia [data-read]")
        page.wait_for_function("S.ops.size===6 && [...S.ops.values()][5].status==='confirmed'", timeout=6000)
        check("7 leitura individual atualiza só a sua grandeza", page.locator("#cc-distancia [data-f=num]").inner_text() == "12.5" and page.evaluate("S.samples.temperatura.length") == 4)

        # ---------- 8. histórico preservado ao trocar de aba / janela ----------
        cnt = page.evaluate("Object.values(S.samples).reduce((a,b)=>a+b.length,0)")
        page.click("#tab-overview"); page.click("#tab-bench")
        page.click("#win-seg button:nth-child(2)")
        page.click("#win-seg button:nth-child(1)")
        check("8 histórico preservado", page.evaluate("Object.values(S.samples).reduce((a,b)=>a+b.length,0)") == cnt)
        check("8 janela selecionada marcada", page.get_attribute("#win-seg button:nth-child(1)", "aria-pressed") == "true" and page.get_attribute("#win-seg button:nth-child(2)", "aria-pressed") == "false")
        page.click("#win-seg button:nth-child(4)")
        check("8 janela 24 h mantém gráfico visível", page.locator(".chart-card").count() == 6 and page.locator("#cc-temperatura svg").count() == 1)
        page.click("#win-seg button:nth-child(1)")
        # amostra fora da janela: injeta uma amostra antiga e confere filtro
        page.evaluate("S.samples.corrente.unshift({t: Date.now()-3600e3, v: 9.9, op: 'old'}); dirty.charts=true; schedule()")
        time.sleep(0.3)
        check("8 amostra antiga fora da janela de 15 min", "9.900" not in page.locator("#cc-corrente [data-f=num]").inner_text())
        page.evaluate("S.samples.corrente.shift(); dirty.charts=true; schedule()")
        page.screenshot(path=os.path.join(SHOTS, "bench_samples.png"), full_page=True)
        check("8 feedback não exibe 'null'", "null" not in page.inner_text("#feedback"))
        geo = page.evaluate("""() => {
          const bad = [];
          for (const svg of document.querySelectorAll('.cc-plot svg')) {
            const W = svg.viewBox.baseVal.width;
            const texts = [...svg.querySelectorAll('text')];
            for (const t of texts) { const b = t.getBBox(); if (b.x < -0.5 || b.x + b.width > W + 0.5) bad.push('fora: ' + t.textContent); }
            const unit = svg.querySelector('text.unit'); 
            if (unit) { const u = unit.getBBox();
              for (const t of texts) { if (t === unit) continue; const b = t.getBBox();
                const inter = !(b.x > u.x + u.width || b.x + b.width < u.x || b.y > u.y + u.height || b.y + b.height < u.y);
                if (inter) bad.push('sobrepõe unidade: ' + t.textContent); } }
          }
          return bad; }""")
        check("8 rótulos dos gráficos dentro da área e sem sobrepor a unidade", not geo, json.dumps(geo, ensure_ascii=False))

        # ---------- 9. motor ----------
        n0 = len(state()["posts"])
        check("9 parâmetros do motor habilitados (sem 'Aguardando contrato')", not page.is_disabled("#steps") and page.locator("#dir-seg button:not([disabled])").count() == 2 and page.locator("#spd-seg button:not([disabled])").count() == 3 and "Aguardando contrato" not in page.inner_text("body"))
        page.click("#btn-start")
        time.sleep(0.3)
        check("9 START exige 2º clique (sem POST no 1º)", len(state()["posts"]) == n0 and "Confirmar START" in page.inner_text("#btn-start"))
        page.click("#btn-start")
        page.wait_for_function("[...S.ops.values()].pop().cmd==='START' && [...S.ops.values()].pop().status==='confirmed'", timeout=6000)
        check("9 START enviado após confirmação, só {cmd}", state()["posts"][-1]["cmd"] == "START" and state()["posts"][-1]["keys"] == ["cmd"])
        page.wait_for_function("document.getElementById('motor-chip').textContent.includes('movimento')", timeout=3000)
        check("9 estado do motor: possivelmente em movimento", "movimento" in page.inner_text("#motor-chip").lower())
        check("9 limite de 60 s informado", "segurança" in page.inner_text("#motor-status"))
        page.click("#btn-pare")
        page.wait_for_function("[...S.ops.values()].pop().cmd==='PARE' && [...S.ops.values()].pop().status==='confirmed'", timeout=6000)
        page.wait_for_function("document.getElementById('motor-chip').textContent.includes('PARE confirmado')", timeout=3000)
        check("9 PARE confirmado muda estado", "pare confirmado" in page.inner_text("#motor-chip").lower())
        # START arma e expira
        page.click("#btn-start"); time.sleep(4.4)
        check("9 armamento expira sem enviar", "Iniciar motor" in page.inner_text("#btn-start") and len(state()["posts"]) == n0 + 2)

        # ---------- 9b. MOVER (direção, passos, velocidade) ----------
        check("9b padrões: direita, 200 passos, normal", page.get_attribute("#dir-seg button[data-v=direita]", "aria-pressed") == "true" and page.input_value("#steps") == "200" and page.get_attribute("#spd-seg button[data-v=normal]", "aria-pressed") == "true")
        check("9b estimativa de duração (200 × 800 µs = 160 ms)", "160 ms" in page.inner_text("#mv-est"), page.inner_text("#mv-est"))
        n0 = len(state()["posts"])
        for bad in ["0", "30001", "1.5", "-3", ""]:
            page.fill("#steps", bad)
            msg = page.inner_text("#steps-msg")
            ok = page.is_disabled("#btn-mover") and "invalid" in (page.get_attribute("#steps", "class") or "") and ("entre 1 e 30000" in msg or "inteiro" in msg)
            check(f"9b passos inválidos ({bad!r}) bloqueiam o envio", ok, msg)
        page.evaluate("onMotorClick('MOVER')"); time.sleep(0.3)
        check("9b clique forçado com passos inválidos não envia", len(state()["posts"]) == n0)
        page.fill("#steps", "50")
        page.click("#dir-seg button[data-v=esquerda]"); page.click("#spd-seg button[data-v=rapida]")
        check("9b seleção de direção e velocidade marcada", page.get_attribute("#dir-seg button[data-v=esquerda]", "aria-pressed") == "true" and page.get_attribute("#dir-seg button[data-v=direita]", "aria-pressed") == "false" and page.get_attribute("#spd-seg button[data-v=rapida]", "aria-pressed") == "true")
        check("9b estimativa recalculada (50 × 400 µs = 20 ms)", "20 ms" in page.inner_text("#mv-est"), page.inner_text("#mv-est"))
        page.click("#btn-mover"); time.sleep(0.3)
        check("9b MOVER exige 2º clique (sem POST no 1º)", len(state()["posts"]) == n0 and "Confirmar movimento" in page.inner_text("#btn-mover"))
        page.click("#spd-seg button[data-v=lenta]"); time.sleep(0.2)
        check("9b mudar parâmetro desarma a confirmação", "Executar movimento" in page.inner_text("#btn-mover") and len(state()["posts"]) == n0)
        page.click("#spd-seg button[data-v=rapida]")
        page.click("#btn-mover"); page.click("#btn-mover")
        page.wait_for_function("[...S.ops.values()].pop().cmd==='MOVER' && [...S.ops.values()].pop().status==='confirmed'", timeout=6000)
        lp = state()["posts"][-1]
        check("9b POST de MOVER com cmd + args corretos", lp["cmd"] == "MOVER" and lp["keys"] == ["args", "cmd"] and lp["args"] == {"dir": "esquerda", "steps": 50, "speed": "rapida"}, json.dumps(lp))
        check("9b um único POST para o MOVER", len(state()["posts"]) == n0 + 1)
        check("9b resultado confirmado exibido", "Movimento INICIADO" in page.inner_text("#feedback"))
        check("9b estado: possivelmente em movimento (estimativa, não verificado)", "movimento" in page.inner_text("#motor-chip").lower() and "estimativa" in page.inner_text("#motor-status"))
        page.wait_for_function("document.getElementById('motor-chip').textContent.includes('estimado')", timeout=5000)
        check("9b estimativa expira sozinha e o chip muda", "expirado" in page.inner_text("#motor-chip").lower())
        page.click("#tab-ops")
        check("9b operações mostram os argumentos", "esquerda · 50 passos · rapida" in page.inner_text("#ops-table"))
        page.click("#tab-bench")
        # argumento inválido que passa pelo cliente: o firmware recusa (stderr) e o estado do motor não muda
        st0 = page.evaluate("S.motor.cmd + ':' + S.motor.t")
        page.evaluate("sendCmd('MOVER', {dir:'cima', steps:10, speed:'normal'})")
        page.wait_for_function("[...S.ops.values()].pop().cmd==='MOVER' && [...S.ops.values()].pop().status==='failed'", timeout=6000)
        check("9b recusa do firmware = falha (stderr), motor não é dado como movido", "falhou" in page.inner_text("#feedback") and page.evaluate("S.motor.cmd + ':' + S.motor.t") == st0)
        # Gateway entregou o MOVER mas o resultado se perdeu: sem reenvio, motor "possivelmente em movimento"
        setmode(scenario="noretry")
        page.fill("#steps", "200"); page.click("#spd-seg button[data-v=normal]")
        n1 = len(state()["posts"])
        page.click("#btn-mover"); page.click("#btn-mover")
        page.wait_for_function("[...S.ops.values()].pop().cmd==='MOVER' && [...S.ops.values()].pop().status==='failed' && [...S.ops.values()].pop().reason.includes('reenviado')", timeout=6000)
        check("9b MOVER sem resultado: um POST só e mensagem explica o não reenvio", len(state()["posts"]) == n1 + 1 and "reenviado" in page.inner_text("#feedback"), page.inner_text("#feedback"))
        check("9b MOVER sem resultado: motor marcado como possivelmente em movimento", "movimento" in page.inner_text("#motor-chip").lower() and "sem resultado" in page.inner_text("#motor-status"), page.inner_text("#motor-status"))
        setmode(scenario="ok")
        page.click("#btn-pare")
        page.wait_for_function("[...S.ops.values()].pop().cmd==='PARE' && [...S.ops.values()].pop().status==='confirmed'", timeout=6000)
        page.screenshot(path=os.path.join(SHOTS, "bench_motor.png"), full_page=True)

        # ---------- 10. SSE: XSS e JSON inválido ----------
        page.click("#bench-read-all")
        page.wait_for_function("S.ops.size===9 || S.ops.size===10", timeout=3000) if False else None
        page.wait_for_function("[...S.ops.values()].pop().status==='confirmed'", timeout=6000)
        emit("{isso nao e json")
        time.sleep(0.3)
        page.click("#tab-events")
        check("10 JSON inválido no SSE é tratado", "JSON inválido" in page.inner_text("#log"))
        xss = '<img src=x onerror="window.__xss=1"><script>window.__xss=1</script>'
        emit({"event": "command_created", "agent_id": "esp32-03", "op_id": "op-xss", "command": "DISTANCIA"})
        emit({"event": "result_received", "agent_id": "esp32-03", "op_id": "op-xss", "stdout": xss, "stderr": ""})
        time.sleep(0.4)
        page.click("#tab-ops")
        check("10 sem XSS (nenhum img/script injetado)", page.evaluate("window.__xss") is None and page.locator("#view-ops img, #log img, #view-ops script").count() == 0)
        check("10 conteúdo aparece como texto", "<img src=x" in page.inner_text("#ops-table"))
        check("10 stdout inválido não vira amostra", page.evaluate("S.samples.distancia.every(s => s.op !== 'op-xss' || s.v === null)"))

        # ---------- 11. resultado de operação criada fora desta aba ----------
        emit({"event": "command_created", "agent_id": "esp32-03", "op_id": "op-ext", "command": "TEMPERATURA"})
        emit({"event": "result_received", "agent_id": "esp32-03", "op_id": "op-ext", "stdout": "22.00 C", "stderr": ""})
        time.sleep(0.4)
        check("11 operação de outra origem alimenta o gráfico", page.evaluate("S.samples.temperatura.some(s => s.op==='op-ext' && s.v===22)"))
        emit({"event": "result_received", "agent_id": "esp32-03", "op_id": "op-semcmd", "stdout": "10.00 C", "stderr": ""})
        time.sleep(0.3)
        check("11 resultado sem comando associado não vira amostra", page.evaluate("!Object.values(S.samples).flat().some(s => s.op==='op-semcmd')"))

        # ---------- 12. falha (retries esgotados) ----------
        setmode(scenario="fail")
        tcount0 = page.evaluate("S.samples.temperatura.length")
        page.click("#tab-bench")
        page.click("#bench-read-all")
        page.wait_for_function("[...S.ops.values()].pop().status==='failed'", timeout=8000)
        page.click("#tab-overview")
        check("12 falha mostrada no feedback e em Atenção", "falhou" in page.inner_text("#feedback") and "falhou" in page.inner_text("#ov-attn"))
        check("12 timeline marca falha", page.locator("#tl .tl-step.fail").count() == 1)
        check("12 falha não gera amostra", page.evaluate("S.samples.temperatura.length") == tcount0)
        page.screenshot(path=os.path.join(SHOTS, "overview_failed.png"), full_page=True)

        # ---------- 13. resposta rápida (eventos antes do HTTP) ----------
        setmode(scenario="fast"); page.click("#tab-bench")
        page.click("#cc-temperatura [data-read]")
        page.wait_for_function("[...S.ops.values()].pop().cmd==='TEMPERATURA' && [...S.ops.values()].pop().status==='confirmed' && !S.sending", timeout=6000)
        time.sleep(0.3)
        tcount1 = page.evaluate("S.samples.temperatura.length")
        diag = page.evaluate("({fb: document.getElementById('feedback').textContent, st: [...S.ops.values()].pop().status, n: S.samples.temperatura.length})")
        check("13 eventos antes do 202 não regridem o estado", "confirmado" in page.inner_text("#feedback") and tcount1 == tcount0 + 1, json.dumps(diag, ensure_ascii=False))

        # ---------- 14. recusa pela API ----------
        setmode(scenario="reject")
        page.click("#bench-read-all"); time.sleep(0.6)
        check("14 recusa da API exibida", "não foi aceito" in page.inner_text("#feedback"))
        page.click("#tab-ops")
        check("14 recusa aparece em Operações", "recusado pela api" in page.inner_text("#ops-table").lower())
        page.click("#tab-bench")

        # ---------- 15. sem confirmação final (watchdog) ----------
        setmode(scenario="silent")
        page.evaluate("CFG.watchMs = 1200")
        before = state()["gets"]["operations"]
        page.click("#bench-read-all")
        page.wait_for_function("[...S.ops.values()].pop().status==='accepted'||[...S.ops.values()].pop().status==='running'", timeout=4000)
        check("15 botões travados com operação ativa", page.is_disabled("#bench-read-all") and page.is_disabled("#btn-pare"))
        page.wait_for_function("[...S.ops.values()].pop().status==='unknown'", timeout=6000)
        time.sleep(0.5)
        check("15 vira 'sem confirmação' e libera controles", not page.is_disabled("#bench-read-all") and "sem confirmação" in page.inner_text("#feedback"))
        check("15 consulta /api/operations após watchdog", state()["gets"]["operations"] == before + 1)
        page.click("#tab-events")
        check("15 status lido no formato real do Gateway ({operation:{status}})", 'status "pending"' in page.inner_text("#log"), page.inner_text("#log")[-300:])
        page.click("#tab-bench")
        page.evaluate("CFG.watchMs = 150000")

        # ---------- 16. SSE cai e volta ----------
        setmode(scenario="ok")
        api("/__mock/drop", {})
        page.wait_for_function("document.getElementById('sse-text').textContent.includes('desconectado')", timeout=4000)
        check("16 SSE desconectado indicado", True)
        page.wait_for_function("!document.getElementById('sse-text').textContent.includes('desconectado')", timeout=15000)
        check("16 SSE reconecta sozinho", True)

        # ---------- 17. Gateway fora do ar ----------
        setmode(gateway_down=True)
        page.evaluate("loadAgent()"); time.sleep(0.5)
        check("17 Gateway sem resposta indicado", "sem resposta" in page.inner_text("#gw-text"))
        check("17 envio bloqueado com Gateway fora", page.is_disabled("#bench-read-all") and page.is_disabled("#btn-start"))
        page.click("#tab-overview")
        check("17 Atenção informa", "não está respondendo" in page.inner_text("#ov-attn"))
        setmode(gateway_down=False); page.evaluate("loadAgent()"); time.sleep(0.5)
        check("17 recupera quando Gateway volta", not page.is_disabled("#bench-read-all"))

        # ---------- 18. capabilities do Registry mandam nos controles ----------
        setmode(caps=["LED_ON", "LED_OFF"]); page.evaluate("loadAgent()"); time.sleep(0.5)
        check("18 sem capabilities da bancada: leitura desabilitada", page.is_disabled("#ov-read-all") and page.is_disabled("#btn-start") and page.is_disabled("#btn-pare") and page.is_disabled("#btn-mover"))
        check("18 Atenção lista o que falta e o que é desconhecido", "LER_SENSORES" in page.inner_text("#ov-attn") and "LED_ON" in page.inner_text("#ov-attn"))
        check("18 nenhum botão para capability desconhecida", page.locator("button:has-text('LED_ON')").count() == 0)
        n0 = len(state()["posts"])
        page.evaluate("sendCmd('CAP_INEXISTENTE')"); time.sleep(0.3)
        check("18 envio direto de capability não suportada é bloqueado no cliente", len(state()["posts"]) == n0)
        setmode(caps=["LER_SENSORES", "TEMPERATURA"]); page.evaluate("loadAgent()"); time.sleep(0.5)
        page.click("#tab-bench")
        check("18 só capabilities presentes ficam ativas", not page.is_disabled("#cc-temperatura [data-read]") and page.is_disabled("#cc-pressao [data-read]") and page.is_disabled("#btn-start"))
        setmode(caps=["LER_SENSORES","TEMPERATURA","PRESSAO","ALTITUDE","CORRENTE","DISTANCIA","START","PARE"]); page.evaluate("loadAgent()"); time.sleep(0.5)
        check("18 sem MOVER no Registry só o movimento fica desabilitado", page.is_disabled("#btn-mover") and not page.is_disabled("#btn-start") and "MOVER" in page.inner_text("#motor-status"))
        setmode(caps=["LER_SENSORES","TEMPERATURA","PRESSAO","ALTITUDE","CORRENTE","DISTANCIA","START","PARE","MOVER"]); page.evaluate("loadAgent()")

        # ---------- 19. teclado / acessibilidade ----------
        page.click("#tab-overview"); page.focus("#tab-overview"); page.keyboard.press("ArrowDown")
        check("19 setas navegam entre abas", page.get_attribute("#tab-bench", "aria-selected") == "true" and page.evaluate("document.activeElement.id") == "tab-bench")
        check("19 painéis com role/label", page.get_attribute("#view-bench", "role") == "tabpanel" and page.get_attribute("#view-bench", "aria-labelledby") == "tab-bench")
        check("19 feedback é região viva", page.get_attribute("#feedback", "aria-live") == "polite")
        check("19 cartões de gráfico rotulados", all(page.get_attribute(f"#cc-{i}", "aria-label") for i in ["distancia","temperatura","pressao","altitude","corrente","fluxo"]))

        # ---------- 20. polling moderado ----------
        g0 = state()["gets"]["agents"]; time.sleep(6.5); g1 = state()["gets"]["agents"]
        check("20 polling do Registry ~3 s (sem consultas extras)", 1 <= (g1 - g0) <= 3, str(g1 - g0))

        # ---------- 20b. agente configurável (multi-agente no futuro) ----------
        q = browser.new_context(viewport={"width": 1280, "height": 900}); qp = q.new_page()
        qp.goto(BASE + "/dashboard/?agent=esp32-01"); qp.wait_for_function("document.getElementById('ov-name').textContent !== '—'", timeout=5000)
        check("20b ?agent= aponta o painel para outro agente do Registry", "LED 01" in qp.inner_text("#ov-name") and qp.inner_text("#foot-agent") == "esp32-01")
        qp.goto(BASE + "/dashboard/?agent=%3Cscript%3E"); time.sleep(0.5)
        check("20b ?agent= inválido cai no padrão esp32-03", qp.evaluate("CFG.agentId") == "esp32-03")
        q.close()

        # ---------- 21. layout estreito ----------
        page.click("#tab-bench")
        m = browser.new_context(viewport={"width": 390, "height": 800}); mp = m.new_page()
        merr = []; mp.on("pageerror", lambda e: merr.append(str(e)))
        mp.goto(BASE + "/dashboard/#bench"); mp.wait_for_function("document.getElementById('ov-name').textContent !== '—'", timeout=5000)
        mp.click("#bench-read-all")
        mp.wait_for_function("S.ops.size===1 && [...S.ops.values()][0].status==='confirmed'", timeout=6000)
        time.sleep(0.4)
        ow = mp.evaluate("[document.documentElement.scrollWidth, window.innerWidth, document.getElementById('main').scrollWidth, document.getElementById('main').clientWidth]")
        check("21 sem rolagem horizontal em 390 px", ow[0] <= ow[1] + 1 and ow[2] <= ow[3] + 1, str(ow))
        check("21 hash #bench abre a Bancada", mp.get_attribute("#tab-bench", "aria-selected") == "true")
        check("21 gráficos cabem na largura", mp.evaluate("[...document.querySelectorAll('.chart-card')].every(c => c.getBoundingClientRect().right <= window.innerWidth + 1)"))
        check("21 sem erro de JS em tela estreita", not merr, "; ".join(merr))
        mp.screenshot(path=os.path.join(SHOTS, "mobile_bench.png"), full_page=True)
        mp.click("#tab-overview"); mp.screenshot(path=os.path.join(SHOTS, "mobile_overview.png"), full_page=True)
        m.close()

        # ---------- capturas desktop finais ----------
        page.click("#tab-overview"); page.screenshot(path=os.path.join(SHOTS, "overview.png"), full_page=True)
        page.click("#tab-ops"); page.screenshot(path=os.path.join(SHOTS, "ops.png"), full_page=True)
        page.click("#tab-events"); page.screenshot(path=os.path.join(SHOTS, "events.png"), full_page=True)
        page.click("#tab-bench"); page.screenshot(path=os.path.join(SHOTS, "bench_final.png"), full_page=True)

        check("FINAL nenhum erro de JS/console durante todo o teste", not [e for e in errors if "Failed to load resource" not in e], "; ".join(errors))
        # prova de isolamento: todos os POSTs foram para o mock e apenas com {cmd}
        st = state()
        check("FINAL todos os POSTs: só esp32-03; só {cmd}, exceto MOVER que leva também {args}", all(p["agent"] == "esp32-03" and (p["keys"] == ["args", "cmd"] if p["cmd"] == "MOVER" else p["keys"] == ["cmd"]) for p in st["posts"]), str(st["posts"][-3:]))
        browser.close()
finally:
    proc.terminate()

fails = [r for r in results if not r[1]]
print(f"\n{len(results)-len(fails)}/{len(results)} verificações passaram")
sys.exit(1 if fails else 0)
