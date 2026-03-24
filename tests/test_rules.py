from jellyfin_strm.rules import RuleSet


def test_rules_identify_known_sidecars() -> None:
    rules = RuleSet.default()

    assert rules.is_video("movie.mp4") is True
    assert rules.is_video("movie.txt") is False
    assert rules.is_sidecar_file("movie.nfo") is True
    assert rules.is_sidecar_file("poster.jpg") is True
    assert rules.is_sidecar_file("movie-fanart.png") is True
    assert rules.should_copy_directory("extrafanart") is True
    assert rules.should_skip_directory("@eaDir") is True
