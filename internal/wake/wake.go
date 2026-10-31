package wake

import (
	"encoding/json"
	"fmt"
	"log"
	"net"

	"github.com/arcanlab/tunneus/internal/protocol"
	"github.com/arcanlab/tunneus/internal/registry"
)

const WakePort = 18081

// Sender encapsula o socket UDP do Gateway para envio de Wake Packets.
type Sender struct {
	conn *net.UDPConn
}

// NewSender cria o socket UDP de envio (bind em :0, qualquer porta).
func NewSender() (*Sender, error) {
	addr, err := net.ResolveUDPAddr("udp", ":0")
	if err != nil {
		return nil, err
	}
	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		return nil, err
	}
	return &Sender{conn: conn}, nil
}

// Send envia um Wake Packet unicast para o IP do subagente.
func (s *Sender) Send(ip string, packet protocol.WakePacket) error {
	data, err := json.Marshal(packet)
	if err != nil {
		return err
	}
	addr, err := net.ResolveUDPAddr("udp", fmt.Sprintf("%s:%d", ip, WakePort))
	if err != nil {
		return err
	}
	_, err = s.conn.WriteToUDP(data, addr)
	if err != nil {
		return err
	}
	log.Printf("[Wake] Pacote enviado para %s (session=%s)", ip, packet.SessionID)
	return nil
}

// SendToAgent gera e envia um Wake Packet para um agente conhecido.
func (s *Sender) SendToAgent(agentID, sessionID, challenge string) error {
	entry, ok := registry.DefaultRegistry.Get(agentID)
	if !ok {
		return fmt.Errorf("agente não registrado: %s", agentID)
	}
	if entry.LastIP == "" {
		return fmt.Errorf("IP desconhecido para agente: %s", agentID)
	}
	mac := registry.ComputeMAC(challenge, agentID, entry.Secret)
	packet := protocol.WakePacket{
		Type:      protocol.TypeWake,
		AgentID:   agentID,
		SessionID: sessionID,
		Challenge: challenge,
		AuthMAC:   mac,
	}
	return s.Send(entry.LastIP, packet)
}

// Close fecha o socket UDP.
func (s *Sender) Close() error {
	if s.conn != nil {
		return s.conn.Close()
	}
	return nil
}

// DefaultSender é o sender global.
var DefaultSender *Sender

// InitSender inicializa o sender UDP.
func InitSender() {
	var err error
	DefaultSender, err = NewSender()
	if err != nil {
		log.Fatal("[Wake] Falha ao criar socket UDP:", err)
	}
	log.Println("[Wake] UDP sender pronto na porta dinâmica")
}
