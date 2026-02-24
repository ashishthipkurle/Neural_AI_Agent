import React, { useEffect, useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ActiveSignals from './Trading/ActiveSignals';
import RiskMeters from './Trading/RiskMeters';
import OverlayCanvas from './Trading/OverlayCanvas';
import DebugPanel from './Trading/DebugPanel';
import { useTradingStore } from '../../store/tradingStore';

import { X, Globe, Search, Scan, Cpu, ArrowUpCircle, ArrowDownCircle, GripVertical, Eye, Zap, RefreshCw, Plus, Bookmark } from 'lucide-react';

interface TradingViewProps {
    onClose?: () => void;
}

export default function TradingView({ onClose }: TradingViewProps) {
    const [signals, setSignals] = useState<any>(null);
    const [risk, setRisk] = useState<any>(null);
    const [analysisSummary, setAnalysisSummary] = useState<string>('');
    const [loading, setLoading] = useState(true);

    // FIX #1: Track the URL properly and navigate imperatively
    const [url, setUrl] = useState(() => localStorage.getItem('trading_terminal_url') || 'https://groww.in/charts/indices/nifty');
    const [inputUrl, setInputUrl] = useState(url);
    const [webviewReady, setWebviewReady] = useState(false);

    // Phase 4: Subscribe to global store
    const { activeSignals, systemHalted, lastSequenceNumber, clearSignals } = useTradingStore();

    // Quick-switch saved sites
    const [savedSites, setSavedSites] = useState<{ url: string, label: string }[]>(() => {
        try {
            const stored = localStorage.getItem('trading_terminal_saved_sites');
            return stored ? JSON.parse(stored) : [
                { url: 'https://groww.in/charts/indices/nifty', label: 'NIFTY 50' },
                { url: 'https://groww.in/charts/indices/sensex', label: 'SENSEX' },
            ];
        } catch { return []; }
    });

    // FIX #3: Resizable sidebar
    const [sidebarWidth, setSidebarWidth] = useState(() => Number(localStorage.getItem('trading_terminal_sidebar_width')) || 420);
    const isResizing = useRef(false);

    // SCAN-LOCK: Store locked signals so we don't re-analyze until price crosses them
    const lockedSignals = useRef<{ direction: string, entry_price: number, candle_index: number }[] | null>(null);
    const lockedYMin = useRef<number>(0);
    const lockedYMax = useRef<number>(0);
    const lockedCandleCount = useRef<number>(50);

    // FALLBACK: When DOM injection fails (e.g. Groww iframe), use React overlay markers
    const [fallbackMarkers, setFallbackMarkers] = useState<{ id: string, type: 'BUY' | 'SELL', topPct: number, leftPct: number }[]>([]);

    // FIX #5: Scan status - real feedback
    const [scanStatus, setScanStatus] = useState<'idle' | 'capturing' | 'analyzing' | 'done'>('idle');
    const [lastScanTime, setLastScanTime] = useState<string>('--');
    const [scanCount, setScanCount] = useState(0);
    const [ragStats, setRagStats] = useState<{ direction: string, dominance: number, total_matches: string } | null>(null);

    // Dynamic chart scaling constraints
    const [chartYMin, setChartYMin] = useState<number>(0);
    const [chartYMax, setChartYMax] = useState<number>(100);

    // Dynamic width for scanner animation
    const [windowWidth, setWindowWidth] = useState(1200);

    useEffect(() => {
        setWindowWidth(window.innerWidth);
        const handleResize = () => setWindowWidth(window.innerWidth);
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const webviewRef = useRef<any>(null);

    // Extract a friendly label from a URL
    const getLabelFromUrl = (siteUrl: string): string => {
        try {
            const u = new URL(siteUrl);
            const path = u.pathname.replace(/\/$/, '');
            const lastSegment = path.split('/').pop() || u.hostname;
            // Clean up common patterns
            return lastSegment
                .replace(/-/g, ' ')
                .replace(/\.html?$/i, '')
                .toUpperCase()
                .substring(0, 20) || u.hostname.replace('www.', '').split('.')[0].toUpperCase();
        } catch {
            return siteUrl.substring(0, 20);
        }
    };

    const navigateToUrl = useCallback((newUrl: string) => {
        setUrl(newUrl);
        setInputUrl(newUrl);
        localStorage.setItem('trading_terminal_url', newUrl);

        // Auto-save to saved sites if not already there
        setSavedSites(prev => {
            const exists = prev.some(s => s.url === newUrl);
            if (!exists) {
                const updated = [...prev, { url: newUrl, label: getLabelFromUrl(newUrl) }];
                localStorage.setItem('trading_terminal_saved_sites', JSON.stringify(updated));
                return updated;
            }
            return prev;
        });

        // Clear all stale data when navigating to a new chart
        setSignals(null);
        setAnalysisSummary('');
        setRagStats(null);
        setRisk(null);
        clearSignals(); // Clear global store signals from previous chart
        lockedSignals.current = null; // unlock so we re-scan on new chart
        // Clear DOM-injected markers inside the webview
        if (webviewRef.current) {
            try {
                webviewRef.current.executeJavaScript(
                    `document.querySelectorAll('.ai-trade-marker').forEach(function(el) { el.remove(); });`
                );
            } catch (_e) { /* webview not ready */ }
        }
        setWebviewReady(false);
        setPageFullyLoaded(false);

        if (webviewRef.current && webviewReady) {
            // loadURL returns a Promise - must catch to prevent ERR_ABORTED crash
            try {
                const loadPromise = webviewRef.current.loadURL(newUrl);
                if (loadPromise && loadPromise.catch) {
                    loadPromise.catch((err: any) => {
                        console.warn("Webview navigation error (non-fatal):", err?.message?.substring(0, 80));
                    });
                }
            } catch (e) {
                console.warn("Failed to navigate webview:", e);
            }
        }
    }, [webviewReady]);

    const removeSavedSite = (siteUrl: string) => {
        setSavedSites(prev => {
            const updated = prev.filter(s => s.url !== siteUrl);
            localStorage.setItem('trading_terminal_saved_sites', JSON.stringify(updated));
            return updated;
        });
    };

    // Page fully loaded tracking - don't scan until chart has rendered
    const [pageFullyLoaded, setPageFullyLoaded] = useState(false);
    const pageLoadTimer = useRef<any>(null);

    // Set up webview event listeners
    useEffect(() => {
        const wv = webviewRef.current;
        if (!wv) return;

        const onDomReady = () => {
            setWebviewReady(true);
            // Sync the address bar with the actual loaded URL
            try {
                const currentUrl = wv.getURL();
                if (currentUrl) setInputUrl(currentUrl);
            } catch { }
        };

        const onFinishLoad = () => {
            // Page finished loading - wait 3 more seconds for chart to render
            if (pageLoadTimer.current) clearTimeout(pageLoadTimer.current);
            pageLoadTimer.current = setTimeout(() => {
                setPageFullyLoaded(true);
                console.log('Page fully loaded - scanning enabled');
            }, 3000);
        };

        const onNavigate = (e: any) => {
            if (e.url) setInputUrl(e.url);
            // New navigation started - clear ALL stale data immediately
            setPageFullyLoaded(false);
            setSignals(null);
            setAnalysisSummary('');
            setRagStats(null);
            setRisk(null);
            clearSignals(); // Clear global store signals from previous chart
            lockedSignals.current = null;
            setScanStatus('idle');
            setFallbackMarkers([]);
            // Clear DOM-injected markers from previous chart
            try {
                wv.executeJavaScript(
                    `document.querySelectorAll('.ai-trade-marker').forEach(function(el) { el.remove(); });`
                );
            } catch (_e) { /* webview might not be ready */ }
        };

        const onFailLoad = (e: any) => {
            console.warn('Webview failed to load:', e.errorDescription, e.validatedURL);
            setPageFullyLoaded(false);
        };

        wv.addEventListener('dom-ready', onDomReady);
        wv.addEventListener('did-finish-load', onFinishLoad);
        wv.addEventListener('did-navigate', onNavigate);
        wv.addEventListener('did-navigate-in-page', onNavigate);
        wv.addEventListener('did-fail-load', onFailLoad);

        return () => {
            wv.removeEventListener('dom-ready', onDomReady);
            wv.removeEventListener('did-finish-load', onFinishLoad);
            wv.removeEventListener('did-navigate', onNavigate);
            wv.removeEventListener('did-navigate-in-page', onNavigate);
            wv.removeEventListener('did-fail-load', onFailLoad);
            if (pageLoadTimer.current) clearTimeout(pageLoadTimer.current);
        };
    }, [loading]);

    // FIX #3: Sidebar resizing logic
    const startResizing = useCallback((e: React.MouseEvent) => {
        isResizing.current = true;
        e.preventDefault();
        const startX = e.clientX;
        const startWidth = sidebarWidth;

        const onMouseMove = (ev: MouseEvent) => {
            if (!isResizing.current) return;
            const delta = startX - ev.clientX;
            const newWidth = Math.max(300, Math.min(700, startWidth + delta));
            setSidebarWidth(newWidth);
        };

        const onMouseUp = () => {
            isResizing.current = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }, [sidebarWidth]);

    useEffect(() => {
        localStorage.setItem('trading_terminal_sidebar_width', sidebarWidth.toString());
    }, [sidebarWidth]);


    // The Vision Scanning Trigger (On-Demand & Initial Load)
    const scanChart = useCallback(async () => {
        if (!pageFullyLoaded || !webviewRef.current) return;
        if (scanStatus === 'capturing' || scanStatus === 'analyzing') return;

        try {
            // 1. Capture Screenshot via Python Backend
            setScanStatus('capturing');
            const captureRes = await fetch('http://localhost:8000/api/trading/capture_screen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            if (!captureRes.ok) throw new Error("Backend failed to capture screen");

            const captureData = await captureRes.json();
            const base64Data = captureData.image;

            if (!base64Data) throw new Error("No image data returned from backend capture.");

            // 2. Send to Vision LLM
            setScanStatus('analyzing');
            const response = await fetch('http://localhost:8000/api/trading/analyze_vision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image: base64Data,
                    url: inputUrl
                })
            });

            if (!response.ok) throw new Error("Vision API failed");
            const data = await response.json();

            // 3. Process Results
            setAnalysisSummary(data.analysis_summary || 'No clear analysis available.');
            if (data.rag_stats) {
                setRagStats(data.rag_stats);
            }
            setScanCount(prev => prev + 1);
            setLastScanTime(new Date().toLocaleTimeString());
            setScanStatus('done');

            if (data.chart_y_min && data.chart_y_max) {
                setChartYMin(data.chart_y_min);
                setChartYMax(data.chart_y_max);
            }

            // Signals are now handled entirely by the backend WebSocket broadcast

            setTimeout(() => setScanStatus('idle'), 3000);

        } catch (err) {
            console.error("Scanning Error:", err);
            setScanStatus('idle');
            setAnalysisSummary('Scan failed or timeout. Please check backend connection.');
        }
    }, [pageFullyLoaded, inputUrl, scanStatus]);

    // Initial Trigger on page load
    useEffect(() => {
        if (!pageFullyLoaded || !webviewRef.current) return;
        const initDelay = setTimeout(() => {
            scanChart();
        }, 1500);
        return () => clearTimeout(initDelay);
    }, [pageFullyLoaded]);

    useEffect(() => {
        let ws: WebSocket;
        let reconnectTimeout: NodeJS.Timeout;

        const connectWebSocket = () => {
            ws = new WebSocket('ws://localhost:8000/api/ws');

            ws.onopen = () => {
                console.log("WebSocket connected. Awaiting STATE_SNAPSHOT...");
            };

            ws.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);

                    if (payload.event === 'STATE_SNAPSHOT') {
                        useTradingStore.getState().processSnapshot(payload);
                        setLoading(false);

                        if (payload.risk_state) setRisk(payload.risk_state);

                    } else if (payload.event?.startsWith('SIGNAL_') || payload.event === 'SYSTEM_HALTED') {
                        useTradingStore.getState().processEvent(payload);

                        // Trigger UI pulse
                        setScanCount(prev => prev + 1);
                        setLastScanTime(new Date().toLocaleTimeString());
                        setScanStatus('analyzing');
                        setTimeout(() => setScanStatus('done'), 500);
                        setTimeout(() => setScanStatus('idle'), 1500);
                    }
                } catch (e) {
                    console.error("WS Parse Error", e);
                }
            };

            ws.onerror = (error) => {
                console.warn("WebSocket error:", error);
                ws.close();
            }

            ws.onclose = () => {
                console.warn("WebSocket disconnected. Retrying in 2s...");
                reconnectTimeout = setTimeout(connectWebSocket, 2000);
            };
        };

        connectWebSocket();

        return () => {
            clearTimeout(reconnectTimeout);
            if (ws) {
                ws.onclose = null; // prevent reconnect on unmount
                ws.close();
            }
        };
    }, []);

    // Handle URL form submission
    const handleNavigate = () => {
        let targetUrl = inputUrl.trim();
        if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
            targetUrl = 'https://' + targetUrl;
        }
        navigateToUrl(targetUrl);
    };

    // Scan status indicator color
    const scanColor = scanStatus === 'capturing' ? 'text-amber-400' :
        scanStatus === 'analyzing' ? 'text-purple-400' :
            scanStatus === 'done' ? 'text-emerald-400' : 'text-cyan-500/50';

    return (
        <>
            {loading && (
                <div className="fixed inset-0 z-[999999] bg-[#030d12] flex items-center justify-center">
                    <div className="text-center">
                        <div className="relative w-16 h-16 mx-auto mb-4">
                            <div className="absolute inset-0 rounded-full border-2 border-cyan-500/30 animate-ping" />
                            <div className="absolute inset-2 rounded-full border-2 border-cyan-400/60 animate-spin" />
                            <div className="absolute inset-4 rounded-full bg-cyan-500/20 flex items-center justify-center">
                                <Eye size={20} className="text-cyan-400" />
                            </div>
                        </div>
                        <div className="text-cyan-400 text-sm font-mono animate-pulse">INITIALIZING NEURAL VISION...</div>
                        <div className="text-slate-500 text-xs mt-2 font-mono">Connecting to AI Trading Engine</div>
                    </div>
                </div>
            )}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                className="fixed inset-0 z-[99999] bg-[#030d12] flex flex-col overflow-hidden text-slate-300 antialiased"
            >
                {/* IDE-style Header */}
                <div className="h-10 flex items-center justify-between px-4 bg-[#02080b] border-b border-cyan-500/20 shrink-0 select-none">
                    <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-2 mr-4 opacity-60 hover:opacity-100 transition-opacity">
                            <div className="w-3 h-3 rounded-full bg-[#ff5f56] cursor-pointer hover:bg-red-400" onClick={onClose} title="Close Terminal" />
                            <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                            <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
                        </div>
                        <h2 className="text-cyan-400 font-bold tracking-widest text-xs flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-cyan-500 animate-[pulse_2s_ease-in-out_infinite] shadow-[0_0_8px_rgba(0,255,255,0.8)]" />
                            TRADING TERMINAL PRO
                        </h2>
                    </div>

                    <div className="flex items-center space-x-4 text-xs font-mono">
                        {/* FIX #5: Real scan status */}
                        <span className={`flex items-center gap-1.5 ${scanColor} transition-colors`}>
                            <Zap size={12} className={scanStatus !== 'idle' ? 'animate-pulse' : ''} />
                            {scanStatus === 'capturing' ? 'CAPTURING...' :
                                scanStatus === 'analyzing' ? 'AI ANALYZING...' :
                                    scanStatus === 'done' ? 'SCAN COMPLETE' : 'STANDBY'}
                        </span>
                        <span className="text-slate-600">|</span>
                        <span className="text-slate-500">SCANS: {scanCount}</span>
                        <span className="text-slate-600">|</span>
                        <span className="text-slate-500">LAST: {lastScanTime}</span>
                    </div>
                </div>

                {/* Content Body - Two Columns */}
                <div className="flex-1 flex overflow-hidden">
                    {/* LEFT COLUMN - Embedded Trading Browser & Scanner */}
                    <div className="flex-1 flex flex-col relative bg-white min-w-0">
                        {/* Integrated Browser Address Bar */}
                        <div className="h-10 bg-[#02080b] flex items-center px-4 gap-3 border-b border-cyan-500/20 shrink-0">
                            <Globe size={14} className="text-cyan-500/50" />
                            <input
                                value={inputUrl}
                                onChange={(e) => setInputUrl(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleNavigate()}
                                className="flex-1 bg-transparent text-xs text-slate-300 outline-none border-none placeholder-slate-600 font-mono"
                                placeholder="Enter trading site URL..."
                            />
                            <button
                                onClick={handleNavigate}
                                className="text-cyan-500/50 hover:text-cyan-400 transition-colors"
                                title="Navigate"
                            >
                                <Search size={14} />
                            </button>
                            <button
                                onClick={() => webviewRef.current?.reload()}
                                className="text-cyan-500/50 hover:text-cyan-400 transition-colors"
                                title="Reload"
                            >
                                <RefreshCw size={12} />
                            </button>
                        </div>

                        {/* Quick-Switch Site Tabs */}
                        {savedSites.length > 0 && (
                            <div className="h-8 bg-[#020a0e] flex items-center px-2 gap-1 border-b border-cyan-500/10 shrink-0 overflow-x-auto custom-scrollbar">
                                <Bookmark size={11} className="text-cyan-500/30 mr-1 shrink-0" />
                                {savedSites.map((site) => (
                                    <div
                                        key={site.url}
                                        className={`group flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-mono cursor-pointer transition-all shrink-0 border ${url === site.url
                                            ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300 shadow-[0_0_8px_rgba(0,255,255,0.1)]'
                                            : 'bg-white/3 border-white/5 text-slate-500 hover:text-slate-300 hover:bg-white/5 hover:border-white/10'
                                            }`}
                                        onClick={() => navigateToUrl(site.url)}
                                    >
                                        <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${url === site.url ? 'bg-cyan-400' : 'bg-slate-600'}`} />
                                        {site.label}
                                        <button
                                            onClick={(e) => { e.stopPropagation(); removeSavedSite(site.url); }}
                                            className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all ml-0.5"
                                            title="Remove"
                                        >
                                            <X size={10} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Webview & Vision Scanner Container */}
                        <div className="flex-1 relative overflow-hidden bg-slate-900">
                            {/* The Actual Trading Site */}
                            <webview
                                ref={webviewRef}
                                src={url}
                                className="w-full h-full border-none"
                                title="Trading View"
                                allowpopups
                            ></webview>

                            <DebugPanel />

                            {/* Deterministic Canvas Overlay (Phase 4 Idempotency) */}
                            {pageFullyLoaded && chartYMax > chartYMin && (
                                <OverlayCanvas
                                    width={windowWidth - sidebarWidth}
                                    height={window.innerHeight - 80} // Approx deducting header
                                    visibleMinPrice={chartYMin}
                                    visibleMaxPrice={chartYMax}
                                    visibleStartIndex={0}
                                    visibleCandleCount={50}
                                    markers={Object.values(activeSignals).map(sig => ({
                                        type: sig.direction === 'LONG' ? 'BUY' : 'SELL',
                                        entry: sig.entry_price,
                                        stop: sig.stop_price,
                                        target: sig.target_price,
                                        candle_index: sig.candle_index,
                                        confidence: sig.confidence,
                                        state: sig.state,
                                        signal_id: sig.signal_id
                                    }))}
                                    riskMode={systemHalted ? 'HALTED' : 'NORMAL'}
                                />
                            )}

                            {/* AI Vision Scanner Overlay */}
                            <div className="absolute inset-0 z-10 pointer-events-none overflow-hidden">
                                {/* Scanning Sweep Animation */}
                                <motion.div
                                    className="absolute top-0 bottom-0 w-[150px] bg-gradient-to-r from-transparent via-cyan-500/5 to-cyan-500/20 border-r border-cyan-400 shadow-[2px_0_15px_rgba(0,255,255,0.4)]"
                                    animate={{ x: [-150, windowWidth] }}
                                    transition={{ repeat: Infinity, duration: 4, ease: "linear" }}
                                >
                                    <div className="absolute top-[40%] -right-4 flex items-center gap-2">
                                        <div className="w-8 h-8 rounded-full border border-cyan-400 bg-cyan-950/80 backdrop-blur-md flex items-center justify-center shadow-[0_0_15px_rgba(0,255,255,0.6)]">
                                            <Scan size={16} className="text-cyan-400 animate-pulse" />
                                        </div>
                                    </div>
                                    <div className="absolute top-[60%] -right-4 flex items-center gap-2">
                                        <div className="w-8 h-8 rounded-full border border-cyan-400 bg-cyan-950/80 backdrop-blur-md flex items-center justify-center shadow-[0_0_15px_rgba(0,255,255,0.6)] animate-pulse" style={{ animationDelay: '1s' }}>
                                            <Scan size={14} className="text-cyan-400" />
                                        </div>
                                    </div>
                                </motion.div>

                                {/* Corner Targeting Brackets */}
                                <div className="absolute top-4 left-4 w-8 h-8 border-t-2 border-l-2 border-cyan-500/30"></div>
                                <div className="absolute top-4 right-4 w-8 h-8 border-t-2 border-r-2 border-cyan-500/30"></div>
                                <div className="absolute bottom-4 left-4 w-8 h-8 border-b-2 border-l-2 border-cyan-500/30"></div>
                                <div className="absolute bottom-4 right-4 w-8 h-8 border-b-2 border-r-2 border-cyan-500/30"></div>

                                {/* FIX #5: Show REAL status indicator */}
                                <div className={`absolute top-4 left-1/2 -translate-x-1/2 backdrop-blur border px-3 py-1 rounded text-[10px] font-mono flex items-center gap-2 transition-all ${scanStatus === 'capturing' ? 'bg-amber-950/80 border-amber-500/50 text-amber-400' :
                                    scanStatus === 'analyzing' ? 'bg-purple-950/80 border-purple-500/50 text-purple-400' :
                                        scanStatus === 'done' ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-400' :
                                            'bg-cyan-950/60 border-cyan-500/30 text-cyan-400'
                                    }`}>
                                    <div className={`w-1.5 h-1.5 rounded-full ${scanStatus === 'capturing' ? 'bg-amber-400 animate-ping' :
                                        scanStatus === 'analyzing' ? 'bg-purple-400 animate-ping' :
                                            scanStatus === 'done' ? 'bg-emerald-400' :
                                                'bg-cyan-400 animate-ping'
                                        }`}></div>
                                    {scanStatus === 'capturing' ? 'CAPTURING SCREENSHOT...' :
                                        scanStatus === 'analyzing' ? 'AI PROCESSING IMAGE...' :
                                            scanStatus === 'done' ? `âœ“ SCAN #${scanCount} COMPLETE` :
                                                'AI VISION ACTIVE'}
                                </div>
                            </div>

                        </div>
                    </div>

                    {/* FIX #3: Resizable Drag Handle */}
                    <div
                        className="w-1 bg-cyan-500/10 hover:bg-cyan-500/40 cursor-col-resize transition-colors relative z-30 group flex items-center justify-center"
                        onMouseDown={startResizing}
                    >
                        <div className="absolute opacity-0 group-hover:opacity-100 transition-opacity">
                            <GripVertical size={12} className="text-cyan-400" />
                        </div>
                    </div>

                    {/* RIGHT COLUMN - AI Assistant (Resizable) */}
                    <div
                        className="bg-[#030d12]/95 backdrop-blur-xl flex flex-col overflow-y-auto custom-scrollbar shrink-0 shadow-[-10px_0_30px_rgba(0,0,0,0.8)] z-20 border-l border-cyan-500/20"
                        style={{ width: `${sidebarWidth}px` }}
                    >
                        <div className="p-5 space-y-5">
                            {/* Header */}
                            <div className="flex items-center gap-3 text-cyan-400 font-bold tracking-widest text-xs border-b border-cyan-500/30 pb-3">
                                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-cyan-500/30 to-blue-600/20 border border-cyan-500/40 flex items-center justify-center shadow-[0_0_12px_rgba(0,255,255,0.2)]">
                                    <Cpu size={14} className="text-cyan-400" />
                                </div>
                                NEURAL TRADING ASSISTANT
                                <div className="ml-auto flex items-center gap-3">
                                    <button
                                        onClick={scanChart}
                                        disabled={scanStatus === 'capturing' || scanStatus === 'analyzing' || !pageFullyLoaded}
                                        className="bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 px-2 py-1 rounded transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title="Manually trigger AI Vision Analysis"
                                    >
                                        <Scan size={12} />
                                        <span>ANALYZE</span>
                                    </button>
                                    <div className="flex items-center gap-1.5">
                                        <div className={`w-1.5 h-1.5 rounded-full ${scanStatus !== 'idle' ? 'bg-emerald-400 animate-pulse' : 'bg-cyan-500/30'}`} />
                                        <span className="text-[9px] text-slate-500 font-mono">
                                            {scanStatus !== 'idle' ? 'LIVE' : 'READY'}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* AI Reasoning Readout */}
                            <div className="bg-gradient-to-br from-[#040e14] to-[#061218] border border-cyan-500/20 rounded-xl p-4 shadow-[inset_0_1px_0_rgba(0,255,255,0.1)] relative overflow-hidden">
                                <div className="absolute top-0 right-0 w-40 h-40 bg-cyan-500/5 rounded-full blur-[60px] -mr-10 -mt-10" />
                                <div className="absolute bottom-0 left-0 w-24 h-24 bg-blue-500/5 rounded-full blur-[40px] -ml-8 -mb-8" />

                                <div className="text-cyan-500 font-bold mb-2 flex items-center gap-2 text-[11px]">
                                    <Eye size={13} className={scanStatus === 'analyzing' ? 'animate-spin' : ''} />
                                    LIVE ANALYSIS
                                    {scanStatus === 'analyzing' && (
                                        <span className="ml-auto text-[9px] text-purple-400 animate-pulse font-mono">PROCESSING...</span>
                                    )}
                                </div>
                                <div className="font-mono text-[11px] leading-relaxed text-cyan-50/80 relative z-10">
                                    {!pageFullyLoaded
                                        ? <span className="text-cyan-400/60 animate-pulse">Loading new chart... waiting for AI scan</span>
                                        : analysisSummary || 'Waiting for first chart scan...'}
                                </div>
                            </div>

                            {/* FAISS RAG Edge Readout */}
                            {ragStats && (
                                <div className="bg-[#030d12] border border-cyan-500/30 rounded-xl p-3 shadow-[0_0_15px_rgba(0,255,255,0.05)] relative overflow-hidden">
                                    <div className="text-cyan-400 font-bold mb-2 flex items-center justify-between text-[11px] tracking-wider">
                                        <div className="flex items-center gap-1.5">
                                            <Bookmark size={12} className="text-cyan-500" />
                                            COMPARATIVE RAG EDGE
                                        </div>
                                        <span className="bg-cyan-500/10 text-cyan-300 px-1.5 py-0.5 rounded text-[9px]">
                                            FAISS INDEX
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 mt-2">
                                        <div className="bg-slate-900/50 rounded flex flex-col items-center justify-center p-2 border border-white/5">
                                            <span className="text-slate-500 text-[9px] mb-1">HISTORICAL EDGE</span>
                                            <span className={`text-[12px] font-bold ${ragStats.direction === 'UPWARD' ? 'text-emerald-400' : ragStats.direction === 'DOWNWARD' ? 'text-red-400' : 'text-slate-300'}`}>
                                                {ragStats.direction}
                                            </span>
                                        </div>
                                        <div className="bg-slate-900/50 rounded flex flex-col items-center justify-center p-2 border border-white/5">
                                            <span className="text-slate-500 text-[9px] mb-1">PROBABILITY</span>
                                            <span className="text-cyan-300 text-[12px] font-bold font-mono">
                                                {ragStats.dominance.toFixed(1)}%
                                            </span>
                                        </div>
                                    </div>
                                    <div className="mt-2 text-[9px] text-slate-500 text-center font-mono uppercase">
                                        Compared vs {ragStats.total_matches} historical charts
                                    </div>
                                </div>
                            )}



                            {/* Risk & Regime */}
                            {risk && <RiskMeters data={risk} />}

                            {/* Active Signals - Always visible, shows loading when empty */}
                            <ActiveSignals data={Object.values(activeSignals)} refreshData={() => { }} />

                            {/* Real Terminal Log */}
                            <div className="border border-cyan-500/15 rounded-xl p-3 bg-black/50 font-mono text-[9px] text-slate-500 space-y-1 shadow-[inset_0_0_15px_rgba(0,0,0,0.6)]">
                                <div className="text-cyan-500/40">&gt; NEURAL_VISION v2.0 INITIALIZED</div>
                                <div className={scanStatus === 'capturing' ? 'text-amber-400' : 'text-slate-600'}>
                                    &gt; {scanStatus === 'capturing' ? '[*] CAPTURING HD SCREENSHOT...' : 'capture: standby'}
                                </div>
                                <div className={scanStatus === 'analyzing' ? 'text-purple-400 animate-pulse' : 'text-slate-600'}>
                                    &gt; {scanStatus === 'analyzing' ? '[AI] LLM ANALYZING PATTERNS...' : 'analysis: idle'}
                                </div>
                                <div className={scanStatus === 'done' ? 'text-emerald-400' : 'text-slate-600'}>
                                    &gt; {scanStatus === 'done' ? `[OK] SCAN #${scanCount} DELIVERED` : `total_scans: ${scanCount}`}
                                </div>
                                <div className="text-slate-600">&gt; last_scan: {lastScanTime}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </motion.div>
        </>
    );
}
