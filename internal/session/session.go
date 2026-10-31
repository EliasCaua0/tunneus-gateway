package session

import (
	"context"
	"errors"
	"sync"
	"time"

	"github.com/arcanlab/tunneus/internal/protocol"
	"github.com/gorilla/websocket"
)

// EphemeralSession é uma sessão temporária criada pelo Controller para uma operação.
type EphemeralSession struct {
	ID         string          `json:"id"`
	AgentID    string          `json:"agent_id"`
	Challenge  string          `json:"-"`
	CommandID  string          `json:"command_id"`
	State      string          `json:"state"`
	Conn       *websocket.Conn `json:"-"`
	RemoteAddr string          `json:"remote_addr"`
	CreatedAt  time.Time       `json:"created_at"`

	authCh   chan bool
	resultCh chan *protocol.Result
	mu       sync.Mutex
}

// NewEphemeral cria uma sessão efêmera pendente.
func NewEphemeral(id, agentID, challenge, commandID string) *EphemeralSession {
	return &EphemeralSession{
		ID:        id,
		AgentID:   agentID,
		Challenge: challenge,
		CommandID: commandID,
		State:     "pending",
		authCh:    make(chan bool, 1),
		resultCh:  make(chan *protocol.Result, 1),
		CreatedAt: time.Now(),
	}
}

// SetConn define a conexão WebSocket após o ESP abrir.
func (s *EphemeralSession) SetConn(conn *websocket.Conn, remoteAddr string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Conn = conn
	s.RemoteAddr = remoteAddr
}

// SendCommand envia um comando pelo WS.
func (s *EphemeralSession) SendCommand(cmd protocol.Command) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.Conn == nil {
		return errors.New("sessão sem conexão ativa")
	}
	data, err := protocol.Encode(cmd)
	if err != nil {
		return err
	}
	s.State = "command_sent"
	return s.Conn.WriteMessage(websocket.TextMessage, data)
}

// NotifyAuth notifica que a autenticação foi bem-sucedida.
func (s *EphemeralSession) NotifyAuth(ok bool) {
	select {
	case s.authCh <- ok:
	default:
	}
}

// WaitAuth aguarda notificação de autenticação.
func (s *EphemeralSession) WaitAuth(ctx context.Context) bool {
	select {
	case ok := <-s.authCh:
		return ok
	case <-ctx.Done():
		return false
	}
}

// NotifyResult entrega o resultado da operação.
func (s *EphemeralSession) NotifyResult(result *protocol.Result) {
	select {
	case s.resultCh <- result:
	default:
	}
}

// WaitResult aguarda o resultado.
func (s *EphemeralSession) WaitResult(ctx context.Context) *protocol.Result {
	select {
	case r := <-s.resultCh:
		return r
	case <-ctx.Done():
		return nil
	}
}

// Close fecha a conexão WS.
func (s *EphemeralSession) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.Conn != nil {
		s.Conn.Close()
		s.Conn = nil
	}
}

// IsExpired retorna true se a sessão tem mais de 60 segundos.
func (s *EphemeralSession) IsExpired() bool {
	return time.Since(s.CreatedAt) > 60*time.Second
}

// ============================================================
// EPHEMERAL STORE COM TTL
// ============================================================

type EphemeralManager struct {
	mu       sync.RWMutex
	sessions map[string]*EphemeralSession
}

func NewEphemeralManager() *EphemeralManager {
	m := &EphemeralManager{
		sessions: make(map[string]*EphemeralSession),
	}
	go m.cleanupLoop()
	return m
}

// cleanupLoop remove sessões expiradas a cada 30 segundos.
func (m *EphemeralManager) cleanupLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		m.mu.Lock()
		for id, s := range m.sessions {
			if s.IsExpired() {
				s.Close()
				delete(m.sessions, id)
			}
		}
		m.mu.Unlock()
	}
}

func (m *EphemeralManager) Add(s *EphemeralSession) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.sessions[s.ID] = s
}

func (m *EphemeralManager) Remove(id string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if s, ok := m.sessions[id]; ok {
		s.Close()
		delete(m.sessions, id)
	}
}

func (m *EphemeralManager) Get(id string) (*EphemeralSession, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	s, ok := m.sessions[id]
	return s, ok
}

// GetByAgentID busca sessão pendente por agente (a mais recente).
func (m *EphemeralManager) GetByAgentID(agentID string) (*EphemeralSession, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	var found *EphemeralSession
	for _, s := range m.sessions {
		if s.AgentID == agentID {
			if found == nil || s.CreatedAt.After(found.CreatedAt) {
				found = s
			}
		}
	}
	return found, found != nil
}

// EphemeralStore é o store global de sessões efêmeras.
var EphemeralStore = NewEphemeralManager()

