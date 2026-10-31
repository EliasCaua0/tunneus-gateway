package main

import (
	"log"

	"github.com/arcanlab/tunneus/internal/server"
)

func main() {

	log.Println("===================================")
	log.Println("      Tunneus Gateway v0.1")
	log.Println("===================================")

	srv := server.New("18080")

	if err := srv.Start(); err != nil {
		log.Fatal(err)
	}
}
