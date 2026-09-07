# Patch conversation.py
with open("apps/api/src/rag_api/services/conversation.py", "r") as f:
    text = f.read()

delete_meth = """
    def update_turn_feedback(self, conversation_id: str, turn_index: int, is_positive: bool | None) -> None:"""

new_delete_meth = """
    def delete_conversation(self, conversation_id: str) -> None:
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
        if conversation_id in self._metadata:
            del self._metadata[conversation_id]

    def update_turn_feedback(self, conversation_id: str, turn_index: int, is_positive: bool | None) -> None:"""

text = text.replace(delete_meth, new_delete_meth)
with open("apps/api/src/rag_api/services/conversation.py", "w") as f:
    f.write(text)


# Patch redis_conversation.py
with open("apps/api/src/rag_api/services/redis_conversation.py", "r") as f:
    text = f.read()

delete_meth2 = """
    def update_turn_feedback(self, conversation_id: str, turn_index: int, is_positive: bool | None) -> None:"""

new_delete_meth2 = """
    def delete_conversation(self, conversation_id: str) -> None:
        self._client.delete(f"conv:{conversation_id}")
        self._client.delete(f"conv_meta:{conversation_id}")
        self._client.srem("conversations:all", conversation_id)

    def update_turn_feedback(self, conversation_id: str, turn_index: int, is_positive: bool | None) -> None:"""

text = text.replace(delete_meth2, new_delete_meth2)
with open("apps/api/src/rag_api/services/redis_conversation.py", "w") as f:
    f.write(text)


# Patch conversations.py router
with open("apps/api/src/rag_api/api/v1/conversations.py", "r") as f:
    text = f.read()

delete_route = """
@router.delete("/{conversation_id}", summary="Delete conversation")
def delete_conversation(conversation_id: str, store=Depends(get_conversation_store)):
    store.delete_conversation(conversation_id)
    return {"status": "deleted"}
"""

if "def delete_conversation" not in text:
    text += delete_route
    with open("apps/api/src/rag_api/api/v1/conversations.py", "w") as f:
        f.write(text)

