package protocol

type Result struct {
	Type    string `json:"type"`
	CommandID string `json:"command_id"`
	Stdout  string `json:"stdout"`
	Stderr  string `json:"stderr"`
}
