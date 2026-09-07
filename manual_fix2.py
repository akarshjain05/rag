with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

bad_set = """      if (!conversationId && res.conversation_id) {
        skipFetch.current = true;
        setConversationId(res.conversation_id);
      }"""

good_set = """      if (!conversationId && res.conversation_id) {
        skipFetch.current = true;
        setConversationId(res.conversation_id);
      }
      if (onNewMessage) onNewMessage();"""

text = text.replace(bad_set, good_set)

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)
