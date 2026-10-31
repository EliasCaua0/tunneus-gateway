package server

import (
	"log"
	"net/http"

	"github.com/arcanlab/tunneus/internal/api"
	"github.com/arcanlab/tunneus/internal/controller"
	"github.com/arcanlab/tunneus/internal/handlers"
	"github.com/arcanlab/tunneus/internal/registry"
	"github.com/arcanlab/tunneus/internal/wake"
	ws "github.com/arcanlab/tunneus/internal/websocket"
)

type Server struct {
	Port string
}

func New(port string) *Server {
	return &Server{Port: port}
}

func (s *Server) Start() error {
	// Inicializa subsistemas
	registry.InitRegistry()
	wake.InitSender()
	controller.InitController()

	mux := http.NewServeMux()

	// Rotas HTTP base
	mux.HandleFunc("/", handlers.Root)
	mux.HandleFunc("/health", handlers.Health)

	// API v4.0 (assíncrona)
	mux.HandleFunc("/api/agents", api.ListAgents)
	mux.HandleFunc("/api/agents/", api.AgentRouter)
	mux.HandleFunc("/api/operations/", api.GetOperation)
	mux.HandleFunc("/api/events", api.SSEHandler)

	// Dashboard Web
	fs := http.FileServer(http.Dir("web/dashboard"))
	mux.Handle("/dashboard/", http.StripPrefix("/dashboard/", fs))
	mux.HandleFunc("/dashboard", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/dashboard/", http.StatusMovedPermanently)
	})

	// WebSocket — apenas para sessões episódicas convocadas
	mux.HandleFunc("/ws", ws.Handler)

	log.Println("===================================")
	log.Println("      Tunneus Gateway v4.0")
	log.Println("      Subagent Controller")
	log.Println("===================================")
	log.Printf("Gateway escutando na porta %s", s.Port)
	log.Println("Dashboard: http://localhost:" + s.Port + "/dashboard/")
	log.Println("SSE:       http://localhost:" + s.Port + "/api/events")

	return http.ListenAndServe(":"+s.Port, mux)
}
