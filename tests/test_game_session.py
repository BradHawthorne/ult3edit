"""Tests for GameSession catalog scanning (no disk image needed)."""

import os
import pytest

from u3edit.tui.game_session import GameSession


@pytest.fixture
def mock_session(tmp_dir):
    """Create a GameSession with a mock tmpdir containing fake extracted files."""
    session = GameSession.__new__(GameSession)
    session.image_path = 'fake.po'
    session.catalog = {}

    # Create a mock DiskContext with a tmpdir
    class MockCtx:
        def __init__(self, tmpdir):
            self._tmpdir = tmpdir
            self._cache = {}
            self._modified = {}

        def read(self, name):
            for f in os.listdir(self._tmpdir):
                if f.split('#')[0].upper() == name.upper():
                    fpath = os.path.join(self._tmpdir, f)
                    with open(fpath, 'rb') as fp:
                        return fp.read()
            return None

        def write(self, name, data):
            self._modified[name] = data

    # Create fake game files in tmpdir
    files = {
        'MAPA#061000': 4096,   # Overworld
        'MAPB#061000': 2048,   # Lord British Castle
        'MAPM#061000': 2048,   # Dungeon of Fire
        'CONA#069900': 192,    # Combat: Lord British
        'CONG#069900': 192,    # Combat: Grassland
        'BRND#060000': 128,    # Brand Shrine
        'FNTN#060000': 128,    # Fountains
        'TLKA#060800': 1024,   # Dialog: LB Castle
        'TLKD#060800': 1024,   # Dialog: Dawn
        'TEXT#060800': 1024,   # Game text
        'ROST#069500': 1280,   # Roster
        'MONA#069900': 256,    # Bestiary: Grassland
        'MONZ#069900': 256,    # Bestiary: Boss
        'PRTY#060000': 16,     # Party state
    }
    for fname, size in files.items():
        path = os.path.join(tmp_dir, fname)
        with open(path, 'wb') as f:
            f.write(bytes(size))

    session.ctx = MockCtx(tmp_dir)
    session._scan_catalog()
    return session


class TestCatalogScanning:
    def test_maps_detected(self, mock_session):
        assert mock_session.has_category('maps')
        names = [n for n, _ in mock_session.files_in('maps')]
        assert 'MAPA' in names
        assert 'MAPB' in names
        assert 'MAPM' in names

    def test_combat_detected(self, mock_session):
        assert mock_session.has_category('combat')
        names = [n for n, _ in mock_session.files_in('combat')]
        assert 'CONA' in names
        assert 'CONG' in names

    def test_special_detected(self, mock_session):
        assert mock_session.has_category('special')
        names = [n for n, _ in mock_session.files_in('special')]
        assert 'BRND' in names
        assert 'FNTN' in names
        # SHRN and TIME not in mock, so shouldn't appear
        assert 'SHRN' not in names

    def test_dialog_detected(self, mock_session):
        assert mock_session.has_category('dialog')
        names = [n for n, _ in mock_session.files_in('dialog')]
        assert 'TLKA' in names
        assert 'TLKD' in names

    def test_text_detected(self, mock_session):
        assert mock_session.has_category('text')
        assert mock_session.files_in('text') == [('TEXT', 'Game Text')]

    def test_roster_detected(self, mock_session):
        assert mock_session.has_category('roster')
        assert mock_session.files_in('roster') == [('ROST', 'Character Roster')]

    def test_bestiary_detected(self, mock_session):
        assert mock_session.has_category('bestiary')
        names = [n for n, _ in mock_session.files_in('bestiary')]
        assert 'MONA' in names
        assert 'MONZ' in names

    def test_party_detected(self, mock_session):
        assert mock_session.has_category('party')
        assert mock_session.files_in('party') == [('PRTY', 'Party State')]

    def test_missing_category(self, mock_session):
        assert not mock_session.has_category('nonexistent')
        assert mock_session.files_in('nonexistent') == []

    def test_display_names(self, mock_session):
        maps = dict(mock_session.files_in('maps'))
        assert maps['MAPA'] == 'Sosaria (Overworld)'
        assert maps['MAPB'] == 'Lord British Castle'
        assert maps['MAPM'] == 'Dungeon of Fire'


class TestReadWrite:
    def test_read_file(self, mock_session):
        data = mock_session.read('ROST')
        assert data is not None
        assert len(data) == 1280

    def test_read_missing(self, mock_session):
        data = mock_session.read('NONEXIST')
        assert data is None

    def test_save_callback(self, mock_session):
        cb = mock_session.make_save_callback('MAPA')
        cb(b'\x01\x02\x03')
        assert mock_session.ctx._modified['MAPA'] == b'\x01\x02\x03'
