package protocol

import "encoding/json"

func Encode(v any) ([]byte, error) {
	return json.Marshal(v)
}

func Decode(data []byte, v any) error {
	return json.Unmarshal(data, v)
}
