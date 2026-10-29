package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/arcanlab/tunneus/internal/controller"
	"github.com/arcanlab/tunneus/internal/protocol"
	"github.com/arcanlab/tunneus/internal/registry"
)

// AgentResponse é a visão pública de um agente para o dashboard.
type AgentResponse struct {
	AgentID      string    `json:"agent_id"`
	Name         string    `json:"name"`
	Type         string    `json:"type"`
	Icon         string    `json:"icon"`
	Description  string    `json:"description"`
	Capabilities []string  `json:"capabilities"`
	Status       string    `json:"status"`
	LastSeen     time.Time `json:"last_seen"`
}

// ListAgents retorna todos os agentes registrados com estado atual.
func ListAgents(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	entries := registry.DefaultRegistry.List()
	var result []AgentResponse
	for _, e := range entries {
		result = append(result, AgentResponse{
			AgentID:      e.AgentID,
			Name:         e.Name,
			Type:         e.Type,
			Icon:         e.Icon,
			Description:  e.Description,
			Capabilities: e.Capabilities,
			Status:       e.Status,
			LastSeen:     e.LastSeen,
		})
	}

	json.NewEncoder(w).Encode(result)
}

// SendAgentCommand recebe um comando do usuário e retorna HTTP 202 Accepted imediatamente.
// A execução ocorre em background; o cliente acompanha via SSE.
func SendAgentCommand(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "Use POST"})
		return
	}

	// Extrai agent_id de /api/agents/{agent_id}/command
	parts := strings.Split(r.URL.Path, "/")
	if len(parts) < 5 {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "URL inválida"})
		return
	}
	agentID := parts[3]

	var req struct {
		Cmd  string         `json:"cmd"`
		Args map[string]any `json:"args"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "JSON inválido"})
		return
	}

	if req.Cmd == "" {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "cmd é obrigatório"})
		return
	}

	// Valida apenas a forma de args (o significado é contrato do firmware)
	if err := protocol.ValidateArgs(req.Args); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]any{"success": false, "message": err.Error()})
		return
	}

	// Submete ao Controller (assíncrono)
	op, err := controller.DefaultController.Submit(agentID, req.Cmd, req.Args)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]any{"success": false, "message": err.Error()})
		return
	}

	// HTTP 202 Accepted — intenção recebida, processamento em background
	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]any{
		"success":    true,
		"message":    "Comando aceito e em processamento",
		"op_id":      op.ID,
		"agent_id":   agentID,
		"command":    req.Cmd,
		"args":       op.Args,
		"status":     op.Status,
		"created_at": op.CreatedAt,
	})
}

// GetOperation retorna o estado de uma operação.
func GetOperation(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	parts := strings.Split(r.URL.Path, "/")
	if len(parts) < 4 {
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	opID := parts[3]

	op, ok := controller.DefaultController.GetOperation(opID)
	if !ok {
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "Operação não encontrada"})
		return
	}

	json.NewEncoder(w).Encode(map[string]any{
		"success":   true,
		"operation": op,
	})
}

// SSEHandler serve Server-Sent Events para o dashboard.
func SSEHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming não suportado", http.StatusInternalServerError)
		return
	}

	client := controller.DefaultController.RegisterSSEClient()
	defer controller.DefaultController.UnregisterSSEClient(client)

	// Envia evento inicial de conexão
	fmt.Fprintf(w, "data: %s\n\n", `{"event":"sse_connected"}`)
	flusher.Flush()

	for {
		select {
		case event, ok := <-client:
			if !ok {
				return
			}
			fmt.Fprintf(w, "data: %s\n\n", event)
			flusher.Flush()
		case <-r.Context().Done():
			return
		}
	}
}

// AgentRouter roteia sub-rotas de /api/agents/{agent_id}/...
func AgentRouter(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	if strings.HasSuffix(path, "/command") && r.Method == http.MethodPost {
		SendAgentCommand(w, r)
		return
	}
	w.WriteHeader(http.StatusNotFound)
	json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "Rota não encontrada"})
}
