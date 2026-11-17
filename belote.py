#!/usr/bin/env python3
"""
Belote — tournoi de belote : 2n joueurs -> n équipes -> championnat (toutes rondes).

Lancement :
    python3 belote.py                 ouvre l'interface dans le navigateur (http://127.0.0.1:8777)
    python3 belote.py --port 9000
    python3 belote.py --sans-navigateur

La formation des équipes se fait dans le navigateur (tirage au sort ou équilibré par niveau).
Le calendrier du championnat est calculé par le moteur de ../Championnat/Tournoi/tournoi.py
(module moteur.py : cercle de Berger, aller simple ou aller-retour).
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ICI = os.path.dirname(os.path.abspath(__file__))


def relancer_si_besoin():
    """Si numpy manque dans l'interpréteur courant, relance avec un interpréteur qui l'a."""
    try:
        import numpy  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("BELOTE_RELANCE"):
        sys.exit("numpy est introuvable : pip install numpy")
    import subprocess
    candidats = [os.path.join(ICI, "..", "Championnat", "berger-championnat", ".venv", "bin", "python"),
                 os.path.join(ICI, "..", "Championnat", "Tournoi", ".venv", "bin", "python"),
                 "/usr/bin/python3"]
    for py in candidats:
        py = os.path.abspath(py)
        if os.path.exists(py) and subprocess.run([py, "-c", "import numpy"], capture_output=True).returncode == 0:
            print(f"numpy absent ici : relance avec {py}")
            os.environ["BELOTE_RELANCE"] = "1"
            os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
    sys.exit("numpy est introuvable : pip install numpy")


relancer_si_besoin()
sys.path.insert(0, os.path.join(ICI, "..", "Championnat", "Tournoi"))
import moteur  # noqa: E402

REPOS = "(repos)"


def championnat(equipes, retour):
    """equipes : liste de noms d'équipes. Renvoie les journées [[(i, j), ...], ...] et les équipes au repos."""
    n = len(equipes)
    if n < 2:
        raise ValueError("Il faut au moins 2 équipes (4 joueurs).")
    if retour not in ("aucun", "pur"):
        retour = "aucun"
    fantome = n % 2 == 1
    m = n + 1 if fantome else n
    if m == 2:
        rondes = [[[0, 1]]]
        if retour == "pur":
            rondes.append([[1, 0]])
    else:
        r = moteur.generer({"n": m, "methode": "berger", "retour": retour,
                            "noms": list(equipes) + ([REPOS] if fantome else [])})
        rondes = r["journees"]
    journees = []
    for matchs in rondes:
        vrais = [[a, b] for a, b in matchs if a < n and b < n]
        reposant = [x for pair in matchs for x in pair if x < n and (pair[0] >= n or pair[1] >= n)]
        journees.append({"matchs": vrais, "repos": reposant})
    return journees


TYPES = {".html": "text/html; charset=utf-8"}


class Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        corps = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        if self.path.split("?")[0] not in ("/", "/index.html"):
            return self.send_error(404)
        with open(os.path.join(ICI, "index.html"), "rb") as f:
            corps = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(corps)

    def do_POST(self):
        if self.path != "/api/championnat":
            return self.send_error(404)
        try:
            taille = int(self.headers.get("Content-Length", 0) or 0)
            d = json.loads(self.rfile.read(taille).decode() or "{}")
            noms = [str(x) for x in d.get("equipes", [])]
            return self._json({"journees": championnat(noms, d.get("retour", "aucun"))})
        except ValueError as e:
            return self._json({"erreur": str(e)}, 400)


def main():
    ap = argparse.ArgumentParser(description="Tournoi de belote : équipes et championnat.")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--sans-navigateur", action="store_true")
    a = ap.parse_args()
    for p in range(a.port, a.port + 20):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Gestionnaire)
            break
        except OSError:
            continue
    else:
        sys.exit("Aucun port libre.")
    url = f"http://127.0.0.1:{p}/"
    print(f"Belote — interface : {url}   (Ctrl+C pour arrêter)")
    if not a.sans_navigateur:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")


if __name__ == "__main__":
    main()
