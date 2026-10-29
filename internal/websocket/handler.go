package websocket

import (
	"log"
	"net"
	"net/http"
	"time"

	"github.com/arcanlab/tunneus/internal/protocol"
	"github.com/arcanlab/tunneus/internal/registry"
	"github.com/arcanlab/tunneus/internal/session"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

// Handler gerencia conexões WebSocket do subagente ESP32.
// O ESP só pode conectar se foi previamente convocado via UDP Wake.
func Handler(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("[WS] Upgrade falhou:", err)
		return
	}
	defer conn.Close()

	// Extrai apenas o IP do RemoteAddr (remove a porta TCP)
	remoteAddr := conn.RemoteAddr().String()
	host, _, err := net.SplitHostPort(remoteAddr)
	if err != nil {
		host = remoteAddr // fallback
	}

	log.Printf("[WS] Nova conexão de %s", host)

	// Timeout de autenticação: se não receber Hello em 8s, fecha.
	// Alinhado com PROTOCOLO.md v4.0 e Controller timeout de 8s.
	conn.SetReadDeadline(time.Now().Add(10 * time.Second))

	_, message, err := conn.ReadMessage()
	if err != nil {
		log.Println("[WS] Timeout aguardando Hello:", err)
		return
	}

	msgType, err := protocol.MessageType(message)
	if err != nil || msgType != protocol.TypeHello {
		log.Println("[WS] Primeira mensagem não é Hello:", err)
		return
	}

	var hello protocol.Hello
	if err := protocol.Decode(message, &hello); err != nil {
		log.Println("[WS] Hello inválido:", err)
		return
	}

	log.Printf("[WS] Hello recebido: agent_id=%s session_id=%s", hello.AgentID, hello.SessionID)

	// Busca sessão efêmera pendente para este agente
	sess, ok := session.EphemeralStore.Get(hello.SessionID)
	if !ok {
		log.Printf("[WS] Sessão %s não encontrada (ESP conectou sem convocação?)", hello.SessionID)
		return
	}

	// Valida challenge_response
	entry, ok := registry.DefaultRegistry.Get(hello.AgentID)
	if !ok {
		log.Printf("[WS] Agente %s não registrado", hello.AgentID)
		return
	}

	if !registry.ValidateChallengeResponse(sess.Challenge, hello.ChallengeResponse, entry.Secret) {
		log.Printf("[WS] Challenge response inválido para %s", hello.AgentID)
		return
	}

	log.Printf("[WS] Autenticação OK para %s", hello.AgentID)

	// Associa conexão à sessão
	sess.SetConn(conn, host)
	sess.State = "auth"

	// Envia Welcome
	welcome := protocol.Welcome{
		Type:          protocol.TypeWelcome,
		Session:       sess.ID,
		Authenticated: true,
	}
	data, _ := protocol.Encode(welcome)
	conn.WriteMessage(websocket.TextMessage, data)

	// Notifica Controller que autenticação OK
	sess.NotifyAuth(true)

	// Remove deadline de leitura para aguardar Result/Bye
	conn.SetReadDeadline(time.Time{})

	// Aguarda Result ou Bye — timeout de sessão máx. 30s
	sessionTimeout := time.NewTimer(30 * time.Second)
	defer sessionTimeout.Stop()

	done := make(chan bool, 1)

	go func() {
		for {
			_, msg, err := conn.ReadMessage()
			if err != nil {
				log.Printf("[WS] Conexão fechada por %s: %v", hello.AgentID, err)
				done <- true
				return
			}

			msgType, err := protocol.MessageType(msg)
			if err != nil {
				continue
			}

			switch msgType {
			case protocol.TypeResult:
				var result protocol.Result
				if err := protocol.Decode(msg, &result); err != nil {
					continue
				}
				log.Printf("[WS] Result recebido: cmd=%s stdout=%s", result.CommandID, result.Stdout)
				sess.NotifyResult(&result)
				sess.State = "completed"

			case protocol.TypeBye:
				var bye protocol.Bye
				if err := protocol.Decode(msg, &bye); err != nil {
					continue
				}
				log.Printf("[WS] Bye recebido de %s: reason=%s", hello.AgentID, bye.Reason)
				// Remove sessão imediatamente ao receber Bye
				session.EphemeralStore.Remove(sess.ID)
				done <- true
				return

			default:
				log.Printf("[WS] Tipo desconhecido: %s", msgType)
			}
		}
	}()

	select {
	case <-done:
		log.Printf("[WS] Sessão %s encerrada normalmente", sess.ID)
	case <-sessionTimeout.C:
		log.Printf("[WS] Sessão %s expirada (timeout 30s)", sess.ID)
	}

	// Cleanup
	sess.Close()
	// Garante remoção se não foi removida ainda
	session.EphemeralStore.Remove(sess.ID)
}

