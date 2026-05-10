"""
Standalone Entry Point for Autonomous Trading.
Bootstraps the Trading Loop outside of the main agent for isolated, headless operation.
"""
import os
import sys
import time
import logging

# Configure logging for console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s'
)

# Ensure trading package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.trading.autonomous_loop import AutonomousTradingLoop

if __name__ == "__main__":
    logger = logging.getLogger("TradingBotMain")
    
    # Ensure environment flag is set to enable the loop
    os.environ["TRADING_ENABLED"] = "true"
    
    logger.info("Starting Headless Autonomous Trading Bot...")
    try:
        loop = AutonomousTradingLoop()
        loop.start()
        
        # Keep main thread alive
        while True:
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Interrupt received, shutting down...")
        if 'loop' in locals():
            loop.stop()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
