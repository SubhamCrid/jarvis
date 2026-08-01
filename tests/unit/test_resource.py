"""
Unit tests for jarvis.resource platform.
"""

import pytest
from jarvis.resource import (
    Resource,
    ResourceType,
    ResourcePermission,
    ActionDescriptor,
    ResourceURI,
    generate_file_actions,
)


def test_resource_instantiation():
    action = ActionDescriptor(
        name="open",
        label="Open File",
        capability_name="tools",
        required_permissions=[ResourcePermission.READ],
    )
    res = Resource(
        id="res-001",
        type=ResourceType.FILE,
        title="test_file.txt",
        uri="file:///C:/test_file.txt",
        metadata={"size": 1024},
        provider="everything",
        actions=[action],
        permissions=[ResourcePermission.READ, ResourcePermission.WRITE],
    )

    assert res.id == "res-001"
    assert res.type == ResourceType.FILE
    assert res.title == "test_file.txt"
    assert res.uri == "file:///C:/test_file.txt"
    assert res.provider == "everything"
    assert len(res.actions) == 1
    assert res.actions[0].name == "open"


def test_resource_uri_parsing():
    uri = ResourceURI.parse("file:///C:/documents/resume.pdf")
    assert uri.scheme == "file"
    assert "resume.pdf" in uri.path

    app_uri = ResourceURI.parse("app://vscode")
    assert app_uri.scheme == "app"
    assert app_uri.path == "vscode"

    mem_uri = ResourceURI.parse("memory://user_profile/fact-123")
    assert mem_uri.scheme == "memory"


def test_resource_uri_builders():
    assert ResourceURI.create_file_uri("C:/test.txt").startswith("file://")
    assert ResourceURI.create_app_uri("spotify") == "app://spotify"
    assert "search://" in ResourceURI.create_search_uri("python")


def test_generate_file_actions():
    actions = generate_file_actions(
        file_path="C:/test.txt",
        permissions=[ResourcePermission.READ, ResourcePermission.DELETE],
    )
    action_names = [a.name for a in actions]
    assert "open" in action_names
    assert "reveal" in action_names
    assert "copy_path" in action_names
    assert "delete" in action_names
