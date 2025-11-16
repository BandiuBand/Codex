from dataclasses import dataclass
import os


@dataclass
class GraphSettings:
    """Configuration for Neo4j + Ollama powered graph building."""

    neo4j_url: str = os.getenv("NEO4J_URL", "bolt://localhost:7687")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "21599031janeShicoryack")
    neo4j_database: str | None = os.getenv("NEO4J_DATABASE") or None

    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:32b")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))

    verification_interval_seconds: int = int(
        os.getenv("VERIFICATION_INTERVAL_SECONDS", "900")
    )
    max_relationship_suggestions: int = int(
        os.getenv("MAX_RELATIONSHIP_SUGGESTIONS", "5")
    )

    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    def neo4j_kwargs(self) -> dict:
        """Return keyword args suitable for Neo4jGraph construction."""

        kwargs = {
            "url": self.neo4j_url,
            "username": self.neo4j_username,
            "password": self.neo4j_password,
        }
        if self.neo4j_database:
            kwargs["database"] = self.neo4j_database
        return kwargs
