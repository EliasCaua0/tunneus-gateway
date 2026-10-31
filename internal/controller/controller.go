package controller

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/arcanlab/tunneus/internal/protocol"
	"github.com/arcanlab/tunneus/internal/registry"
	"github.com/arcanlab/tunneus/internal/session"
	"github.com/arcanlab/tunneus/internal/wake"
	"github.com/google/uuid"
)

// Operation representa uma única intenção lógica do usuário.
type Operation struct {
	ID        string         `json:"id"`
	AgentID   string         `json:"agent_id"`
	Command   string         `json:"command"`
	Args      map[string]any `json:"args,omitempty"`
	Status    string         `json:"status"` // pending | wake_sent | connecting | authenticated | command_sent | executing | completed | failed
	Result    string         `json:"result"`
	Error     string         `json:"error"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
	Retries   int            `json:"retries"`
	SessionID string         `json:"session_id"`
	Challenge string         `json:"challenge"`
}

// nonIdempotentCmds lista capabilities cujo efeito físico NÃO pode ser repetido.
// Se o comando já foi entregue ao agente (command_sent) e o resultado não
// chegou, o Gateway não reenvia: o agente pode ter executado e só a resposta
// se perdeu, e um reenvio dobraria o efeito (ex.: MOVER giraria duas vezes).
// Falhas ANTES da entrega (wake, autenticação) continuam sendo repetidas,
// pois nesse ponto o comando nunca chegou ao agente.
var nonIdempotentCmds = map[string]bool{
	"MOVER": true,
}

// Controller orquestra todo o fluxo de convocação → execução.
type Controller struct {
	mu         sync.RWMutex
	operations map[string]*Operation
	sseClients map[chan string]bool
	sseMu      sync.RWMutex
}

// NewController cria o orquestrador.
func NewController() *Controller {
	c := &Controller{
		operations: make(map[string]*Operation),
		sseClients: make(map[chan string]bool),
	}
	// Inicia goroutine de limpeza periódica
	go c.cleanupLoop()
	return c
}

// cleanupLoop remove operações antigas a cada 5 minutos (evita memory leak)
func (c *Controller) cleanupLoop() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()
	for range ticker.C {
		c.mu.Lock()
		before := len(c.operations)
		cutoff := time.Now().Add(-30 * time.Minute)
		for id, op := range c.operations {
			if op.CreatedAt.Before(cutoff) {
				delete(c.operations, id)
			}
		}
		after := len(c.operations)
		c.mu.Unlock()
		if before != after {
			log.Printf("[Controller] Limpeza: %d operações removidas (%d restantes)", before-after, after)
		}
	}
}

// Submit recebe uma intenção do usuário, cria a operação e a executa em background.
func (c *Controller) Submit(agentID, command string, args map[string]any) (*Operation, error) {
	entry, ok := registry.DefaultRegistry.Get(agentID)
	if !ok {
		return nil, fmt.Errorf("agente não registrado: %s", agentID)
	}
	if !contains(entry.Capabilities, command) {
		return nil, fmt.Errorf("comando não suportado pelo agente: %s", command)
	}

	op := &Operation{
		ID:        uuid.NewString(),
		AgentID:   agentID,
		Command:   command,
		Args:      args,
		Status:    "pending",
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	c.mu.Lock()
	c.operations[op.ID] = op
	c.mu.Unlock()

	created := map[string]any{"command": command}
	if len(args) > 0 {
		created["args"] = args
	}
	c.emit("command_created", op, created)

	go c.execute(op)

	return op, nil
}

// execute é o fluxo completo de uma operação (com retry).
func (c *Controller) execute(op *Operation) {
	backoffs := []time.Duration{0, 1 * time.Second, 2 * time.Second, 4 *
		time.Second, 8 * time.Second}
	maxRetries := len(backoffs)

	for attempt := 0; attempt < maxRetries; attempt++ {
		sessionID := uuid.NewString()
		challenge := generateChallenge()
		op.SessionID = sessionID
		op.Challenge = challenge
		op.Retries = attempt

		c.updateStatus(op.ID, "wake_sent")
		c.emit("wake_sent", op, map[string]any{"attempt": attempt + 1})

		if attempt > 0 {
			time.Sleep(backoffs[attempt])
		}

		err := wake.DefaultSender.SendToAgent(op.AgentID, sessionID, challenge)
		if err != nil {
			log.Printf("[Controller] Wake falhou (tentativa %d): %v", attempt+1, err)
			c.emit("wake_failed", op, map[string]any{"attempt": attempt + 1, "error": err.Error()})
			continue
		}

		sess := session.NewEphemeral(sessionID, op.AgentID, challenge, op.ID)
		session.EphemeralStore.Add(sess)

		// Timeout de 8s para autenticação
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		authOK := sess.WaitAuth(ctx)
		cancel()

		if !authOK {
			log.Printf("[Controller] Auth timeout (tentativa %d)", attempt+1)
			c.emit("auth_timeout", op, map[string]any{"attempt": attempt + 1})
			session.EphemeralStore.Remove(sess.ID)
			continue
		}

		c.updateStatus(op.ID, "authenticated")
		c.emit("auth_ok", op, nil)

		cmd := protocol.Command{
			Type:      protocol.TypeCommand,
			CommandID: op.ID,
			Cmd:       op.Command,
			Args:      op.Args,
		}
		if err := sess.SendCommand(cmd); err != nil {
			log.Printf("[Controller] Erro ao enviar comando: %v", err)
			c.updateStatus(op.ID, "failed")
			c.emit("command_send_failed", op, map[string]any{"error": err.Error()})
			session.EphemeralStore.Remove(sess.ID)
			return
		}

		c.updateStatus(op.ID, "command_sent")
		c.emit("command_sent", op, nil)

		// Aguarda resultado — timeout 10s
		ctx2, cancel2 := context.WithTimeout(context.Background(), 15*time.Second)
		result := sess.WaitResult(ctx2)
		cancel2()

		if result == nil {
			log.Printf("[Controller] Result timeout (tentativa %d)", attempt+1)
			c.emit("result_timeout", op, map[string]any{"attempt": attempt + 1})
			session.EphemeralStore.Remove(sess.ID)
			if nonIdempotentCmds[op.Command] {
				// O comando já foi entregue: não reenviar (ver nonIdempotentCmds).
				op.Error = "comando entregue, mas o resultado não chegou; não reenviado por não ser idempotente"
				c.updateStatus(op.ID, "failed")
				c.emit("operation_failed", op, map[string]any{"reason": "result_unconfirmed_no_retry"})
				return
			}
			continue
		}

		// Sucesso!
		op.Result = result.Stdout
		if result.Stderr != "" {
			op.Error = result.Stderr
		}
		c.updateStatus(op.ID, "completed")
		c.emit("result_received", op, map[string]any{"stdout": result.Stdout, "stderr": result.Stderr})

		// Atualiza Registry
		registry.DefaultRegistry.UpdateStatus(op.AgentID, "standby")
		registry.DefaultRegistry.UpdateIP(op.AgentID, sess.RemoteAddr)
		_ = registry.DefaultRegistry.Save()

		// Limpa sessão
		session.EphemeralStore.Remove(sess.ID)
		return
	}

	// Todas as tentativas falharam
	c.updateStatus(op.ID, "failed")
	c.emit("operation_failed", op, map[string]any{"reason": "max_retries_exhausted"})
	registry.DefaultRegistry.UpdateStatus(op.AgentID, "unreachable")
}

// GetOperation retorna o estado de uma operação.
func (c *Controller) GetOperation(id string) (*Operation, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	op, ok := c.operations[id]
	return op, ok
}

// ListOperations retorna todas as operações (mais recentes primeiro).
func (c *Controller) ListOperations() []*Operation {
	c.mu.RLock()
	defer c.mu.RUnlock()
	list := make([]*Operation, 0, len(c.operations))
	for _, op := range c.operations {
		list = append(list, op)
	}
	// ordenar por created_at desc
	for i := 0; i < len(list)-1; i++ {
		for j := i + 1; j < len(list); j++ {
			if list[i].CreatedAt.Before(list[j].CreatedAt) {
				list[i], list[j] = list[j], list[i]
			}
		}
	}
	return list
}

// updateStatus atualiza o status de uma operação.
func (c *Controller) updateStatus(opID, status string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if op, ok := c.operations[opID]; ok {
		op.Status = status
		op.UpdatedAt = time.Now()
	}
}

// SSE — Server-Sent Events

// RegisterSSEClient registra um canal para receber eventos.
func (c *Controller) RegisterSSEClient() chan string {
	ch := make(chan string, 32)
	c.sseMu.Lock()
	c.sseClients[ch] = true
	c.sseMu.Unlock()
	return ch
}

// UnregisterSSEClient remove um canal.
func (c *Controller) UnregisterSSEClient(ch chan string) {
	c.sseMu.Lock()
	delete(c.sseClients, ch)
	close(ch)
	c.sseMu.Unlock()
}

// emit monta um evento SSE de uma operação e o envia a todos os clientes.
// O JSON é gerado por json.Marshal: textos vindos do agente (stdout/stderr) ou
// de erros nunca quebram o formato, ao contrário da montagem por Sprintf.
func (c *Controller) emit(event string, op *Operation, extra map[string]any) {
	payload := map[string]any{
		"event":    event,
		"op_id":    op.ID,
		"agent_id": op.AgentID,
	}
	for k, v := range extra {
		payload[k] = v
	}
	data, err := json.Marshal(payload)
	if err != nil {
		log.Printf("[Controller] Falha ao serializar evento SSE %s: %v", event, err)
		return
	}
	c.broadcastSSE(string(data))
}

// broadcastSSE envia um evento JSON para todos os clientes conectados.
func (c *Controller) broadcastSSE(event string) {
	c.sseMu.RLock()
	defer c.sseMu.RUnlock()
	for ch := range c.sseClients {
		select {
		case ch <- event:
		default:
			// canal cheio, ignora
		}
	}
}

// DefaultController é o controller global.
var DefaultController *Controller

// InitController inicializa o controller global.
func InitController() {
	DefaultController = NewController()
	log.Println("[Controller] Orquestrador inicializado")
}

// helpers

func generateChallenge() string {
	b := make([]byte, 32)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
