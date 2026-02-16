import yaml

from agent.core.intent import IntentParser


def test_chatgpt_report_to_telegram_routes_to_mission():
    cfg = yaml.safe_load(open("agent/config/settings.yaml", "r", encoding="utf-8"))
    parser = IntentParser(cfg)

    text = "go to chatgpt and chat with him about electric cars for 1 min and send the report on telegram"
    intents = parser.parse(text)

    assert intents, "Expected at least one intent"
    assert intents[0].action == "start_mission"
    assert intents[0].tool_name == "start_mission"
    assert intents[0].parameters.get("goal")
