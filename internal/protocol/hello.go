package protocol

type Hello struct {
	Type              string `json:"type"`
	AgentID           string `json:"agent_id"`
	Agent             string `json:"agent"`
	Version           string `json:"version"`
	SessionID         string `json:"session_id"`
	ChallengeResponse string `json:"challenge_response"`
}
