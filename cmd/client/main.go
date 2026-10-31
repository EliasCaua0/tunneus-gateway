package main

import (
	"log"
	"os/exec"
	"strings"
	"time"

	"github.com/arcanlab/tunneus/internal/protocol"
	"github.com/gorilla/websocket"
)

func main() {

	conn, _, err := websocket.DefaultDialer.Dial("ws://localhost:18080/ws", nil)
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	log.Println("Conectado ao Gateway!")

	hello := protocol.Hello{
		Type:    protocol.TypeHello,
		Agent:   "linux-agent",
		Version: "0.1.0",
	}

	data, err := protocol.Encode(hello)
	if err != nil {
		log.Fatal(err)
	}

	if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
		log.Fatal(err)
	}

	go heartbeat(conn)

	for {

		_, msg, err := conn.ReadMessage()
		if err != nil {
			log.Println(err)
			return
		}

		msgType, err := protocol.MessageType(msg)
		if err != nil {
			log.Println(err)
			continue
		}

		switch msgType {

		case protocol.TypeWelcome:

			var welcome protocol.Welcome

			if err := protocol.Decode(msg, &welcome); err != nil {
				log.Println(err)
				continue
			}

			log.Printf("Sessão criada: %s", welcome.Session)

		case protocol.TypeCommand:

			var command protocol.Command

			if err := protocol.Decode(msg, &command); err != nil {
				log.Println(err)
				continue
			}

			log.Printf("Executando comando: %s", command.Cmd)

			parts := strings.Fields(command.Cmd)

			if len(parts) == 0 {
				log.Println("Comando vazio recebido.")
				continue
			}

			cmd := exec.Command(parts[0], parts[1:]...)

			output, err := cmd.CombinedOutput()

			result := protocol.Result{
				Type: protocol.TypeResult,
				ID:   command.ID,
			}

			if err != nil {
				result.Stderr = string(output)
				if result.Stderr == "" {
					result.Stderr = err.Error()
				}
			} else {
				result.Stdout = string(output)
			}

			data, err := protocol.Encode(result)
			if err != nil {
				log.Println(err)
				continue
			}

			if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
				log.Println(err)
				return
			}

			log.Println("Resultado enviado.")

		default:
			log.Printf("Mensagem desconhecida: %s", msgType)
		}
	}
}

func heartbeat(conn *websocket.Conn) {

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for range ticker.C {

		hb := protocol.Heartbeat{
			Type: protocol.TypeHeartbeat,
		}

		data, err := protocol.Encode(hb)
		if err != nil {
			log.Println(err)
			continue
		}

		if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
			log.Println(err)
			return
		}
	}
}
