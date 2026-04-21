from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "feihualing API"
    database_url: str

    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "quentinz/bge-large-zh-v1.5"
    embedding_dim: int = 1024

    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_chat_model: str = "qwen-plus"

    rag_top_k: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()
