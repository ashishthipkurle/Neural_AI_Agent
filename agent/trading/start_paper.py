"""
Paper Trading Launcher -- Start the autonomous trading loop in paper mode.

Usage:
    python -m agent.trading.start_paper
    python -m agent.trading.start_paper --symbols SPY,QQQ,AAPL
    python -m agent.trading.start_paper --demo  (30s cycles for live demos)

This script:
1. Starts the FastAPI server on port 8000
2. Launches the autonomous trading loop in paper mode
3. Opens the dashboard WebSocket for real-time updates
4. Runs until Ctrl+C
"""
import os
import sys
import argparse
import logging
import threading
import signal

# Ensure UTF-8 on Windows
if os.name == "nt":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Start paper trading")
    parser.add_argument(
        "--symbols",
        type=str,
        default="SPY,QQQ,AAPL,MSFT,TSLA",
        help="Comma-separated symbols to trade (default: SPY,QQQ,AAPL,MSFT,TSLA)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10000,
        help="Initial paper capital (default: $10,000)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port (default: 8000)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Demo mode: 30s cycles instead of candle-aligned (for live demos only)",
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Skip starting the API server (useful if already running)",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join("agent_data", "paper_trading.log"),
                encoding="utf-8",
            ),
        ],
    )
    logger = logging.getLogger("PaperTrading")

    symbols = [s.strip() for s in args.symbols.split(",")]
    logger.info("=" * 60)
    logger.info("PAPER TRADING LAUNCHER")
    logger.info("=" * 60)
    logger.info(f"  Symbols:  {symbols}")
    logger.info(f"  Capital:  ${args.capital:,.2f}")
    logger.info(f"  Demo:     {args.demo}")
    logger.info(f"  Port:     {args.port}")
    logger.info("=" * 60)

    # Ensure agent_data directory exists
    os.makedirs("agent_data", exist_ok=True)

    # Start the autonomous trading loop
    from agent.trading.autonomous_loop import AutonomousTradingLoop

    config = {
        "mode": "paper",
        "market": "USA",
        "symbols": symbols,
        "initial_capital": args.capital,
        "demo_mode": args.demo,
        "strategies_enabled": [
            "trend_following",
            "mean_reversion",
            "breakout",
            "faiss_pattern",
        ],
    }

    loop = AutonomousTradingLoop(config)

    # Graceful shutdown handler
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received...")
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not args.no_server:
        # Start FastAPI server in a background thread
        def run_server():
            import uvicorn
            from agent.api_server import app

            uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        logger.info(f"API server started on http://localhost:{args.port}")
        logger.info(f"Dashboard WS: ws://localhost:{args.port}/api/trading/ws")

    # Start the trading loop (blocks until shutdown)
    logger.info("Starting autonomous trading loop...")
    loop.start()

    # Keep main thread alive
    try:
        loop._thread.join()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — shutting down...")
        loop.stop()


if __name__ == "__main__":
    main()
