import uuid
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Turn:
    user: str
    assistant: str

class ConversationStore:
    def __init__(self):
        self._conversations: Dict[str, List[Turn]] = {}

    def get_history(self, conversation_id: str) -> List[Turn]:
        return self._conversations.get(conversation_id, [])

    def append_turn(self, conversation_id: str, turn: Turn) -> None:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        self._conversations[conversation_id].append(turn)
        
    def create_conversation(self) -> str:
        cid = str(uuid.uuid4())
        self._conversations[cid] = []
        return cid
