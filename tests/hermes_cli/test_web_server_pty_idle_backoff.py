from hermes_cli import web_server


def test_pty_idle_backoff_returns_positive_bounded_delays():
    backoff = web_server._PtyIdleBackoff(initial=0.01, maximum=0.04)

    assert backoff.next_delay() == 0.01
    assert backoff.next_delay() == 0.02
    assert backoff.next_delay() == 0.04
    assert backoff.next_delay() == 0.04


def test_pty_idle_backoff_reset_restores_initial_delay():
    backoff = web_server._PtyIdleBackoff(initial=0.01, maximum=0.04)

    assert backoff.next_delay() == 0.01
    assert backoff.next_delay() == 0.02
    backoff.reset()

    assert backoff.next_delay() == 0.01


def test_pty_idle_backoff_rejects_non_positive_values():
    for kwargs in ({"initial": 0, "maximum": 0.04}, {"initial": 0.01, "maximum": 0}):
        try:
            web_server._PtyIdleBackoff(**kwargs)
        except ValueError as exc:
            assert "positive" in str(exc)
        else:  # pragma: no cover - assertion branch
            raise AssertionError(f"accepted invalid backoff values: {kwargs}")
