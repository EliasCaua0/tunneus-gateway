package protocol

type Bye struct {
	Type      string `json:"type"`
	SessionID string `json:"session_id"`
	Reason    string `json:"reason"`
}
