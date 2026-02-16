import os

from agent.tools.os_tools import OSTools
from agent.core.intent import IntentParser


def test_delete_path_removes_directory(tmp_path):
    workspace = tmp_path / "agent_test_workspace"
    workspace.mkdir()
    status_file = workspace / "status.txt"
    status_file.write_text("pipeline working", encoding="utf-8")

    tools = OSTools()
    tools.permissions.is_path_allowed = lambda path: True
    tools.permissions.request_permission = lambda description: True

    result = tools.delete_path(str(workspace), recursive=True)

    assert "Successfully deleted directory" in result
    assert not workspace.exists()


def test_delete_path_removes_file(tmp_path):
    status_file = tmp_path / "status.txt"
    status_file.write_text("pipeline working", encoding="utf-8")

    tools = OSTools()
    tools.permissions.is_path_allowed = lambda path: True
    tools.permissions.request_permission = lambda description: True

    result = tools.delete_path(str(status_file), recursive=True)

    assert "Successfully deleted file" in result
    assert not status_file.exists()


def test_intent_parser_routes_delete_folder_command():
    parser = IntentParser(config={})
    intents = parser.parse("Delete the folder agent_test_workspace completely.")

    assert intents
    assert intents[0].tool_name == "delete_path"
    assert intents[0].parameters["path"] == "agent_test_workspace"
    assert intents[0].parameters["recursive"] is True
