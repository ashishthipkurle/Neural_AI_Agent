from agent.safety.destructive_pipeline import DestructiveActionPipeline


def test_destructive_action_requires_override():
    pipeline = DestructiveActionPipeline()
    denied = pipeline.evaluate("delete all files", explicit_override=False)
    assert denied.allowed is False

    allowed = pipeline.evaluate("delete all files", explicit_override=True)
    assert allowed.allowed is True
