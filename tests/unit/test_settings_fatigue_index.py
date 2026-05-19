from driver_fatigue.config.settings import AppSettings


def test_default_fatigue_index_enabled():
    s = AppSettings()
    assert s.fatigue_index.enabled is True


def test_fatigue_index_can_be_disabled_via_yaml(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("fatigue_index:\n  enabled: false\n")
    s = AppSettings.from_yaml(cfg)
    assert s.fatigue_index.enabled is False
