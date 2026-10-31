package protocol

// WakePacket é o payload JSON enviado via UDP unicast para convocar o subagente.
type WakePacket struct {
	Type      string `json:"type"`
	AgentID   string `json:"agent_id"`
	SessionID string `json:"session_id"`
	Challenge string `json:"challenge"`
	AuthMAC   string `json:"auth_mac"`
}
