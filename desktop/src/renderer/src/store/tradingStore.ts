import { create } from 'zustand';

// ══════════════════════════════════════════════════════════════
// TYPE DEFINITIONS
// ══════════════════════════════════════════════════════════════

export interface CandleData {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface Position {
    symbol: string;
    side: string;
    quantity: number;
    avg_entry_price: number;
    current_price: number;
    unrealized_pnl: number;
}

export interface Signal {
    signal_id: string;
    asset: string;
    direction: string;
    entry_price: number;
    stop_price: number;
    target_price: number;
    state: string;
    confidence: number;
    strategy_name: string;
    created_at: number;
}

export interface TradeRecord {
    trade_id: string;
    symbol: string;
    direction: string;
    entry_price: number;
    exit_price: number;
    quantity: number;
    net_pnl: number;
    r_achieved: number;
    strategy_name: string;
    closed_at: number;
}

export interface OrderRecord {
    order_id: string;
    symbol: string;
    side: string;
    order_type: string;
    quantity: number;
    price: number;
    status: string;
    created_at: number;
}

export interface PortfolioState {
    status: string;
    mode: string;
    total_equity: number;
    cash_balance: number;
    buying_power: number;
    drawdown_pct: number;
    risk_mode: string;
    open_positions: number;
    total_trades: number;
    total_pnl: number;
    broker_live: boolean;
    positions: Position[];
}

export interface RiskState {
    mode: string;
    kill_switch_active: boolean;
    kill_switch_reason: string;
    drawdown_pct: number;
    broker_connected: boolean;
    circuit_breaker: { is_open: boolean; failures: number };
}

export interface SystemStatus {
    running: boolean;
    mode: string;
    market: string;
    bar_counter: number;
    symbols: string[];
    broker: Record<string, any>;
}

export interface IndicatorData {
    rsi: number[];
    macd: { line: number[]; signal: number[]; histogram: number[] };
    atr: number[];
    bollinger: { upper: number[]; middle: number[]; lower: number[] };
    ml_prediction?: {
        direction: 'UP' | 'DOWN';
        confidence: number;
        magnitude: number;
        entry_price: number;
        stop_price: number;
        target_price: number;
        model_accuracy: number;
        top_features: { name: string; importance: number }[];
        lookforward: number;
        trained_on: number;
    } | null;
}

// ══════════════════════════════════════════════════════════════
// STORE
// ══════════════════════════════════════════════════════════════

export interface TradingState {
    // Symbol selection
    selectedSymbol: string;
    selectedTimeframe: string;
    symbols: string[];
    market: string;

    // Market data
    candles: CandleData[];
    indicators: IndicatorData | null;

    // Portfolio
    portfolio: PortfolioState | null;

    // Signals and Trades
    activeSignals: Signal[];
    tradeHistory: TradeRecord[];
    recentOrders: OrderRecord[];
    tradeStats: { total: number; wins: number; losses: number; win_rate: number; total_net_pnl: number; avg_r: number };

    // Risk & System
    riskState: RiskState | null;
    systemStatus: SystemStatus | null;

    // Connection
    wsConnected: boolean;
    lastUpdate: number;
    loading: boolean;
    error: string | null;

    // Actions
    setMarket: (market: string) => Promise<void>;
    setSymbol: (symbol: string) => void;
    setTimeframe: (tf: string) => void;
    fetchAll: () => Promise<void>;
    fetchCandles: () => Promise<void>;
    fetchIndicators: () => Promise<void>;
    connectWebSocket: () => void;
    disconnectWebSocket: () => void;
}

const API = 'http://localhost:8000';
const WS_API = 'ws://localhost:8000';

let wsInstance: WebSocket | null = null;
let candleIntervalId: ReturnType<typeof setInterval> | null = null;

export const useTradingStore = create<TradingState>((set, get) => ({
    selectedSymbol: 'AAPL',
    selectedTimeframe: '15m',
    symbols: [],
    market: 'USA',

    candles: [],
    indicators: null,

    portfolio: null,

    activeSignals: [],
    tradeHistory: [],
    recentOrders: [],
    tradeStats: { total: 0, wins: 0, losses: 0, win_rate: 0, total_net_pnl: 0, avg_r: 0 },

    riskState: null,
    systemStatus: null,

    wsConnected: false,
    lastUpdate: 0,
    loading: true,
    error: null,

    setMarket: async (market) => {
        try {
            const res = await fetch(`${API}/api/trading/market`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ market })
            });
            if (res.ok) {
                const data = await res.json();
                set({ market: data.market, symbols: data.symbols, selectedSymbol: data.symbols[0], candles: [], indicators: null });
                setTimeout(() => {
                    get().fetchAll();
                    get().fetchCandles();
                    get().fetchIndicators();
                }, 0);
            }
        } catch (err) {
            console.error("Failed to set market:", err);
        }
    },

    setSymbol: (symbol) => {
        set({ selectedSymbol: symbol, candles: [], indicators: null });
        // Re-fetch data for new symbol
        setTimeout(() => {
            get().fetchCandles();
            get().fetchIndicators();
        }, 0);
    },

    setTimeframe: (tf) => {
        set({ selectedTimeframe: tf, candles: [], indicators: null });
        setTimeout(() => {
            get().fetchCandles();
            get().fetchIndicators();
        }, 0);
    },

    fetchCandles: async () => {
        const { selectedSymbol, selectedTimeframe } = get();
        try {
            const res = await fetch(`${API}/api/trading/candles?symbol=${selectedSymbol}&timeframe=${selectedTimeframe}&limit=200`);
            if (res.ok) {
                const data = await res.json();
                const newCandles = data.candles || [];
                // Only update if data actually changed (prevents unnecessary re-renders)
                const existing = get().candles;
                let shouldUpdate = false;
                
                if (existing.length === 0 || newCandles.length === 0) {
                    shouldUpdate = true;
                } else if (existing.length !== newCandles.length) {
                    shouldUpdate = true;
                } else {
                    const eLast = existing[existing.length - 1];
                    const nLast = newCandles[newCandles.length - 1];
                    if (
                        eLast.time !== nLast.time ||
                        eLast.close !== nLast.close ||
                        eLast.high !== nLast.high ||
                        eLast.low !== nLast.low ||
                        eLast.volume !== nLast.volume
                    ) {
                        shouldUpdate = true;
                    }
                }

                if (shouldUpdate) {
                    set({ candles: newCandles });
                }
            }
        } catch (e) {
            console.error('Failed to fetch candles:', e);
        }
    },

    fetchIndicators: async () => {
        const { selectedSymbol, selectedTimeframe } = get();
        try {
            const res = await fetch(`${API}/api/trading/indicators?symbol=${selectedSymbol}&timeframe=${selectedTimeframe}`);
            if (res.ok) {
                const data = await res.json();
                set({ indicators: data.indicators || null });
            }
        } catch (e) {
            console.error('Failed to fetch indicators:', e);
        }
    },

    fetchAll: async () => {
        set({ loading: true, error: null });
        try {
            const [portfolioRes, signalsRes, riskRes, symbolsRes, systemRes] = await Promise.allSettled([
                fetch(`${API}/api/trading/portfolio`),
                fetch(`${API}/api/trading/signals`),
                fetch(`${API}/api/trading/risk`),
                fetch(`${API}/api/trading/symbols`),
                fetch(`${API}/api/trading/system`),
            ]);

            if (portfolioRes.status === 'fulfilled' && portfolioRes.value.ok) {
                const data = await portfolioRes.value.json();
                set({ portfolio: data });
            }

            if (signalsRes.status === 'fulfilled' && signalsRes.value.ok) {
                const data = await signalsRes.value.json();
                set({
                    activeSignals: data.active || [],
                    tradeHistory: data.history || [],
                    recentOrders: data.recentOrders || [],
                    tradeStats: data.stats || get().tradeStats,
                });
            }

            if (riskRes.status === 'fulfilled' && riskRes.value.ok) {
                const data = await riskRes.value.json();
                set({ riskState: data });
            }

            if (symbolsRes.status === 'fulfilled' && symbolsRes.value.ok) {
                const data = await symbolsRes.value.json();
                if (data.symbols?.length > 0) {
                    set({ symbols: data.symbols });
                    // Set default symbol if current one isn't in the list
                    if (!data.symbols.includes(get().selectedSymbol)) {
                        set({ selectedSymbol: data.symbols[0] });
                    }
                }
            }

            if (systemRes.status === 'fulfilled' && systemRes.value.ok) {
                const data = await systemRes.value.json();
                set({ systemStatus: data });
            }

            set({ loading: false, lastUpdate: Date.now() });

            // Also fetch chart data
            await get().fetchCandles();
            await get().fetchIndicators();

        } catch (e: any) {
            set({ loading: false, error: e.message || 'Failed to connect to backend' });
        }
    },

    connectWebSocket: () => {
        if (wsInstance) return;

        const ws = new WebSocket(`${WS_API}/api/trading/ws`);
        wsInstance = ws;

        ws.onopen = () => {
            set({ wsConnected: true, error: null });
            // Initial data fetch
            get().fetchAll();

            // ── LIVE CANDLE POLLING: Refresh chart data every 3 seconds ──
            if (candleIntervalId) clearInterval(candleIntervalId);
            candleIntervalId = setInterval(() => {
                get().fetchCandles();
                get().fetchIndicators();
            }, 3_000); // 3 seconds for near-real-time updates
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'HEARTBEAT' && data.data) {
                    set({
                        portfolio: data.data.portfolio,
                        activeSignals: data.data.activeSignals || [],
                        tradeHistory: data.data.tradeHistory || [],
                        recentOrders: data.data.recentOrders || [],
                        systemStatus: data.data.system,
                        riskState: data.data.risk,
                        lastUpdate: Date.now(),
                    });
                }
            } catch (e) {
                console.error('Failed to parse WebSocket message', e);
            }
        };

        ws.onclose = () => {
            wsInstance = null;
            set({ wsConnected: false });
            // Stop candle polling
            if (candleIntervalId) { clearInterval(candleIntervalId); candleIntervalId = null; }
            // Reconnect attempt
            setTimeout(() => {
                get().connectWebSocket();
            }, 5000);
        };

        ws.onerror = () => {
            set({ error: 'WebSocket connection error' });
            ws.close();
        };
    },

    disconnectWebSocket: () => {
        // Stop candle polling
        if (candleIntervalId) { clearInterval(candleIntervalId); candleIntervalId = null; }
        if (wsInstance) {
            wsInstance.onclose = null; // Prevent auto-reconnect
            wsInstance.close();
            wsInstance = null;
            set({ wsConnected: false });
        }
    },
}));
