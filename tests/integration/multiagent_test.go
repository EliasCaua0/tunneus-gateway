package integration

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/arcanlab/tunneus/internal/api"
	"github.com/arcanlab/tunneus/internal/controller"
	"github.com/arcanlab/tunneus/internal/protocol"
	"github.com/arcanlab/tunneus/internal/registry"
	"github.com/arcanlab/tunneus/internal/session"
	"github.com/arcanlab/tunneus/internal/wake"
	wsHandler "github.com/arcanlab/tunneus/internal/websocket"
	gorilla "github.com/gorilla/websocket"
)

type commandObservation struct {
	agentID    string
	sessionID  string
	command    protocol.Command
	receivedAt time.Time
}

type testAgent struct {
	id     string
	secret string
	wakes  chan protocol.WakePacket
}

type testEnvironment struct {
	registry   *registry.Registry
	controller *controller.Controller
	server     *httptest.Server
	udp        *net.UDPConn
	sender     *wake.Sender
	agents     map[string]*testAgent
	commands   chan commandObservation
	errors     chan error
	wakeCounts map[string]*atomic.Int32
	wakeTimes  chan string
	resultGate chan struct{}
	done       chan struct{}
	release    sync.Once
}

func newTestEnvironment(t *testing.T, agentIDs ...string) *testEnvironment {
	t.Helper()
	env := &testEnvironment{
		registry:   registry.NewRegistry(""),
		controller: controller.NewController(),
		agents:     make(map[string]*testAgent),
		commands:   make(chan commandObservation, len(agentIDs)*2),
		errors:     make(chan error, 16),
		wakeCounts: make(map[string]*atomic.Int32),
		wakeTimes:  make(chan string, 16),
		resultGate: make(chan struct{}),
		done:       make(chan struct{}),
	}

	oldRegistry := registry.DefaultRegistry
	oldController := controller.DefaultController
	oldSender := wake.DefaultSender
	registry.DefaultRegistry = env.registry
	controller.DefaultController = env.controller

	for _, agentID := range agentIDs {
		secret := registry.GenerateSecret()
		env.registry.Set(&registry.Entry{
			AgentID:      agentID,
			Secret:       secret,
			LastIP:       "127.0.0.1",
			Capabilities: []string{"TEST"},
			Status:       "standby",
		})
		env.agents[agentID] = &testAgent{
			id:     agentID,
			secret: secret,
			wakes:  make(chan protocol.WakePacket, 4),
		}
		env.wakeCounts[agentID] = &atomic.Int32{}
	}

	var err error
	env.udp, err = net.ListenUDP("udp", &net.UDPAddr{IP: net.ParseIP("127.0.0.1"), Port: wake.WakePort})
	if err != nil {
		t.Fatalf("bind UDP de teste: %v", err)
	}
	env.sender, err = wake.NewSender()
	if err != nil {
		t.Fatalf("criar Wake sender: %v", err)
	}
	wake.DefaultSender = env.sender

	mux := http.NewServeMux()
	mux.HandleFunc("/api/agents", api.ListAgents)
	mux.HandleFunc("/api/agents/", api.AgentRouter)
	mux.HandleFunc("/api/events", api.SSEHandler)
	mux.HandleFunc("/ws", wsHandler.Handler)
	env.server = httptest.NewServer(mux)

	for _, agent := range env.agents {
		go env.runAgent(agent)
	}
	go env.receiveWakes()

	t.Cleanup(func() {
		env.release.Do(func() { close(env.resultGate) })
		close(env.done)
		env.server.Close()
		env.sender.Close()
		env.udp.Close()
		registry.DefaultRegistry = oldRegistry
		controller.DefaultController = oldController
		wake.DefaultSender = oldSender
	})
	return env
}

func (env *testEnvironment) receiveWakes() {
	buffer := make([]byte, 4096)
	for {
		n, _, err := env.udp.ReadFromUDP(buffer)
		if err != nil {
			return
		}
		var packet protocol.WakePacket
		if err := protocol.Decode(buffer[:n], &packet); err != nil {
			env.errors <- err
			continue
		}
		agent, ok := env.agents[packet.AgentID]
		if !ok {
			env.errors <- fmt.Errorf("Wake para agente desconhecido: %s", packet.AgentID)
			continue
		}
		env.wakeCounts[packet.AgentID].Add(1)
		env.wakeTimes <- fmt.Sprintf("agent=%s session=%s wake_at=%s", packet.AgentID, packet.SessionID, time.Now().Format(time.RFC3339Nano))
		agent.wakes <- packet
	}
}

func (env *testEnvironment) runAgent(agent *testAgent) {
	for {
		select {
		case <-env.done:
			return
		case packet := <-agent.wakes:
			if !registry.ValidateMAC(packet.Challenge, agent.id, packet.AuthMAC, agent.secret) {
				env.errors <- fmt.Errorf("Wake HMAC inválido para %s", agent.id)
				continue
			}
			wsURL := strings.Replace(env.server.URL, "http://", "ws://", 1) + "/ws"
			conn, _, err := gorilla.DefaultDialer.Dial(wsURL, nil)
			if err != nil {
				env.errors <- fmt.Errorf("WebSocket %s: %w", agent.id, err)
				continue
			}
			hello := protocol.Hello{
				Type:              protocol.TypeHello,
				AgentID:           agent.id,
				Agent:             "integration-test-agent",
				Version:           "4.1",
				SessionID:         packet.SessionID,
				ChallengeResponse: computeChallengeResponse(packet.Challenge, agent.secret),
			}
			if err := conn.WriteJSON(hello); err != nil {
				conn.Close()
				env.errors <- err
				continue
			}
			var welcome protocol.Welcome
			if err := conn.ReadJSON(&welcome); err != nil || !welcome.Authenticated {
				conn.Close()
				env.errors <- fmt.Errorf("Welcome %s: %v", agent.id, err)
				continue
			}
			var command protocol.Command
			if err := conn.ReadJSON(&command); err != nil {
				conn.Close()
				env.errors <- err
				continue
			}
			env.commands <- commandObservation{agentID: agent.id, sessionID: packet.SessionID, command: command, receivedAt: time.Now()}
			<-env.resultGate
			err = conn.WriteJSON(protocol.Result{
				Type:      protocol.TypeResult,
				CommandID: command.CommandID,
				Stdout:    "ok:" + agent.id,
			})
			if err == nil {
				_ = conn.WriteJSON(protocol.Bye{Type: protocol.TypeBye, SessionID: packet.SessionID, Reason: "done"})
			}
			conn.Close()
			if err != nil {
				env.errors <- err
			}
		}
	}
}

func computeChallengeResponse(challenge, secret string) string {
	return registry.ComputeMAC(challenge, "", secret)
}

func (env *testEnvironment) postCommand(agentID string) (map[string]any, int, time.Duration, error) {
	started := time.Now()
	response, err := http.Post(env.server.URL+"/api/agents/"+agentID+"/command", "application/json", bytes.NewBufferString(`{"cmd":"TEST"}`))
	if err != nil {
		return nil, 0, 0, err
	}
	defer response.Body.Close()
	var body map[string]any
	err = json.NewDecoder(response.Body).Decode(&body)
	return body, response.StatusCode, time.Since(started), err
}

func (env *testEnvironment) waitCommand(t *testing.T) commandObservation {
	t.Helper()
	select {
	case observation := <-env.commands:
		return observation
	case err := <-env.errors:
		t.Fatalf("agente de teste: %v", err)
	case <-time.After(3 * time.Second):
		t.Fatal("timeout aguardando Command")
	}
	return commandObservation{}
}

func (env *testEnvironment) waitCompleted(t *testing.T, opID, agentID string) time.Duration {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		op, ok := env.controller.GetOperation(opID)
		if ok && op.Status == "completed" {
			for {
				if _, active := env.registry.ActiveOperation(agentID); !active {
					duration := op.UpdatedAt.Sub(op.CreatedAt)
					if duration < 0 {
						t.Fatalf("operação %s tem duração negativa: %s", opID, duration)
					}
					return duration
				}
				time.Sleep(time.Millisecond)
			}
		}
		select {
		case err := <-env.errors:
			t.Fatalf("agente de teste: %v", err)
		default:
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatalf("operação %s não concluiu", opID)
	return 0
}

func (env *testEnvironment) waitSessionRemoved(t *testing.T, sessionID string) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if _, ok := session.EphemeralStore.Get(sessionID); !ok {
			return
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatalf("sessão %s permaneceu aberta", sessionID)
}

func TestOperationsOnDifferentAgentsDispatchInParallel(t *testing.T) {
	env := newTestEnvironment(t, "esp32-01", "esp32-02", "esp32-03")
	started := time.Now()
	t.Logf("parallel_start=%s", started.Format(time.RFC3339Nano))

	type acceptance struct {
		agentID string
		body    map[string]any
		status  int
		latency time.Duration
		err     error
	}
	acceptances := make(chan acceptance, 3)
	for _, agentID := range []string{"esp32-01", "esp32-02", "esp32-03"} {
		go func(agentID string) {
			body, status, latency, err := env.postCommand(agentID)
			acceptances <- acceptance{agentID: agentID, body: body, status: status, latency: latency, err: err}
		}(agentID)
	}

	operations := make(map[string]string)
	for i := 0; i < 3; i++ {
		accepted := <-acceptances
		if accepted.err != nil {
			t.Fatal(accepted.err)
		}
		if accepted.status != http.StatusAccepted {
			t.Fatalf("POST %s: status %d, body=%v", accepted.agentID, accepted.status, accepted.body)
		}
		operations[accepted.agentID] = accepted.body["op_id"].(string)
		t.Logf("accepted agent=%s op=%s latency=%s", accepted.agentID, operations[accepted.agentID], accepted.latency)
	}

	observations := make([]commandObservation, 0, 3)
	for i := 0; i < 3; i++ {
		observation := env.waitCommand(t)
		observations = append(observations, observation)
		t.Logf("command_received agent=%s op=%s at=%s", observation.agentID, observation.command.CommandID, observation.receivedAt.Format(time.RFC3339Nano))
	}
	for i := 0; i < 3; i++ {
		t.Log(<-env.wakeTimes)
	}

	env.release.Do(func() { close(env.resultGate) })
	for agentID, opID := range operations {
		env.waitCompleted(t, opID, agentID)
		t.Logf("completed agent=%s op=%s total_from_start=%s", agentID, opID, time.Since(started))
	}
	for _, observation := range observations {
		env.waitSessionRemoved(t, observation.sessionID)
	}
	t.Logf("parallel_total=%s", time.Since(started))
}

func TestBusyAgentReturnsImmediate409WithoutSecondWake(t *testing.T) {
	env := newTestEnvironment(t, "esp32-01")
	first, status, _, err := env.postCommand("esp32-01")
	if err != nil || status != http.StatusAccepted {
		t.Fatalf("primeiro POST: status=%d body=%v err=%v", status, first, err)
	}
	firstOpID := first["op_id"].(string)
	observation := env.waitCommand(t)
	wakeTime := <-env.wakeTimes
	t.Log(wakeTime)

	second, status, latency, err := env.postCommand("esp32-01")
	if err != nil {
		t.Fatal(err)
	}
	if status != http.StatusConflict {
		t.Fatalf("segundo POST: status=%d body=%v", status, second)
	}
	if second["error"] != "agent_busy" || second["active_op_id"] != firstOpID {
		t.Fatalf("resposta 409 inválida: %v", second)
	}
	if _, exists := second["op_id"]; exists {
		t.Fatalf("recusa criou novo op_id: %v", second)
	}
	if latency > 250*time.Millisecond {
		t.Fatalf("recusa não foi rápida: %s", latency)
	}
	t.Logf("busy_409 agent=esp32-01 active_op=%s latency=%s at=%s", firstOpID, latency, time.Now().Format(time.RFC3339Nano))

	time.Sleep(100 * time.Millisecond)
	if got := env.wakeCounts["esp32-01"].Load(); got != 1 {
		t.Fatalf("Wakes para agente ocupado = %d; esperado 1", got)
	}

	env.release.Do(func() { close(env.resultGate) })
	env.waitCompleted(t, firstOpID, "esp32-01")
	env.waitSessionRemoved(t, observation.sessionID)
}

func (env *testEnvironment) getAgent(t *testing.T, agentID string) api.AgentResponse {
	t.Helper()
	response, err := http.Get(env.server.URL + "/api/agents")
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("GET /api/agents: status %d", response.StatusCode)
	}
	var agents []api.AgentResponse
	if err := json.NewDecoder(response.Body).Decode(&agents); err != nil {
		t.Fatal(err)
	}
	for _, agent := range agents {
		if agent.AgentID == agentID {
			return agent
		}
	}
	t.Fatalf("agente %s ausente em GET /api/agents", agentID)
	return api.AgentResponse{}
}

func (env *testEnvironment) subscribeSSE(t *testing.T) <-chan map[string]any {
	t.Helper()
	response, err := http.Get(env.server.URL + "/api/events")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { response.Body.Close() })
	events := make(chan map[string]any, 32)
	go func() {
		defer close(events)
		scanner := bufio.NewScanner(response.Body)
		for scanner.Scan() {
			line := scanner.Text()
			if !strings.HasPrefix(line, "data: ") {
				continue
			}
			var event map[string]any
			if json.Unmarshal([]byte(strings.TrimPrefix(line, "data: ")), &event) == nil {
				events <- event
			}
		}
	}()
	return events
}

func waitSSEState(t *testing.T, events <-chan map[string]any, agentID, state, opID string) map[string]any {
	t.Helper()
	deadline := time.NewTimer(3 * time.Second)
	defer deadline.Stop()
	for {
		select {
		case event, ok := <-events:
			if !ok {
				t.Fatal("SSE encerrado")
			}
			if event["event"] == "agent_state_changed" && event["agent_id"] == agentID && event["operation_state"] == state && event["op_id"] == opID {
				return event
			}
		case <-deadline.C:
			t.Fatalf("timeout aguardando estado SSE %s para %s", state, agentID)
		}
	}
}

func TestAgentOperationStateViaRESTAndSSE(t *testing.T) {
	env := newTestEnvironment(t, "esp32-01")
	events := env.subscribeSSE(t)

	initial := env.getAgent(t, "esp32-01")
	if initial.OperationState != registry.OperationAvailable || initial.ActiveOpID != "" {
		t.Fatalf("estado inicial inválido: %+v", initial)
	}
	t.Logf("agent_state agent=esp32-01 state=available at=%s", time.Now().Format(time.RFC3339Nano))

	accepted, status, _, err := env.postCommand("esp32-01")
	if err != nil || status != http.StatusAccepted {
		t.Fatalf("POST: status=%d body=%v err=%v", status, accepted, err)
	}
	opID := accepted["op_id"].(string)
	observation := env.waitCommand(t)

	busyEvent := waitSSEState(t, events, "esp32-01", registry.OperationInOperation, opID)
	if busyEvent["active_op_id"] != opID {
		t.Fatalf("evento ocupado sem active_op_id correto: %v", busyEvent)
	}
	busy := env.getAgent(t, "esp32-01")
	if busy.OperationState != registry.OperationInOperation || busy.ActiveOpID != opID {
		t.Fatalf("estado ocupado inválido: %+v", busy)
	}
	if busy.Status != "standby" {
		t.Fatalf("estado de operação alterou conectividade: %+v", busy)
	}
	t.Logf("agent_state agent=esp32-01 state=in_operation op=%s at=%s", opID, time.Now().Format(time.RFC3339Nano))

	env.release.Do(func() { close(env.resultGate) })
	env.waitCompleted(t, opID, "esp32-01")
	availableEvent := waitSSEState(t, events, "esp32-01", registry.OperationAvailable, opID)
	if _, exists := availableEvent["active_op_id"]; exists {
		t.Fatalf("evento disponível manteve active_op_id: %v", availableEvent)
	}
	available := env.getAgent(t, "esp32-01")
	if available.OperationState != registry.OperationAvailable || available.ActiveOpID != "" {
		t.Fatalf("estado disponível inválido: %+v", available)
	}
	env.waitSessionRemoved(t, observation.sessionID)
	t.Logf("agent_state agent=esp32-01 state=available op=%s at=%s", opID, time.Now().Format(time.RFC3339Nano))
}
