"""Tests for Channels Redis configuration (Railway WebSocket timeouts)."""

from config.redis_channels import build_channels_redis_hosts, build_channels_redis_layer_config


def test_build_channels_redis_hosts_uses_full_url_and_timeouts():
    hosts = build_channels_redis_hosts(
        "redis://:secret@redis.railway.internal:6379/0",
        socket_connect_timeout=20.0,
        socket_timeout=25.0,
    )
    assert len(hosts) == 1
    assert hosts[0]["address"] == "redis://:secret@redis.railway.internal:6379/0"
    assert hosts[0]["socket_connect_timeout"] == 20.0
    assert hosts[0]["socket_timeout"] == 25.0
    assert hosts[0]["retry_on_timeout"] is True
    assert "ssl_cert_reqs" not in hosts[0]


def test_build_channels_redis_hosts_rediss_sets_ssl_cert_reqs():
    hosts = build_channels_redis_hosts("rediss://user:pass@host.example.com:6380/1")
    assert hosts[0]["address"].startswith("rediss://")
    assert hosts[0]["ssl_cert_reqs"] is None


def test_build_channels_redis_layer_config_capacity_defaults():
    config = build_channels_redis_layer_config("redis://localhost:6379/0")
    assert config["capacity"] == 1500
    assert config["expiry"] == 60
    assert config["group_expiry"] == 86400
    assert len(config["hosts"]) == 1
