import { useState, useRef, useEffect, KeyboardEvent } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Message {
  role: "user" | "agent";
  content: string;
}

const STARTER_PROMPTS = [
  "I need to set up my Strat from scratch — where do I start?",
  "My guitar has fret buzz on the low strings",
  "Walk me through setting intonation step by step",
  "My pickup is humming really badly — how do I fix it?",
  "How do I wire a new humbucker pickup?",
  "What strings should I use for Drop D tuning?",
];

function TypingIndicator() {
  return (
    <div className="message agent">
      <span className="message-label">SHRED TECH</span>
      <div className="typing-indicator">
        <div className="typing-dot" />
        <div className="typing-dot" />
        <div className="typing-dot" />
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(Math.max(el.scrollHeight, 48), 200) + "px";
  };

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text.trim(),
          session_id: sessionId,
        }),
      });

      if (res.status === 429) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: `Rate limit reached — ${data.detail}` },
        ]);
        return;
      }

      if (res.status === 422) {
        const data = await res.json();
        const detail = data.detail?.[0]?.msg || "Invalid input.";
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: detail },
        ]);
        return;
      }

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: data.response },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content:
            "Connection error — make sure the backend is running on port 8000.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const handleReset = () => {
    setMessages([]);
    setSessionId(null);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const showWelcome = messages.length === 0 && !isLoading;

  return (
    <div className="app">
      <header className="header">
        <span className="header-icon">🎸</span>
        <div className="header-text">
          <div className="header-title">SHRED TECH</div>
          <div className="header-subtitle">Guitar Setup Assistant · Powered by Gemini</div>
        </div>
      </header>

      {showWelcome ? (
        <div className="welcome">
          <div className="welcome-hero">
            <div className="welcome-icon">🎸</div>
            <h1 className="welcome-heading">SHRED TECH</h1>
            <p className="welcome-tagline">
              Professional guitar setup, diagnostics, and electronics — from truss rod to pickup wiring.
              Tell me what you're working on.
            </p>
          </div>
          <div className="welcome-prompts">
            <div className="welcome-prompts-label">Try asking</div>
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                className="starter-btn"
                onClick={() => sendMessage(prompt)}
              >
                <span className="prompt-arrow">›</span>
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="chat-container">
          <div className="chat-header">
            <button className="reset-btn" onClick={handleReset}>
              New session
            </button>
          </div>
          <div className="messages">
            {messages.map((msg, i) => (
              <div key={i} className={`message ${msg.role}`}>
                <span className="message-label">
                  {msg.role === "user" ? "YOU" : "SHRED TECH"}
                </span>
                <div className="message-bubble">{msg.content}</div>
              </div>
            ))}
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      <div className="input-area">
        <div className="input-row">
          <div className="input-wrapper">
            <textarea
              ref={textareaRef}
              className="message-input"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                autoResize();
              }}
              onKeyDown={handleKeyDown}
              placeholder="Describe your guitar issue or ask a setup question..."
              disabled={isLoading}
            />
          </div>
          <button
            className="send-btn"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
          >
            Send ›
          </button>
        </div>
        <div className="input-hint">Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  );
}
