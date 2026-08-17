import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


class Neo4jClient:
    """Use the Bolt driver, with the HTTPS Query API as a network fallback."""

    def __init__(self, uri, user, password, database="neo4j"):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._transport = "bolt"

    def _query_api_url(self):
        host = self.uri.split("://", 1)[-1].rstrip("/")
        return f"https://{host}/db/{self.database}/query/v2"

    def _run_https(self, query, params=None, access_mode="Write"):
        credentials = base64.b64encode(
            f"{self.user}:{self.password}".encode("utf-8")
        ).decode("ascii")
        body = json.dumps(
            {
                "statement": " ".join(query.splitlines()),
                "parameters": params or {},
                "accessMode": access_mode,
            }
        ).encode("utf-8")
        request = Request(
            self._query_api_url(),
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {credentials}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Neo4j HTTPS query failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Neo4j HTTPS connection failed: {exc.reason}") from exc

        data = payload.get("data", {})
        fields = data.get("fields", [])
        return [dict(zip(fields, values)) for values in data.get("values", [])]

    def verify_connectivity(self):
        try:
            return self._driver.verify_connectivity()
        except ServiceUnavailable:
            self._run_https("RETURN 1 AS ok", access_mode="Read")
            self._transport = "https"
            return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def session(self):
        """Provide the context-manager shape used by the official driver."""
        return self

    def execute_write(self, transaction_function):
        """Run a driver-style transaction callback through the active transport."""
        return transaction_function(self)

    def execute(self, query, params=None, access_mode="Read"):
        if self._transport == "https":
            return self._run_https(query, params, access_mode=access_mode)
        with self._driver.session(database=self.database) as session:
            result = session.run(query, **(params or {}))
            return [record.data() for record in result]

    def run(self, query, params=None, **kwargs):
        parameters = dict(params or {})
        parameters.update(kwargs)
        normalized = query.lstrip().upper()
        write_keywords = ("CREATE", "DELETE", "DETACH", "MERGE", "REMOVE", "SET")
        access_mode = "Write" if any(word in normalized for word in write_keywords) else "Read"
        return self.execute(query, parameters, access_mode=access_mode)

    def close(self):
        self._driver.close()


def get_driver():
    """Return a Neo4j client configured from environment variables."""
    load_dotenv()
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not uri or not user or not password:
        raise RuntimeError("Missing Neo4j credentials in environment")
    return Neo4jClient(uri, user, password, database)


def verify_connectivity(driver):
    return driver.verify_connectivity()


def run_query(driver, query, params=None):
    return driver.run(query, params)
