import { useState, useRef, useEffect } from "react";
import { chatQuery } from "../api/graphApi";

export default function QueryPanel({ onChatResponse }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! How can I help you explore the Order-to-Cash data today?" }
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (textOverride) => {
    const text = typeof textOverride === "string" ? textOverride : input;
    if (!text.trim() || loading) return;

    const userMessage = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const result = await chatQuery(userMessage.content);
      const assistantMessage = { 
        role: "assistant", 
        content: result.answer,
        intent: result.intent
      };
      setMessages((prev) => [...prev, assistantMessage]);
      
      if (onChatResponse) {
        onChatResponse(result);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message}` }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel chat-panel">
      <div className="chat-header">
        <h2>AI Query Assistant</h2>
      </div>
      
      <div className="chat-history">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-bubble ${msg.role}`}>
            <div className="bubble-content">
              {msg.content}
            </div>
            {msg.intent && msg.intent !== "UNKNOWN" && msg.intent !== "REJECTED" && (
              <div className="intent-badge">{msg.intent.replace('_', ' ')}</div>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble assistant loading">
            <span className="dot"></span><span className="dot"></span><span className="dot"></span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="chat-suggestions">
        <button className="suggestion-pill" onClick={() => handleSend("Trace billing document 90504248")}>
          Trace Billing Doc
        </button>
        <button className="suggestion-pill" onClick={() => handleSend("Find broken flows")}>
          Broken Flows
        </button>
      </div>

      <div className="chat-input-area">
        <input 
          type="text" 
          className="form-input chat-input" 
          placeholder="Ask a question..." 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          disabled={loading}
        />
        <button 
          className="btn btn-primary" 
          onClick={handleSend}
          disabled={!input.trim() || loading}
        >
          Send
        </button>
      </div>
    </section>
  );
}

