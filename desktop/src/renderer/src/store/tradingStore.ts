import { create } from 'zustand';

export type SignalLifecycleState = 'IDLE' | 'GENERATED' | 'LOCKED' | 'ACTIVE' | 'CLOSED' | 'RESET';

export interface ActiveSignal {
    signal_id: string;
    version_number: number;
    asset: string;
    direction: 'LONG' | 'SHORT';
    state: SignalLifecycleState;
    entry_price: number;
    stop_price: number;
    target_price: number;
    candle_index: number;
    timeframe: string;
    confidence: number;
    position_size_pct: number;
    current_r: number;
    highest_r: number;
    candles_elapsed: number;
    is_terminal: boolean;
    resolution_reason: string | null;
    metadata: Record<string, any>;
}

export interface TradingState {
    // Idempotency tracking
    lastSequenceNumber: number;

    // Core state from snapshot
    systemHalted: boolean;
    activeSignals: Record<string, ActiveSignal>; // Mapped by signal_id
    portfolioState: Record<string, any>;
    riskState: Record<string, any>;

    // Debug/Diagnostics
    lastSnapshotUtc: number | null;
    lastEventTimestampUtc: number | null;
    engineClockHash: string | null;

    // Snapshot Race Barrier
    hasReceivedSnapshot: boolean;
    eventBuffer: any[];

    // Actions
    processEvent: (payload: any) => void;
    processSnapshot: (payload: any) => void;
    clearSignals: () => void;
}

export const useTradingStore = create<TradingState>((set, get) => ({
    lastSequenceNumber: -1,

    systemHalted: false,
    activeSignals: {},
    portfolioState: {},
    riskState: {},

    lastSnapshotUtc: null,
    lastEventTimestampUtc: null,
    engineClockHash: null,

    hasReceivedSnapshot: false,
    eventBuffer: [],

    clearSignals: () => {
        set({ activeSignals: {} });
        console.log('[Store] Signals cleared (chart switch)');
    },

    processSnapshot: (payload) => {
        // Reconnection or initial load sync
        set((state) => {
            // Safety: Only accept snapshot if it's newer than our sequence stream,
            // or if we have no sequence (initial load).
            if (payload.snapshot_sequence_number < state.lastSequenceNumber && state.lastSequenceNumber !== -1) {
                console.warn(`[Store] Ignored stale snapshot sequence ${payload.snapshot_sequence_number}`);
                return state;
            }

            const newSignals: Record<string, ActiveSignal> = {};
            (payload.active_signals || []).forEach((sig: ActiveSignal) => {
                newSignals[sig.signal_id] = Object.freeze(sig); // 6. Deep freeze
            });

            console.log(`[Store] Hydrated from snapshot up to sequence ${payload.snapshot_sequence_number}`);

            // Flush Event Buffer
            const buffer = state.eventBuffer;
            const validBufferedEvents = buffer.filter(e => e.event_sequence_number > payload.snapshot_sequence_number);

            return {
                lastSequenceNumber: payload.snapshot_sequence_number,
                systemHalted: payload.system_halted || false,
                activeSignals: newSignals,
                portfolioState: payload.portfolio_state || {},
                riskState: payload.risk_state || {},
                lastSnapshotUtc: payload.timestamp_utc,
                hasReceivedSnapshot: true,
                eventBuffer: validBufferedEvents // Temporarily hold to flush outside set
            };
        });

        // Recursively apply buffered events sequentially
        const remaining = get().eventBuffer;

        // Clear buffer before flushing to avoid loops
        set({ eventBuffer: [] });

        remaining.forEach(evt => {
            get().processEvent(evt);
        });
    },

    processEvent: (payload) => {
        const state = get();

        // 2. Snapshot Race Barrier
        if (!state.hasReceivedSnapshot) {
            set((draft) => ({ eventBuffer: [...draft.eventBuffer, payload] }));
            console.log(`[Store] Buffered event ${payload.event_sequence_number} pending snapshot...`);
            return;
        }

        // ── Idempotency & Sequencing Check ──
        const seq = payload.event_sequence_number;

        if (seq !== undefined) {
            if (seq <= state.lastSequenceNumber) {
                console.debug(`[Store] Ignored duplicate/stale event sequence: ${seq}`);
                return;
            }

            if (seq > state.lastSequenceNumber + 1 && state.lastSequenceNumber !== -1) {
                console.warn(`[Store] Sequence gap detected! Expected ${state.lastSequenceNumber + 1}, got ${seq}. Reconnection may be necessary.`);
                // Note: A robust implementation might trigger a WS reconnect here to grab a fresh snapshot.
            }
        }

        // ── Apply Event Mutation ──
        set((draft) => {
            const updates: Partial<TradingState> = {
                lastSequenceNumber: seq !== undefined ? seq : draft.lastSequenceNumber,
                lastEventTimestampUtc: payload.signal_timestamp_utc || draft.lastEventTimestampUtc,
                engineClockHash: payload.engine_clock_hash || draft.engineClockHash,
            };

            if (payload.event === 'SYSTEM_HALTED') {
                updates.systemHalted = true;
            }
            else if (payload.event?.startsWith('SIGNAL_')) {
                const sigData: ActiveSignal = payload.signal;
                if (sigData && sigData.signal_id) {
                    const currentSig = draft.activeSignals[sigData.signal_id];

                    // Version idempotency (defensive)
                    if (currentSig && currentSig.signal_id === sigData.signal_id && sigData.version_number <= currentSig.version_number) {
                        console.debug(`[Store] Ignored stale signal version: ${sigData.version_number}`);
                        return draft; // Abort set entirely if version is stale
                    }

                    const newActiveSignals = { ...draft.activeSignals };

                    if (sigData.is_terminal) {
                        // Remove from active tracking once terminal (target/stop hit)
                        delete newActiveSignals[sigData.signal_id];
                    } else {
                        // Upsert ACTIVE/LOCKED signal (frozen)
                        newActiveSignals[sigData.signal_id] = Object.freeze(sigData);
                    }

                    updates.activeSignals = newActiveSignals;
                }
            }

            return updates;
        });
    }
}));
