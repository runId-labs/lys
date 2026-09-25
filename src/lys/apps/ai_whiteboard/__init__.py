"""
Whiteboard app: a visual surface the chatbot draws on, and the user edits by hand.

The scene is an Excalidraw document stored as JSON. The LLM never emits it whole —
it emits semantic operations that the service applies — so a turn can never corrupt
what it did not mean to touch.

Depends on ``lys.apps.ai``: the app extends AIConversation and contributes chatbot
tools. Load it AFTER ``lys.apps.ai``, and before any consumer that overrides
AIConversationService — a consumer's own override must inherit from this app's, or
the tools are silently absent.

Kept out of ``lys.apps.ai`` on purpose: the chatbot is useful without a whiteboard,
and a consumer that does not want one should not carry the table, the tools, nor the
Excalidraw format in its data model.
"""
