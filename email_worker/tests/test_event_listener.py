from types import SimpleNamespace

from email_worker.notifications import event_listener


def test_redirect_for_real_delivery_returns_original_when_unconfigured(monkeypatch):
    monkeypatch.setattr(
        event_listener,
        "settings",
        SimpleNamespace(email_test_redirect_base=""),
    )

    assert event_listener._redirect_for_real_delivery("user@example.com") == "user@example.com"


def test_redirect_for_real_delivery_rewrites_placeholder_sps_com(monkeypatch):
    monkeypatch.setattr(
        event_listener,
        "settings",
        SimpleNamespace(email_test_redirect_base="tester@example.net"),
    )

    assert event_listener._redirect_for_real_delivery("intern@sps.com") == "tester+intern@example.net"


def test_redirect_for_real_delivery_leaves_real_domains_untouched(monkeypatch):
    monkeypatch.setattr(
        event_listener,
        "settings",
        SimpleNamespace(email_test_redirect_base="tester@example.net"),
    )

    assert event_listener._redirect_for_real_delivery("requester@acme.org") == "requester@acme.org"


def test_redirect_for_real_delivery_ignores_empty_or_malformed_base(monkeypatch):
    monkeypatch.setattr(
        event_listener,
        "settings",
        SimpleNamespace(email_test_redirect_base="not-an-email"),
    )

    assert event_listener._redirect_for_real_delivery("intern@sps.com") == "intern@sps.com"