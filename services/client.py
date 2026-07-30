async def generate_json(
    *,
    prompt: str,
    schema: type[BaseModel],
    provider: str = "groq",
):
    ...