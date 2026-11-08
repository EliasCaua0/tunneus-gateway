package registry

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

const (
	OperationAvailable   = "available"
	OperationInOperation = "in_operation"
)

// AgentBusyError indica que outra operação já reservou o agente.
type AgentBusyError struct {
	AgentID    string
	ActiveOpID string
}

func (e *AgentBusyError) Error() string {
	return fmt.Sprintf("agente ocupado: %s já possui a operação ativa %s", e.AgentID, e.ActiveOpID)
}

// Entry é um registro persistente de um subagente conhecido.
type Entry struct {
	AgentID      string    `json:"agent_id"`
	Secret       string    `json:"secret"` // base64, 32 bytes
	LastIP       string    `json:"last_ip"`
	MAC          string    `json:"mac"`
	Capabilities []string  `json:"capabilities"`
	LastSeen     time.Time `json:"last_seen"`
	Status       string    `json:"status"` // standby | connecting | executing | unreachable
	FirmwareVer  string    `json:"firmware_ver"`
	Name         string    `json:"name"`        // nome de exibição no dashboard
	Type         string    `json:"type"`        // tipo: led, servo, sensor, etc.
	Icon         string    `json:"icon"`        // emoji ou identificador visual
	Description  string    `json:"description"` // descrição curta
}

// Registry mantém os subagentes conhecidos em memória + persistência opcional.
type Registry struct {
	mu               sync.RWMutex
	saveMu           sync.Mutex
	entries          map[string]*Entry // key: agent_id
	activeOperations map[string]string // key: agent_id, value: op_id
	path             string
}

// NewRegistry cria um registry vazio (ou carrega de arquivo se existir).
func NewRegistry(path string) *Registry {
	r := &Registry{
		entries:          make(map[string]*Entry),
		activeOperations: make(map[string]string),
		path:             path,
	}
	if path != "" {
		_ = r.Load() // ignora erro inicial
	}
	return r
}

// Load carrega entries de arquivo JSON.
func (r *Registry) Load() error {
	data, err := os.ReadFile(r.path)
	if err != nil {
		return err
	}
	var list []*Entry
	if err := json.Unmarshal(data, &list); err != nil {
		return err
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, e := range list {
		r.entries[e.AgentID] = cloneEntry(e)
	}
	return nil
}

// Save persiste entries em arquivo JSON.
func (r *Registry) Save() error {
	r.saveMu.Lock()
	defer r.saveMu.Unlock()

	r.mu.RLock()
	if r.path == "" {
		r.mu.RUnlock()
		return nil
	}
	path := r.path
	list := make([]*Entry, 0, len(r.entries))
	for _, e := range r.entries {
		list = append(list, cloneEntry(e))
	}
	r.mu.RUnlock()

	data, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		return err
	}
	tmpPath := path + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmpPath, path)
}

// Get busca um entry pelo agent_id.
func (r *Registry) Get(agentID string) (*Entry, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	e, ok := r.entries[agentID]
	return cloneEntry(e), ok
}

// Set cria ou atualiza um entry.
func (r *Registry) Set(e *Entry) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.entries[e.AgentID] = cloneEntry(e)
}

// UpdateStatus atualiza apenas o status e last_seen.
func (r *Registry) UpdateStatus(agentID, status string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if e, ok := r.entries[agentID]; ok {
		e.Status = status
		e.LastSeen = time.Now()
	}
}

// UpdateIP atualiza o IP conhecido.
func (r *Registry) UpdateIP(agentID, ip string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if e, ok := r.entries[agentID]; ok {
		e.LastIP = ip
	}
}

// List retorna todos os entries.
func (r *Registry) List() []*Entry {
	r.mu.RLock()
	defer r.mu.RUnlock()
	list := make([]*Entry, 0, len(r.entries))
	for _, e := range r.entries {
		list = append(list, cloneEntry(e))
	}
	return list
}

// TryReserveAgent reserva o agente sem bloquear se outra operação já o reservou.
func (r *Registry) TryReserveAgent(agentID, opID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if activeOpID, ok := r.activeOperations[agentID]; ok {
		return &AgentBusyError{AgentID: agentID, ActiveOpID: activeOpID}
	}
	r.activeOperations[agentID] = opID
	return nil
}

// ReleaseAgent libera somente a reserva pertencente à operação informada.
func (r *Registry) ReleaseAgent(agentID, opID string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if activeOpID, ok := r.activeOperations[agentID]; ok && activeOpID == opID {
		delete(r.activeOperations, agentID)
	}
}

// ActiveOperation retorna a operação que mantém o agente reservado.
func (r *Registry) ActiveOperation(agentID string) (string, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	opID, ok := r.activeOperations[agentID]
	return opID, ok
}

func cloneEntry(e *Entry) *Entry {
	if e == nil {
		return nil
	}
	clone := *e
	clone.Capabilities = append([]string(nil), e.Capabilities...)
	return &clone
}

// GenerateSecret cria uma secret de 32 bytes em base64.
func GenerateSecret() string {
	b := make([]byte, 32)
	// Em produção, use crypto/rand. Aqui deixamos simples para MVP.
	for i := range b {
		b[i] = byte(i*7 + 13) // pseudo-random fixo para demo; substituir por crypto/rand
	}
	return base64.StdEncoding.EncodeToString(b)
}

// ComputeMAC calcula HMAC-SHA256(challenge + agent_id, secret).
func ComputeMAC(challenge, agentID string, secretB64 string) string {
	secret, _ := base64.StdEncoding.DecodeString(secretB64)
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(challenge + agentID))
	return hex.EncodeToString(mac.Sum(nil))
}

// ValidateMAC verifica se o MAC fornecido corresponde ao esperado.
func ValidateMAC(challenge, agentID, providedMAC, secretB64 string) bool {
	expected := ComputeMAC(challenge, agentID, secretB64)
	return hmac.Equal([]byte(providedMAC), []byte(expected))
}

// ValidateChallengeResponse valida challenge_response = HMAC(challenge, secret).
func ValidateChallengeResponse(challenge, response, secretB64 string) bool {
	secret, _ := base64.StdEncoding.DecodeString(secretB64)
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(challenge))
	expected := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(response), []byte(expected))
}

// DefaultRegistry é o registry global do gateway.
var DefaultRegistry *Registry

// InitRegistry inicializa o registry com os agentes da feira.
func InitRegistry() {
	DefaultRegistry = NewRegistry("registry.json")

	// Agente 01 — Semáforo de LEDs (firmware v1.0, 3 LEDs com args {cor})
	DefaultRegistry.Set(&Entry{
		AgentID:      "esp32-01",
		Secret:       "dGVzdC1zZWNyZXQtZm9yLWVzcDMyLTA0LWFyY2FuLmxhYg==",
		Capabilities: []string{"LIGAR_LED", "DESLIGAR_LED", "ESTADO_LEDS"},
		Status:       "standby",
		Name:         "Agente 01 — Semáforo de LEDs",
		Type:         "led",
		LastIP:       "192.168.18.100",
		FirmwareVer:  "1.0",
		Description:  "Controle de 3 LEDs (vermelho GPIO13, amarelo GPIO26, verde GPIO25) com args {cor}",
	})

	// Agente 02 — Polias Industriais
	DefaultRegistry.Set(&Entry{
		AgentID:      "esp32-02",
		Secret:       "dGVzdC1zZWNyZXQtZm9yLWVzcDMyLTAyLWFyY2FuLmxhYg==",
		Capabilities: []string{"LIGAR", "ELEVAÇÃO A", "ELEVAÇÃO B", "DESLIGAR"},
		Status:       "standby",
		Name:         "Agente 02 — Polias Industriais",
		Type:         "industrial",
		Icon:         "⚙️",
		LastIP:       "192.168.18.100",
		Description:  "Controle de elevação por polias (Ponte H)",
	})

	// Agente 03 — Bancada de Sensores + Motor de Passo
	DefaultRegistry.Set(&Entry{
		AgentID:      "esp32-03",
		Secret:       "dGVzdC1zZWNyZXQtZm9yLWVzcDMyLTAzLWFyY2FuLmxhYg==",
		Capabilities: []string{"LER_SENSORES", "TEMPERATURA", "PRESSAO", "ALTITUDE", "CORRENTE", "DISTANCIA", "START", "PARE", "MOVER"},
		Status:       "standby",
		Name:         "Agente 03 — Bancada Sensores + Motor de Passo",
		Type:         "sensor_motor",
		Icon:         "📊",
		LastIP:       "192.168.18.13",
		FirmwareVer:  "4.4",
		Description:  "Bancada de sensores (BMP180, ACS712, HC-SR04) com motor de passo controlado",
	})

	_ = DefaultRegistry.Save()
	fmt.Println("[Registry] Inicializado com 3 subagentes (esp32-01, esp32-02, esp32-03)")
}
