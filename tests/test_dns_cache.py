"""Tests for DNS cache, including partition support."""

import json

from mail_sovereignty.dns_cache import DnsCache


class TestDnsCachePartition:
    def test_default_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mail_sovereignty.dns_cache.CACHE_DIR", tmp_path)
        cache = DnsCache("EE")
        assert cache.path == tmp_path / "ee.json"
        assert cache.partition is None

    def test_partition_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mail_sovereignty.dns_cache.CACHE_DIR", tmp_path)
        cache = DnsCache("DE", partition="09")
        assert cache.path == tmp_path / "de_09.json"
        assert cache.partition == "09"

    def test_partition_save_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mail_sovereignty.dns_cache.CACHE_DIR", tmp_path)
        cache = DnsCache("DE", partition="01")
        cache.set_domain("flensburg.de", {"mx": ["mx.flensburg.de"], "spf": ""})
        cache.save()

        assert (tmp_path / "de_01.json").exists()
        data = json.loads((tmp_path / "de_01.json").read_text())
        assert "flensburg.de" in data

        # Reload and verify
        cache2 = DnsCache("DE", partition="01")
        result = cache2.get_domain("flensburg.de")
        assert result is not None
        assert result["mx"] == ["mx.flensburg.de"]

    def test_partitions_are_independent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mail_sovereignty.dns_cache.CACHE_DIR", tmp_path)

        cache01 = DnsCache("DE", partition="01")
        cache01.set_domain("flensburg.de", {"mx": ["mx1"]})
        cache01.save()

        cache09 = DnsCache("DE", partition="09")
        cache09.set_domain("muenchen.de", {"mx": ["mx2"]})
        cache09.save()

        assert cache01.get_domain("muenchen.de") is None
        assert cache09.get_domain("flensburg.de") is None

    def test_save_log_shows_partition(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("mail_sovereignty.dns_cache.CACHE_DIR", tmp_path)
        cache = DnsCache("DE", partition="09")
        cache.set_domain("test.de", {"mx": []})
        # Force a miss then hit so stats are nonzero
        cache.get_domain("nonexistent.de")  # miss
        cache.get_domain("test.de")  # hit
        cache.save()
        captured = capsys.readouterr()
        assert "DE:09" in captured.out
