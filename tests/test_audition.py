"""Playback control: replay and A/B are what judging a seam actually needs."""

from pathlib import Path

from dancelab.cli import audition as A


class _FakeProc:
    def __init__(self):
        self.terminated = False
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self.terminated = True
        self._alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self._alive = False


def _fake_spawn(monkeypatch):
    """Record what would have been played, without making a sound."""
    played: list[tuple[Path, int]] = []

    def spawn(path, repeats):
        played.append((Path(path), repeats))
        return _FakeProc()

    monkeypatch.setattr(A, "_spawn", spawn)
    return played


def _wav(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"RIFF....WAVE")
    return p


def test_playing_a_second_file_remembers_the_first(tmp_path, monkeypatch):
    played = _fake_spawn(monkeypatch)
    a, b = _wav(tmp_path, "a.wav"), _wav(tmp_path, "b.wav")
    au = A.Audition()
    au.play(a)
    au.play(b)
    assert au.current == b and au.previous == a
    assert [p for p, _ in played] == [a, b]


def test_back_toggles_between_the_two_auditions(tmp_path, monkeypatch):
    _fake_spawn(monkeypatch)
    a, b = _wav(tmp_path, "a.wav"), _wav(tmp_path, "b.wav")
    au = A.Audition()
    au.play(a)
    au.play(b)
    au.back()
    assert au.current == a          # back to the first
    au.back()
    assert au.current == b          # and forward again: A, B, A, B
    au.back()
    assert au.current == a


def test_back_does_nothing_when_there_is_no_previous(tmp_path, monkeypatch):
    _fake_spawn(monkeypatch)
    au = A.Audition()
    assert au.back() is False
    au.play(_wav(tmp_path, "a.wav"))
    assert au.back() is False       # one audition is not a comparison


def test_replay_repeats_the_same_file(tmp_path, monkeypatch):
    played = _fake_spawn(monkeypatch)
    a = _wav(tmp_path, "a.wav")
    au = A.Audition()
    au.play(a)
    au.replay(repeats=4)
    assert played == [(a, 1), (a, 4)]
    assert au.previous is None      # replaying is not a new comparison


def test_starting_a_new_file_stops_the_old_one(tmp_path, monkeypatch):
    _fake_spawn(monkeypatch)
    au = A.Audition()
    au.play(_wav(tmp_path, "a.wav"))
    first = au._process
    au.play(_wav(tmp_path, "b.wav"))
    assert first.terminated, "the previous audition kept playing over the new one"


def test_a_missing_file_is_refused_without_disturbing_playback(tmp_path, monkeypatch):
    _fake_spawn(monkeypatch)
    a = _wav(tmp_path, "a.wav")
    au = A.Audition()
    au.play(a)
    assert au.play(tmp_path / "nope.wav") is False
    assert au.current == a
