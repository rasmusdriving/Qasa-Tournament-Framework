from pydantic import BaseModel

# ... existing schemas ...

class RoundUpdate(BaseModel):
    name: str
