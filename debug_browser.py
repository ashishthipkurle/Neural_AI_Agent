
import asyncio
import os
import logging
import sys

# Windows Loop Policy (Essential for Playwright)
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.insert(0, ".")

from agent.skills.browser.skill import AdvancedBrowserSkill

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugBrowser")

async def test_browser():
    logger.info("Initializing Browser Skill...")
    config = {
        'browser': {
            'headless': False,
            'stealth': True
        }
    }
    skill = AdvancedBrowserSkill(config)
    
    logger.info("Starting Browser (on_start)...")
    await skill.on_start()
    
    if skill.health().value != "ready":
        logger.error(f"Browser failed to start. Health: {skill.health().value}")
        return

    logger.info("Browser Started! Navigating to Google...")
    try:
        result = await skill.execute("browse", {"url": "https://www.google.com"})
        logger.info(f"Navigation Result: {result}")
        
        logger.info("Waiting 5 seconds for visual confirmation...")
        await asyncio.sleep(5)
        
        logger.info("Closing...")
        await skill.on_unload()
    except Exception as e:
        logger.error(f"Execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_browser())
