package registry

import (
	"errors"
	"fmt"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
)

func TestTryReserveAgentAllowsOnlyOneOperation(t *testing.T) {
	r := NewRegistry("")
	const contenders = 32

	var successes atomic.Int32
	start := make(chan struct{})
	var wg sync.WaitGroup
	for i := 0; i < contenders; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			err := r.TryReserveAgent("esp32-01", fmt.Sprintf("op-%d", i))
			if err == nil {
				successes.Add(1)
				return
			}
			var busyErr *AgentBusyError
			if !errors.As(err, &busyErr) {
				t.Errorf("erro inesperado: %v", err)
			}
		}(i)
	}
	close(start)
	wg.Wait()

	if got := successes.Load(); got != 1 {
		t.Fatalf("reservas aceitas = %d; esperado 1", got)
	}
	activeOpID, ok := r.ActiveOperation("esp32-01")
	if !ok {
		t.Fatal("agente deveria permanecer reservado")
	}

	r.ReleaseAgent("esp32-01", "op-inexistente")
	if got, _ := r.ActiveOperation("esp32-01"); got != activeOpID {
		t.Fatal("operação diferente conseguiu liberar a reserva")
	}
	r.ReleaseAgent("esp32-01", activeOpID)
	if err := r.TryReserveAgent("esp32-01", "op-final"); err != nil {
		t.Fatalf("agente não foi liberado pelo proprietário: %v", err)
	}
}

func TestTryReserveAgentDoesNotBlockOtherAgents(t *testing.T) {
	r := NewRegistry("")
	const agents = 32

	start := make(chan struct{})
	var wg sync.WaitGroup
	for i := 0; i < agents; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			agentID := fmt.Sprintf("esp32-%02d", i)
			if err := r.TryReserveAgent(agentID, "op-"+agentID); err != nil {
				t.Errorf("reserva de %s recusada: %v", agentID, err)
			}
		}(i)
	}
	close(start)
	wg.Wait()

	for i := 0; i < agents; i++ {
		agentID := fmt.Sprintf("esp32-%02d", i)
		if _, ok := r.ActiveOperation(agentID); !ok {
			t.Errorf("%s não está reservado", agentID)
		}
	}
}

func TestActiveOperationIsNotPersisted(t *testing.T) {
	path := filepath.Join(t.TempDir(), "registry.json")
	r := NewRegistry(path)
	if err := r.TryReserveAgent("esp32-01", "op-ativa"); err != nil {
		t.Fatal(err)
	}
	if err := r.Save(); err != nil {
		t.Fatal(err)
	}

	reloaded := NewRegistry(path)
	if opID, ok := reloaded.ActiveOperation("esp32-01"); ok {
		t.Fatalf("operação transitória foi persistida: %s", opID)
	}
}
