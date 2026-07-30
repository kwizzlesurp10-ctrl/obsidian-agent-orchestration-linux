import os

from obsidian_orchestration.vault_adapter import InMemoryVault, ObsidianTunnelVault, get_default_vault


def test_inmemory_roundtrip():
    v = InMemoryVault()
    v.write("a/b.md", "hello")
    assert v.read("a/b.md") == "hello"
    assert v.search("hello")[0]["path"] == "a/b.md"


def test_get_default_vault_memory():
    os.environ.pop("OBSIDIAN_API_KEY", None)
    os.environ.pop("OBSIDIAN_USE_LIVE", None)
    v = get_default_vault()
    assert isinstance(v, InMemoryVault)


def test_obsidian_tunnel_vault_constructs():
    v = ObsidianTunnelVault(base_url="https://127.0.0.1:27124", api_key="test")
    assert v.base_url.endswith("27124")
