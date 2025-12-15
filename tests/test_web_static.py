import os
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from agentfw.web.server import AgentEditorHandler


class TestWebStatic:
    def setup_method(self) -> None:
        self.original_cwd = os.getcwd()
        self.static_dir = Path(__file__).resolve().parents[1] / "agentfw" / "web" / "static"
        os.chdir(self.static_dir)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AgentEditorHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def teardown_method(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        os.chdir(self.original_cwd)

    def _get(self, path: str) -> str:
        conn = HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", path)
        response = conn.getresponse()
        payload = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200
        return payload

    def test_serves_index_and_assets(self) -> None:
        html = self._get("/")
        assert "Редактор агентів" in html
        assert "app.js" in html
        assert "styles.css" in html
        assert "graphCanvas" in html

        script = self._get("/app.js")
        assert "fetch('/api/tools')" in script

        css = self._get("/styles.css")
        assert "font-family" in css
