from agent.core.intent import IntentParser
from agent.skills.planning.skill import PlanningSkill
from agent.skills.coding.skill import CodingSkill


def test_research_markdown_telegram_routes_to_mission_and_noncoding_steps():
    prompt = (
        "Research the top 5 AI startups in India in 2026, create a markdown report, "
        "save it in generated/ai_startups.md, and send the file to me via Telegram."
    )

    intents = IntentParser({}).parse(prompt)
    assert intents
    assert intents[0].action == "start_mission"

    planner = PlanningSkill()
    steps = planner._decompose_goal(prompt, {})

    assert len(steps) >= 2
    assert steps[0].skill == "research"
    assert steps[0].action == "deep_research"
    assert steps[0].params.get("output_path") == "generated/ai_startups.md"

    assert any(s.skill == "telegram" and s.action == "send_document" for s in steps)
    assert all(s.skill != "coding" for s in steps)


def test_paraphrased_prompt_routes_semantically_to_mission():
    prompt = (
        "Please investigate leading AI startups in India for 2026, prepare a markdown summary "
        "in generated/ai_startups.md, and share the document on Telegram."
    )
    intents = IntentParser({}).parse(prompt)
    assert intents
    assert intents[0].action == "start_mission"
    assert intents[0].parameters.get("semantic_hints", {}).get("output_path") == "generated/ai_startups.md"


def test_natural_sentence_without_exact_keywords_still_avoids_coding_route():
    prompt = (
        "Find the best 5 AI companies in India this year, write a report file, "
        "save it as generated/ai_startups.md and send it to me on telegram"
    )
    planner = PlanningSkill()
    steps = planner._decompose_goal(prompt, {})
    assert steps
    assert steps[0].skill == "research"
    assert any(s.skill == "telegram" and s.action == "send_document" for s in steps)
    assert all(s.skill != "coding" for s in steps)


def test_screenshot_currently_open_app_routes_to_screen_analysis_intents():
    prompt = "Take a screenshot and tell me what application is currently open."
    intents = IntentParser({}).parse(prompt)

    assert intents
    assert len(intents) >= 2
    assert intents[0].action == "capture_screen"
    assert intents[1].action == "describe_image"
    assert intents[1].parameters.get("use_last_capture") is True


def test_ordered_web_workflow_routes_to_mission_with_structure():
    prompt = 'Go to google.com, search for "AI regulation India 2026", open first 3 results, summarize them.'
    intents = IntentParser({}).parse(prompt)

    assert intents
    assert intents[0].action == "start_mission"
    workflow = intents[0].parameters.get("ordered_web_workflow", {})
    assert workflow.get("site") == "google.com"
    assert workflow.get("query") == "AI regulation India 2026"
    assert workflow.get("result_count") == 3


def test_arrow_news_workflow_routes_to_mission_and_noncoding_steps():
    prompt = "Search news → summarize → save file → send telegram"
    intents = IntentParser({}).parse(prompt)

    assert intents
    assert intents[0].action == "start_mission"
    workflow = intents[0].parameters.get("news_summary_workflow", {})
    assert workflow.get("query") == "latest news"
    assert workflow.get("output_path") == "generated/news_summary.md"

    planner = PlanningSkill()
    steps = planner._decompose_goal(prompt, {})

    assert len(steps) >= 2
    assert steps[0].skill == "research"
    assert steps[0].action == "deep_research"
    assert steps[0].params.get("query") == "latest news"
    assert steps[0].params.get("output_path") == "generated/news_summary.md"
    assert any(s.skill == "telegram" and s.action == "send_document" for s in steps)
    assert all(s.skill != "coding" for s in steps)


def test_startup_build_research_screenshot_telegram_routes_to_ordered_mission_steps():
    prompt = (
        "Build a landing page for a startup called NovaEdge AI, research competitors, generate content, "
        "create React project, install dependencies, run it, take screenshot of running site, and send everything via Telegram."
    )
    intents = IntentParser({}).parse(prompt)

    assert intents
    assert intents[0].action == "start_mission"
    workflow = intents[0].parameters.get("startup_build_workflow", {})
    assert workflow.get("startup_name") == "NovaEdge AI"
    assert workflow.get("project_name") == "novaedge_ai"

    planner = PlanningSkill()
    steps = planner._decompose_goal(prompt, {})

    assert len(steps) >= 5
    assert steps[0].skill == "coding"
    assert steps[0].action == "scaffold_react_website"
    assert steps[1].skill == "research"
    assert steps[1].action == "deep_research"
    assert steps[2].skill == "vision"
    assert steps[2].action == "screenshot"
    assert any(s.skill == "telegram" and s.action == "send_document" for s in steps)


def test_startup_name_preserved_in_normalized_mission_goal():
    normalized_goal = (
        "Build a landing page for NovaEdge AI, research competitors, generate content, "
        "create React project, install dependencies, run it, take screenshot, and send all artifacts via Telegram."
    )
    planner = PlanningSkill()
    steps = planner._decompose_goal(normalized_goal, {})

    assert steps
    assert "NovaEdge AI" in steps[0].description
    assert steps[0].params.get("project_name") == "novaedge_ai"
    assert steps[1].params.get("output_path") == "generated/novaedge_ai_competitors.md"
    assert steps[2].params.get("path") == "generated/novaedge_ai_site.png"
    assert any(
        s.skill == "telegram" and s.action == "send_document" and "novaedge_ai" in s.params.get("path", "")
        for s in steps
    )


def test_ai_startup_gets_ai_content_not_medical():
    """NovaEdge AI should get AI-themed content, not medical equipment."""
    skill = CodingSkill()
    btype = skill._detect_business_type("NovaEdge AI")
    assert btype == "ai", f"Expected 'ai' type for NovaEdge AI, got '{btype}'"

    content = skill._get_content_preset("NovaEdge AI", btype)
    assert "AI" in content["eyebrow"] or "ai" in content["eyebrow"].lower()
    # Products should be AI-related, not medical
    product_names = [p["name"] for p in content["products"]]
    assert not any("BP Monitor" in n or "Pulse Oximeter" in n for n in product_names), \
        f"AI startup got medical products: {product_names}"
    assert any("Predictive" in n or "NLP" in n or "Vision" in n or "Copilot" in n for n in product_names)


def test_health_startup_gets_health_content():
    """Health-related names should get medical content."""
    skill = CodingSkill()
    btype = skill._detect_business_type("MedCare Solutions")
    assert btype == "health"

    content = skill._get_content_preset("MedCare Solutions", btype)
    product_names = [p["name"] for p in content["products"]]
    assert any("Monitor" in n or "ECG" in n or "Oximeter" in n for n in product_names)


def test_generic_startup_defaults_to_tech():
    """A generic name should default to tech type."""
    skill = CodingSkill()
    btype = skill._detect_business_type("Fusion Labs")
    assert btype == "tech"


def test_content_preset_has_business_name_in_tagline():
    """Content should reference the actual business name."""
    skill = CodingSkill()
    content = skill._get_content_preset("NovaEdge AI", "ai")
    assert "NovaEdge AI" in content["tagline"]
    assert "NovaEdge AI" in content["about"]


# ---- Browser crash recovery tests ----
import asyncio
import pytest


def test_browser_skill_has_crash_recovery_methods():
    """Browser skill should expose _is_page_alive, _recover_browser, _recycle_page."""
    from agent.skills.browser.skill import AdvancedBrowserSkill
    skill = AdvancedBrowserSkill({"browser": {"headless": True}})
    assert hasattr(skill, "_is_page_alive")
    assert hasattr(skill, "_recover_browser")
    assert hasattr(skill, "_recycle_page")
    assert asyncio.iscoroutinefunction(skill._is_page_alive)
    assert asyncio.iscoroutinefunction(skill._recover_browser)
    assert asyncio.iscoroutinefunction(skill._recycle_page)


def test_browser_recycle_page_action_accepted():
    """execute('recycle_page', {}) should be handled without error."""
    from agent.skills.browser.skill import AdvancedBrowserSkill
    skill = AdvancedBrowserSkill({"browser": {"headless": True}})
    # With no browser running, recycle_page should still succeed gracefully
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(skill.execute("recycle_page", {}))
    loop.close()
    assert result.success


def test_mission_restores_dev_url_before_screenshot():
    """MissionControlSkill should store _mission_dev_url and pre-navigate for screenshot."""
    # This is a unit-level check that the attribute mechanism works
    from agent.skills.mission.skill import MissionControlSkill
    import inspect
    source = inspect.getsource(MissionControlSkill._start_mission)
    # Verify the dev-URL restore block exists
    assert "_mission_dev_url" in source
    assert "vision" in source and "screenshot" in source
    assert "Restoring dev server" in source
