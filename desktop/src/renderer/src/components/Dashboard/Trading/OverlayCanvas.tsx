import React, { useRef, useEffect, useCallback, useMemo, useState } from 'react';

interface OverlayMarker {
    type: 'BUY' | 'SELL';
    entry: number;
    stop: number;
    target: number;
    candle_index: number;
    confidence: number;
    state: string;
    signal_id?: string;
}

interface OverlayProps {
    width: number;
    height: number;
    visibleMinPrice: number;
    visibleMaxPrice: number;
    visibleStartIndex: number;
    visibleCandleCount: number;
    markers: OverlayMarker[];
    regime?: string;
    riskMode?: string;
}

/**
 * User-adjustable Canvas Overlay with draggable edge handles.
 * 
 * The canvas itself is ALWAYS pointer-events:none so the website below
 * stays fully interactive. Only the 4 small drag handles + calibrate
 * button capture mouse events.
 */
const OverlayCanvas: React.FC<OverlayProps> = ({
    width,
    height,
    visibleMinPrice,
    visibleMaxPrice,
    visibleStartIndex,
    visibleCandleCount,
    markers,
    regime = 'QUIET',
    riskMode = 'NORMAL',
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // ── User-adjustable chart region (percentage 0-100) ──────────
    const [chartLeft, setChartLeft] = useState(() =>
        Number(localStorage.getItem('overlay_chart_left') || '3')
    );
    const [chartRight, setChartRight] = useState(() =>
        Number(localStorage.getItem('overlay_chart_right') || '55')
    );
    const [chartTop, setChartTop] = useState(() =>
        Number(localStorage.getItem('overlay_chart_top') || '12')
    );
    const [chartBottom, setChartBottom] = useState(() =>
        Number(localStorage.getItem('overlay_chart_bottom') || '92')
    );

    const [showHandles, setShowHandles] = useState(false);

    // Persist on change
    useEffect(() => {
        localStorage.setItem('overlay_chart_left', String(chartLeft));
        localStorage.setItem('overlay_chart_right', String(chartRight));
        localStorage.setItem('overlay_chart_top', String(chartTop));
        localStorage.setItem('overlay_chart_bottom', String(chartBottom));
    }, [chartLeft, chartRight, chartTop, chartBottom]);

    // Pixel values
    const region = useMemo(() => ({
        x: (chartLeft / 100) * width,
        y: (chartTop / 100) * height,
        w: ((chartRight - chartLeft) / 100) * width,
        h: ((chartBottom - chartTop) / 100) * height,
    }), [chartLeft, chartRight, chartTop, chartBottom, width, height]);

    // ── Safe bounds fallback ─────────────────────────────────────
    const { safeMin, safeMax } = useMemo(() => {
        let min = visibleMinPrice;
        let max = visibleMaxPrice;
        if (min === 0 && max === 100 && markers.length > 0) {
            let actualMin = Infinity;
            let actualMax = -Infinity;
            markers.forEach(m => {
                actualMin = Math.min(actualMin, m.entry, m.stop > 0 ? m.stop : Infinity, m.target > 0 ? m.target : Infinity);
                actualMax = Math.max(actualMax, m.entry, m.stop, m.target);
            });
            if (actualMin !== Infinity && actualMax !== -Infinity) {
                const padding = (actualMax - actualMin) * 0.2 || actualMin * 0.05;
                min = Math.max(0, actualMin - padding);
                max = actualMax + padding;
            }
        }
        return { safeMin: min, safeMax: max };
    }, [visibleMinPrice, visibleMaxPrice, markers]);

    // ── Price → Y (within chart region) ──────────────────────────
    const priceToY = useCallback(
        (price: number): number => {
            const range = safeMax - safeMin;
            if (range <= 0) return region.y + region.h / 2;
            const normalized = (price - safeMin) / range;
            const y = region.y + region.h - normalized * region.h;
            return Math.max(region.y, Math.min(region.y + region.h, y));
        },
        [region, safeMin, safeMax]
    );

    // ── Draw canvas ──────────────────────────────────────────────
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, width, height);

        if (riskMode === 'HALTED') {
            ctx.fillStyle = 'rgba(255, 0, 0, 0.08)';
            ctx.fillRect(region.x, region.y, region.w, region.h);
            ctx.font = 'bold 14px monospace';
            ctx.fillStyle = 'rgba(255, 50, 50, 0.6)';
            ctx.textAlign = 'center';
            ctx.fillText('⚠ RISK HALTED', region.x + region.w / 2, region.y + 24);
        }

        // Draw markers
        markers.forEach((marker) => {
            const entryY = priceToY(marker.entry);
            const stopY = priceToY(marker.stop);
            const targetY = priceToY(marker.target);
            const isBuy = marker.type === 'BUY';
            const isTerminal = ['TARGET_HIT', 'STOP_HIT', 'INVALIDATED', 'CLOSED'].includes(marker.state);
            const isLocked = marker.state === 'LOCKED';
            ctx.globalAlpha = isTerminal ? 0.35 : (isLocked ? 0.6 : 1.0);

            const lx = region.x;
            const rx = region.x + region.w;

            // Entry Line
            ctx.beginPath();
            ctx.strokeStyle = isBuy ? '#00E676' : '#FF5252';
            ctx.lineWidth = 2;
            ctx.setLineDash([8, 5]);
            ctx.moveTo(lx, entryY);
            ctx.lineTo(rx, entryY);
            ctx.stroke();
            ctx.setLineDash([]);

            // Stop Line
            if (marker.stop > 0) {
                ctx.beginPath();
                ctx.strokeStyle = 'rgba(255, 50, 50, 0.4)';
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 6]);
                ctx.moveTo(lx, stopY);
                ctx.lineTo(rx, stopY);
                ctx.stroke();
                ctx.setLineDash([]);
            }

            // Target Line
            if (marker.target > 0) {
                ctx.beginPath();
                ctx.strokeStyle = 'rgba(50, 255, 100, 0.4)';
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 6]);
                ctx.moveTo(lx, targetY);
                ctx.lineTo(rx, targetY);
                ctx.stroke();
                ctx.setLineDash([]);
            }

            // Stop band
            if (marker.stop > 0) {
                ctx.fillStyle = 'rgba(255, 50, 50, 0.05)';
                const t = Math.min(entryY, stopY);
                ctx.fillRect(lx, t, rx - lx, Math.abs(stopY - entryY));
            }

            // Target band
            if (marker.target > 0) {
                ctx.fillStyle = 'rgba(50, 255, 100, 0.05)';
                const t = Math.min(entryY, targetY);
                ctx.fillRect(lx, t, rx - lx, Math.abs(targetY - entryY));
            }

            // Arrow + type label
            const arrowX = rx - 25;
            const arrowSize = 8;
            ctx.fillStyle = isBuy ? '#00E676' : '#FF5252';
            ctx.beginPath();
            if (isBuy) {
                ctx.moveTo(arrowX, entryY - arrowSize - 2);
                ctx.lineTo(arrowX - arrowSize / 2, entryY - 2);
                ctx.lineTo(arrowX + arrowSize / 2, entryY - 2);
            } else {
                ctx.moveTo(arrowX, entryY + arrowSize + 2);
                ctx.lineTo(arrowX - arrowSize / 2, entryY + 2);
                ctx.lineTo(arrowX + arrowSize / 2, entryY + 2);
            }
            ctx.closePath();
            ctx.fill();

            ctx.font = 'bold 12px monospace';
            ctx.textAlign = 'center';
            ctx.shadowColor = 'rgba(0,0,0,0.8)';
            ctx.shadowBlur = 4;
            ctx.fillText(marker.type, arrowX, isBuy ? entryY - arrowSize - 8 : entryY + arrowSize + 14);
            ctx.shadowBlur = 0;

            // Price labels — bold and high-contrast
            ctx.font = 'bold 11px monospace';
            ctx.textAlign = 'right';
            ctx.shadowColor = 'rgba(0,0,0,0.9)';
            ctx.shadowBlur = 3;

            ctx.fillStyle = isBuy ? '#00E676' : '#FF5252';
            ctx.fillText(`ENTRY ${marker.entry.toFixed(2)}`, rx - 5, entryY - 6);
            if (marker.stop > 0) {
                ctx.fillStyle = '#FF5252';
                ctx.fillText(`STOP ${marker.stop.toFixed(2)}`, rx - 5, stopY - 6);
            }
            if (marker.target > 0) {
                ctx.fillStyle = '#00E676';
                ctx.fillText(`TARGET ${marker.target.toFixed(2)}`, rx - 5, targetY - 6);
            }
            ctx.shadowBlur = 0;

            if (isLocked) {
                ctx.font = 'bold 11px monospace';
                ctx.fillStyle = '#FFA726';
                ctx.textAlign = 'center';
                ctx.shadowColor = 'rgba(0,0,0,0.9)';
                ctx.shadowBlur = 4;
                ctx.fillText('LOCKED', arrowX, entryY + (isBuy ? -24 : 26));
                ctx.shadowBlur = 0;
            }
            ctx.globalAlpha = 1.0;
        });

        // Calibration border
        if (showHandles) {
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(0, 200, 255, 0.5)';
            ctx.lineWidth = 1;
            ctx.strokeRect(region.x, region.y, region.w, region.h);
            ctx.setLineDash([]);
        }

        if (regime !== 'QUIET') {
            ctx.font = '9px monospace';
            ctx.fillStyle = 'rgba(255, 255, 255, 0.25)';
            ctx.textAlign = 'right';
            ctx.fillText(`REGIME: ${regime}`, region.x + region.w - 4, region.y + region.h - 4);
        }
    }, [width, height, markers, regime, riskMode, priceToY, region, showHandles]);

    // ── Drag handle component ────────────────────────────────────
    const DragHandle = ({ edge, pixelX, pixelY }: { edge: 'left' | 'right' | 'top' | 'bottom'; pixelX: number; pixelY: number }) => {
        const isHorizontal = edge === 'left' || edge === 'right';
        const label = edge[0].toUpperCase();

        const onMouseDown = (e: React.MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();

            const onMove = (ev: MouseEvent) => {
                const container = canvasRef.current?.parentElement;
                if (!container) return;
                const rect = container.getBoundingClientRect();
                const mx = ev.clientX - rect.left;
                const my = ev.clientY - rect.top;
                const pctX = Math.max(0, Math.min(100, (mx / width) * 100));
                const pctY = Math.max(0, Math.min(100, (my / height) * 100));

                switch (edge) {
                    case 'left': if (pctX < chartRight - 5) setChartLeft(Math.round(pctX)); break;
                    case 'right': if (pctX > chartLeft + 5) setChartRight(Math.round(pctX)); break;
                    case 'top': if (pctY < chartBottom - 5) setChartTop(Math.round(pctY)); break;
                    case 'bottom': if (pctY > chartTop + 5) setChartBottom(Math.round(pctY)); break;
                }
            };

            const onUp = () => {
                window.removeEventListener('mousemove', onMove);
                window.removeEventListener('mouseup', onUp);
            };

            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
        };

        return (
            <div
                onMouseDown={onMouseDown}
                style={{
                    position: 'absolute',
                    left: pixelX - 10,
                    top: pixelY - 10,
                    width: 20,
                    height: 20,
                    background: 'rgba(0, 200, 255, 0.8)',
                    border: '2px solid #00e5ff',
                    borderRadius: 3,
                    cursor: isHorizontal ? 'ew-resize' : 'ns-resize',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 9,
                    fontWeight: 'bold',
                    fontFamily: 'monospace',
                    color: '#000',
                    zIndex: 30,
                    pointerEvents: 'auto',
                    userSelect: 'none',
                    boxShadow: '0 0 8px rgba(0,200,255,0.5)',
                }}
                title={`Drag to adjust ${edge} edge`}
            >
                {label}
            </div>
        );
    };

    return (
        <div style={{ position: 'absolute', top: 0, left: 0, width, height, pointerEvents: 'none', zIndex: 20 }}>
            {/* Canvas — ALWAYS pointer-events:none, never blocks the website */}
            <canvas
                ref={canvasRef}
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: `${width}px`,
                    height: `${height}px`,
                    pointerEvents: 'none',
                }}
            />

            {/* Calibrate button — only this tiny button captures clicks */}
            <button
                onClick={() => setShowHandles(!showHandles)}
                style={{
                    position: 'absolute',
                    top: 6,
                    right: 6,
                    zIndex: 25,
                    background: showHandles ? 'rgba(0, 200, 255, 0.3)' : 'rgba(0, 0, 0, 0.4)',
                    border: `1px solid ${showHandles ? 'rgba(0, 200, 255, 0.6)' : 'rgba(255, 255, 255, 0.15)'}`,
                    color: showHandles ? '#00e5ff' : 'rgba(255, 255, 255, 0.4)',
                    padding: '3px 8px',
                    borderRadius: 4,
                    fontSize: 9,
                    fontFamily: 'monospace',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    backdropFilter: 'blur(4px)',
                    letterSpacing: 1,
                    pointerEvents: 'auto',
                }}
                title="Toggle chart region calibration. Drag L/R/T/B handles to match your chart."
            >
                {showHandles ? '✓ DONE' : '⊞ CALIBRATE'}
            </button>

            {/* Drag handles — only visible when calibrating, only these capture mouse */}
            {showHandles && (
                <>
                    <DragHandle edge="left" pixelX={region.x} pixelY={region.y + region.h / 2} />
                    <DragHandle edge="right" pixelX={region.x + region.w} pixelY={region.y + region.h / 2} />
                    <DragHandle edge="top" pixelX={region.x + region.w / 2} pixelY={region.y} />
                    <DragHandle edge="bottom" pixelX={region.x + region.w / 2} pixelY={region.y + region.h} />
                </>
            )}
        </div>
    );
};

export default OverlayCanvas;
