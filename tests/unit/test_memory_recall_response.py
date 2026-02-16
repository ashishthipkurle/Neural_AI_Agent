from agent.skills.memory.skill import MemorySkill


def test_recall_returns_memory_content_for_single_match():
    skill = MemorySkill()
    skill._vector_store = None
    skill._memories = [
        {
            "id": 1,
            "content": "User's company name is Quantum Forge Labs.",
            "tags": ["company", "profile"],
            "category": "general",
        }
    ]

    result = skill._action_recall({"query": "What is my company name?", "limit": 5}, {})

    assert result.success is True
    assert "Quantum Forge Labs" in result.message
    assert result.data["count"] == 1


def test_recall_returns_not_found_message_when_empty():
    skill = MemorySkill()
    skill._vector_store = None
    skill._memories = []

    result = skill._action_recall({"query": "What is my company name?", "limit": 5}, {})

    assert result.success is True
    assert result.data["count"] == 0
    assert "couldn't find" in result.message.lower()
