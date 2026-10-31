package protocol

import (
	"encoding/json"
	"fmt"
)

// Command é a mensagem Gateway → ESP que pede a execução de uma capability.
//
// Args é opcional (protocolo v4.1). Comandos sem parâmetros (LED_ON, START,
// LER_SENSORES...) omitem o campo, mantendo o formato v4.0 byte a byte.
// O Gateway não interpreta o conteúdo de Args: quem define e valida o contrato
// de cada capability é o firmware do agente.
type Command struct {
	Type      string         `json:"type"`
	CommandID string         `json:"command_id"`
	Cmd       string         `json:"cmd"`
	Args      map[string]any `json:"args,omitempty"`
}

// Limites de Args. Existem porque o ESP32 interpreta a mensagem em um
// documento JSON de tamanho fixo; um Args maior que isso seria descartado
// silenciosamente pelo firmware.
const (
	MaxArgsKeys     = 8
	MaxArgsKeyLen   = 24
	MaxArgsStrLen   = 32
	MaxArgsJSONSize = 256
)

// ValidateArgs verifica a forma de Args (não o significado): poucas chaves,
// apenas valores escalares (string, número ou bool), tamanho total limitado.
// Args nulo ou vazio é válido.
func ValidateArgs(args map[string]any) error {
	if len(args) == 0 {
		return nil
	}
	if len(args) > MaxArgsKeys {
		return fmt.Errorf("args: no máximo %d campos", MaxArgsKeys)
	}
	for k, v := range args {
		if k == "" || len(k) > MaxArgsKeyLen {
			return fmt.Errorf("args: nome de campo inválido (1 a %d caracteres)", MaxArgsKeyLen)
		}
		switch val := v.(type) {
		case string:
			if len(val) > MaxArgsStrLen {
				return fmt.Errorf("args.%s: texto maior que %d caracteres", k, MaxArgsStrLen)
			}
		case float64, bool:
			// números JSON chegam como float64 e bool é escalar: aceitos
		default:
			return fmt.Errorf("args.%s: apenas texto, número ou booleano são aceitos", k)
		}
	}
	data, err := json.Marshal(args)
	if err != nil {
		return fmt.Errorf("args inválido: %v", err)
	}
	if len(data) > MaxArgsJSONSize {
		return fmt.Errorf("args: tamanho máximo de %d bytes excedido", MaxArgsJSONSize)
	}
	return nil
}
