"use client";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8787/ws/events";

type Handler = (event: WsEvent) => void;

export interface WsEvent {
  type: string;
  id: number;
  ts: number;
  payload: Record<string, unknown>;
}

class EventBus {
  private ws: WebSocket | null = null;
  private handlers = new Set<Handler>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    try {
      this.ws = new WebSocket(WS_URL);
      this.ws.onmessage = (e) => {
        try {
          const event: WsEvent = JSON.parse(e.data);
          this.handlers.forEach((h) => h(event));
        } catch {}
      };
      this.ws.onclose = () => this.scheduleReconnect();
      this.ws.onerror = () => this.ws?.close();
    } catch {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  subscribe(handler: Handler): () => void {
    this.handlers.add(handler);
    this.connect();
    return () => { this.handlers.delete(handler); };
  }
}

export const eventBus = new EventBus();
