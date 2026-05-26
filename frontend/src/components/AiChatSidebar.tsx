import { useState, useRef, useEffect } from 'react';
import { Input, Collapse, Tag } from 'antd';
import { SendOutlined, SearchOutlined, LoadingOutlined } from '@ant-design/icons';
import MarkdownRenderer from './MarkdownRenderer';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import type { ChatMessage, ToolCall, AgentEvent } from '../types';

const primary = '#5b5feb';
const textColor = '#1e1e24';
const textSecondary = '#6b7280';
const borderColor = '#e8e8ed';
const cardBg = '#ffffff';

interface Props {
  lessonId: number;
  lessonTitle: string;
  onCollapse: () => void;
}

interface StreamState {
  fullText: string;
  toolCalls: ToolCall[];
}

function applyAgentEvent(
  event: AgentEvent,
  state: StreamState,
  setThinking: (v: boolean) => void,
  setTools: (v: ToolCall[]) => void,
  setText: (v: string) => void,
) {
  switch (event.type) {
    case 'agent_thinking':
      setThinking(true);
      break;
    case 'tool_call':
      setThinking(false);
      state.toolCalls.push({ name: event.tool || 'unknown', arguments: event.args || {} });
      setTools([...state.toolCalls]);
      break;
    case 'tool_result':
      break;
    case 'agent_done':
      state.fullText = event.text || '';
      setText(state.fullText);
      break;
    case 'agent_error':
      state.fullText = `Error: ${event.error || 'Unknown error'}`;
      setText(state.fullText);
      break;
  }
}

export default function AiChatSidebar({ lessonId, lessonTitle: _lessonTitle, onCollapse }: Props) {
  const { t } = useContentLang();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [streamingToolCalls, setStreamingToolCalls] = useState<ToolCall[]>([]);
  const [streamingThinking, setStreamingThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Reset chat when switching to a different lesson
  useEffect(() => {
    setMessages([]);
    setStreaming(false);
    setStreamingText('');
    setStreamingToolCalls([]);
    setStreamingThinking(false);
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, [lessonId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, streamingToolCalls]);

  const resetStreaming = () => {
    setStreamingText('');
    setStreamingToolCalls([]);
    setStreamingThinking(false);
  };

  const finishMessage = (finalText: string, tc: ToolCall[]) => {
    setStreaming(false);
    resetStreaming();
    setMessages((prev) => [...prev, {
      role: 'assistant',
      content: finalText,
      toolCalls: tc.length > 0 ? tc : undefined,
    }]);
    abortRef.current = null;
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput('');

    setMessages([...messages, { role: 'user', content: text }]);
    setStreaming(true);
    resetStreaming();

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const state: StreamState = { fullText: '', toolCalls: [] };

    try {
      await api.chat(
        lessonId, text, messages,
        (e) => applyAgentEvent(e, state, setStreamingThinking, setStreamingToolCalls, setStreamingText),
        ctrl.signal,
      );
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        state.fullText = `Error: ${err?.message || 'Request failed'}`;
        setStreamingText(state.fullText);
      }
    }

    finishMessage(state.fullText, state.toolCalls);
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: cardBg }}>
      <style>{`
        @keyframes afs-fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes afs-dotPulse {
          0%, 60%, 100% { transform: scale(0.7); opacity: 0.25; }
          30% { transform: scale(1); opacity: 0.7; }
        }
        .afs-msg-enter {
          animation: afs-fadeInUp 0.3s ease-out both;
        }
      `}</style>

      {/* Header */}
      <div
        style={{
          padding: '14px 20px',
          borderBottom: `1px solid ${borderColor}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span
          style={{
            fontSize: 15,
            fontWeight: 500,
            color: textColor,
            letterSpacing: '-0.01em',
          }}
        >
          {t('chat.title')}
        </span>
        <button
          type="button"
          onClick={onCollapse}
          style={{
            background: 'none',
            border: 'none',
            color: textSecondary,
            fontSize: 12,
            cursor: 'pointer',
            padding: '4px 10px',
            borderRadius: 6,
          }}
        >
          {t('chat.collapse')}
        </button>
      </div>

      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '16px 16px 8px',
        }}
      >
        {/* Empty state */}
        {messages.length === 0 && !streaming && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              paddingBottom: 48,
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: '50%',
                border: `1.5px solid ${borderColor}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 16,
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: primary,
                  opacity: 0.35,
                }}
              />
            </div>
            <span
              style={{
                fontSize: 13,
                color: textSecondary,
                lineHeight: '20px',
              }}
            >
              {t('chat.emptyHint')}
            </span>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <div
            key={i}
            className="afs-msg-enter"
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              marginBottom: 14,
            }}
          >
            {msg.role === 'user' ? (
              <div
                style={{
                  maxWidth: '80%',
                  background: primary,
                  color: '#fff',
                  borderRadius: '12px 12px 4px 12px',
                  padding: '10px 14px',
                  fontSize: 13,
                  lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                  boxShadow: '0 1px 3px rgba(91,95,235,0.25)',
                }}
              >
                {msg.content}
              </div>
            ) : (
              <div
                style={{
                  maxWidth: '85%',
                  background: cardBg,
                  border: `1px solid ${borderColor}`,
                  borderRadius: '12px 12px 12px 4px',
                  padding: '12px 16px',
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: textColor,
                }}
              >
                {/* Tool calls */}
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    <Collapse
                      size="small"
                      ghost
                      items={msg.toolCalls.map((tc, tci) => ({
                        key: String(tci),
                        label: (
                          <span style={{ fontSize: 12, color: primary }}>
                            <SearchOutlined style={{ marginRight: 6 }} />
                            {tc.name}
                          </span>
                        ),
                        children: (
                          <div style={{ fontSize: 11, color: textSecondary, maxHeight: 120, overflow: 'auto' }}>
                            <div style={{ marginBottom: 4, fontWeight: 500 }}>Arguments:</div>
                            <pre style={{ margin: 0, fontSize: 10, whiteSpace: 'pre-wrap' }}>
                              {JSON.stringify(tc.arguments, null, 2)}
                            </pre>
                          </div>
                        ),
                      }))}
                    />
                  </div>
                )}
                {/* Message content */}
                <MarkdownRenderer content={msg.content} />
              </div>
            )}
          </div>
        ))}

        {/* Streaming tools + text */}
        {streaming && (streamingToolCalls.length > 0 || streamingText || streamingThinking) && (
          <div
            className="afs-msg-enter"
            style={{
              display: 'flex',
              justifyContent: 'flex-start',
              marginBottom: 14,
            }}
          >
            <div
              style={{
                maxWidth: '85%',
                background: cardBg,
                border: `1px solid ${borderColor}`,
                borderRadius: '12px 12px 12px 4px',
                padding: '12px 16px',
                fontSize: 13,
                lineHeight: 1.6,
                color: textColor,
              }}
            >
              {/* Tool calls during streaming */}
              {streamingToolCalls.map((tc, tci) => (
                <div key={tci} style={{
                  marginBottom: 8,
                  padding: '6px 10px',
                  background: '#f5f3ff',
                  borderRadius: 6,
                  fontSize: 11,
                  color: primary,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}>
                  <SearchOutlined />
                  <span style={{ fontWeight: 500 }}>{tc.name}</span>
                  <Tag style={{ fontSize: 10, marginLeft: 'auto', lineHeight: '16px' }}>
                    {t('chat.searching')}
                  </Tag>
                </div>
              ))}
              {/* Thinking indicator */}
              {streamingThinking && !streamingText && (
                <span style={{ fontSize: 12, color: textSecondary, fontStyle: 'italic' }}>
                  <LoadingOutlined style={{ marginRight: 6 }} />
                  {t('chat.thinking')}
                </span>
              )}
              {/* Text */}
              {streamingText && <MarkdownRenderer content={streamingText} />}
            </div>
          </div>
        )}

        {/* Typing indicator (initial state: no tools, no text, no thinking yet) */}
        {streaming && !streamingToolCalls.length && !streamingText && !streamingThinking && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '14px 16px',
            }}
          >
            {[0, 0.2, 0.4].map((delay, idx) => (
              <span
                key={idx}
                style={{
                  display: 'inline-block',
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: textSecondary,
                  animation: `afs-dotPulse 1.4s infinite ease-in-out`,
                  animationDelay: `${delay}s`,
                }}
              />
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div
        style={{
          padding: '10px 16px 12px',
          borderTop: `1px solid ${borderColor}`,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: 8,
          }}
        >
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('chat.placeholder')}
            autoSize={{ minRows: 1, maxRows: 4 }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={streaming}
            variant="borderless"
            style={{ flex: 1, fontSize: 13, padding: '6px 0' }}
          />
          {streaming ? (
            <button
              type="button"
              onClick={handleStop}
              style={{
                background: 'none',
                border: 'none',
                color: '#ef4444',
                fontSize: 12,
                cursor: 'pointer',
                padding: '8px 4px',
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
            >
              {t('chat.stop')}
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim()}
              style={{
                width: 34,
                height: 34,
                borderRadius: '50%',
                border: 'none',
                background: primary,
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: input.trim() ? 'pointer' : 'not-allowed',
                opacity: input.trim() ? 1 : 0.35,
                flexShrink: 0,
                padding: 0,
              }}
            >
              <SendOutlined style={{ fontSize: 14 }} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
