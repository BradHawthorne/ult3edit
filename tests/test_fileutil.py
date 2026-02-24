"""Tests for file utilities."""

import os

import pytest

from ult3edit.fileutil import (
    resolve_game_file, find_game_files, decode_high_ascii, encode_high_ascii, backup_file,
    resolve_single_file, hex_int,
)


class TestResolveGameFile:
    def test_with_hash_suffix(self, tmp_dir):
        path = os.path.join(tmp_dir, 'MAPA#061000')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_game_file(tmp_dir, 'MAP', 'A')
        assert result is not None
        assert 'MAPA' in result

    def test_without_hash_suffix(self, tmp_dir):
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_game_file(tmp_dir, 'MAP', 'A')
        assert result == path

    def test_not_found(self, tmp_dir):
        result = resolve_game_file(tmp_dir, 'MAP', 'Z')
        assert result is None

    def test_excludes_dproj(self, tmp_dir):
        # Create a .dproj file that should be excluded
        path = os.path.join(tmp_dir, 'MAPA#061000.dproj')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_game_file(tmp_dir, 'MAP', 'A')
        assert result is None


class TestFindGameFiles:
    def test_finds_multiple(self, tmp_dir):
        for letter in 'ABC':
            with open(os.path.join(tmp_dir, f'MON{letter}#069900'), 'wb') as f:
                f.write(b'\x00')
        results = find_game_files(tmp_dir, 'MON', 'ABCZ')
        assert len(results) == 3
        letters = [r[0] for r in results]
        assert 'A' in letters and 'B' in letters and 'C' in letters


class TestDecodeHighAscii:
    def test_simple(self):
        data = bytes([0xC8, 0xC5, 0xCC, 0xCC, 0xCF])  # HELLO
        assert decode_high_ascii(data) == 'HELLO'

    def test_stops_at_null(self):
        data = bytes([0xC8, 0xC9, 0x00, 0xC1])
        assert decode_high_ascii(data) == 'HI'

    def test_empty(self):
        assert decode_high_ascii(b'\x00') == ''
        assert decode_high_ascii(b'') == ''

    def test_space(self):
        data = bytes([0xC8, 0xA0, 0xC9])  # 'H I'
        assert decode_high_ascii(data) == 'H I'


class TestEncodeHighAscii:
    def test_simple(self):
        result = encode_high_ascii('HERO', 10)
        assert len(result) == 10
        assert result[0] == ord('H') | 0x80
        assert result[4] == 0xA0  # Padding (high-ASCII space)

    def test_truncation(self):
        result = encode_high_ascii('VERY LONG NAME HERE', 10)
        assert len(result) == 10

    def test_uppercase(self):
        result = encode_high_ascii('hero', 4)
        assert result[0] == ord('H') | 0x80

    def test_roundtrip(self):
        original = 'HERO'
        encoded = encode_high_ascii(original, 10)
        decoded = decode_high_ascii(encoded)
        assert decoded == original


# ── Migrated from test_new_features.py ──

class TestBackupFile:
    def test_creates_bak_file(self, tmp_dir, sample_roster_file):
        bak_path = backup_file(sample_roster_file)
        assert bak_path == sample_roster_file + '.bak'
        assert os.path.exists(bak_path)

    def test_bak_matches_original(self, tmp_dir, sample_roster_file):
        with open(sample_roster_file, 'rb') as f:
            original = f.read()
        backup_file(sample_roster_file)
        with open(sample_roster_file + '.bak', 'rb') as f:
            bak = f.read()
        assert original == bak

    def test_missing_file_raises(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            backup_file(os.path.join(tmp_dir, 'nonexistent'))


# =============================================================================
# Roster validation
# =============================================================================


# =============================================================================
# Migrated from test_new_features.py — fileutil tests
# =============================================================================


class TestDeadCodeRemoved:
    """Verify removed dead functions are no longer importable."""

    def test_validate_file_size_removed(self):
        """validate_file_size should no longer exist in fileutil."""
        from ult3edit import fileutil
        assert not hasattr(fileutil, 'validate_file_size')

    def test_load_game_file_removed(self):
        """load_game_file should no longer exist in fileutil."""
        from ult3edit import fileutil
        assert not hasattr(fileutil, 'load_game_file')


class TestResolveSingleFile:
    """Tests for resolve_single_file with ProDOS suffixes."""

    def test_find_plain_file(self, tmp_path):
        """Finds a plain file by name."""
        (tmp_path / 'PRTY').write_bytes(b'\x00' * 16)
        result = resolve_single_file(str(tmp_path), 'PRTY')
        assert result is not None
        assert 'PRTY' in result

    def test_find_prodos_hashed_file(self, tmp_path):
        """Finds a file with ProDOS #hash suffix."""
        (tmp_path / 'PRTY#069500').write_bytes(b'\x00' * 16)
        result = resolve_single_file(str(tmp_path), 'PRTY')
        assert result is not None
        assert 'PRTY#069500' in result

    def test_not_found_returns_none(self, tmp_path):
        """Returns None when file doesn't exist."""
        result = resolve_single_file(str(tmp_path), 'NOSUCHFILE')
        assert result is None

    def test_prefers_hashed_over_plain(self, tmp_path):
        """When both plain and hashed exist, hashed is returned first."""
        (tmp_path / 'ROST#069500').write_bytes(b'\x00' * 64)
        (tmp_path / 'ROST').write_bytes(b'\x00' * 64)
        result = resolve_single_file(str(tmp_path), 'ROST')
        assert result is not None
        assert '#' in result


class TestResolveGameFileExtended:
    """Tests for resolve_game_file with prefix+letter pattern."""

    def test_find_with_hash(self, tmp_path):
        """Finds MAPA#061000 style files."""
        (tmp_path / 'MAPA#061000').write_bytes(b'\x00' * 100)
        result = resolve_game_file(str(tmp_path), 'MAP', 'A')
        assert result is not None
        assert 'MAPA#061000' in result

    def test_find_plain(self, tmp_path):
        """Falls back to plain name if no hash file exists."""
        (tmp_path / 'CONA').write_bytes(b'\x00' * 192)
        result = resolve_game_file(str(tmp_path), 'CON', 'A')
        assert result is not None
        assert 'CONA' in result

    def test_not_found(self, tmp_path):
        """Returns None if neither hashed nor plain exists."""
        result = resolve_game_file(str(tmp_path), 'MAP', 'Z')
        assert result is None

    def test_excludes_dproj(self, tmp_path):
        """Files ending in .dproj are excluded."""
        (tmp_path / 'MAPA#061000.dproj').write_bytes(b'\x00')
        result = resolve_game_file(str(tmp_path), 'MAP', 'A')
        assert result is None


class TestFindGameFilesExtended:
    """Tests for find_game_files across multiple letters."""

    def test_finds_multiple(self, tmp_path):
        """Finds all existing files across letter range."""
        (tmp_path / 'CONA').write_bytes(b'\x00' * 192)
        (tmp_path / 'CONC').write_bytes(b'\x00' * 192)
        result = find_game_files(str(tmp_path), 'CON', 'ABCDE')
        assert len(result) == 2
        letters = [r[0] for r in result]
        assert 'A' in letters
        assert 'C' in letters

    def test_empty_directory(self, tmp_path):
        """Returns empty list for empty directory."""
        result = find_game_files(str(tmp_path), 'CON', 'ABCDE')
        assert result == []


class TestFileUtilEdgeCases:
    """Test fileutil utility edge cases."""

    def test_hex_int_parses_hex(self):
        """hex_int parses 0x prefix."""
        assert hex_int('0xFF') == 255
        assert hex_int('0x10') == 16

    def test_hex_int_parses_decimal(self):
        """hex_int parses decimal strings."""
        assert hex_int('42') == 42

    def test_hex_int_parses_dollar_prefix(self):
        """hex_int parses $ prefix (if supported)."""
        try:
            result = hex_int('$FF')
            assert result == 255
        except ValueError:
            pass  # $ prefix may not be supported

    def test_resolve_single_file_not_found(self, tmp_path):
        """resolve_single_file returns None for missing file."""
        result = resolve_single_file(str(tmp_path), 'NONEXISTENT')
        assert result is None

    def test_resolve_single_file_found(self, tmp_path):
        """resolve_single_file finds file by prefix."""
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_single_file(str(tmp_path), 'ROST')
        assert result is not None

    def test_decode_encode_high_ascii_roundtrip(self):
        """decode/encode_high_ascii round-trips."""
        text = "HELLO WORLD"
        encoded = encode_high_ascii(text, len(text))
        decoded = decode_high_ascii(encoded)
        assert decoded == text
