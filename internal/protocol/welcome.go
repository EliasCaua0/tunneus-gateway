package protocol

type Welcome struct {
	Type          string `json:"type"`
	Session       string `json:"session"`
	Authenticated bool   `json:"authenticated"`
}
