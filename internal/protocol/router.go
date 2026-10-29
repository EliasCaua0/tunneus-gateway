package protocol

func MessageType(data []byte) (string, error) {
	var msg Message
	err := Decode(data, &msg)
	if err != nil {
		return "", err
	}
	return msg.Type, nil
}
