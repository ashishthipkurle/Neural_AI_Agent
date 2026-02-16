from agent.skills.planning.skill import PlanningSkill


def _actions(steps):
    return [(s.skill, s.action) for s in steps]


def test_chat_with_chatgpt_routes_to_browser_chat_loop():
    skill = PlanningSkill()
    goal = "go to chatgpt and chat with him about electric cars for 1 min and send the report on telegram"
    steps = skill._decompose_goal(goal, context={})

    actions = _actions(steps)
    assert ("browser", "navigate") in actions
    assert ("browser", "browser_chat_loop") in actions


def test_talk_to_chatgpt_routes_to_browser_chat_loop():
    skill = PlanningSkill()
    goal = "go to chatgpt and talk to him about import export business for 1 min"
    steps = skill._decompose_goal(goal, context={})

    actions = _actions(steps)
    assert ("browser", "navigate") in actions
    assert ("browser", "browser_chat_loop") in actions
