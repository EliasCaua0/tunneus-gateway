package handlers

import (
	"fmt"
	"net/http"
)

func Root(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintln(w, "Tunneus Gateway Online")
}
