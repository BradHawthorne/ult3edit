"""Tests for BCD encode/decode."""

from ult3edit.bcd import bcd_to_int, bcd16_to_int, int_to_bcd, int_to_bcd16, is_valid_bcd


class TestBcdToInt:
    def test_zero(self):
        assert bcd_to_int(0x00) == 0

    def test_simple(self):
        assert bcd_to_int(0x25) == 25

    def test_max(self):
        assert bcd_to_int(0x99) == 99

    def test_tens_only(self):
        assert bcd_to_int(0x50) == 50

    def test_ones_only(self):
        assert bcd_to_int(0x07) == 7


    def test_invalid_nibble_produces_value(self):
        """Invalid BCD bytes (nibble > 9) still decode without crashing."""
        assert bcd_to_int(0xAB) == 111  # (10*10 + 11)
        assert bcd_to_int(0xFF) == 165  # (15*10 + 15)


class TestBcd16ToInt:
    def test_zero(self):
        assert bcd16_to_int(0x00, 0x00) == 0

    def test_simple(self):
        assert bcd16_to_int(0x01, 0x50) == 150

    def test_max(self):
        assert bcd16_to_int(0x99, 0x99) == 9999

    def test_hundreds_only(self):
        assert bcd16_to_int(0x05, 0x00) == 500


class TestIntToBcd:
    def test_zero(self):
        assert int_to_bcd(0) == 0x00

    def test_simple(self):
        assert int_to_bcd(25) == 0x25

    def test_max(self):
        assert int_to_bcd(99) == 0x99

    def test_clamp_high(self):
        assert int_to_bcd(150) == 0x99

    def test_clamp_low(self):
        assert int_to_bcd(-5) == 0x00


class TestIntToBcd16:
    def test_zero(self):
        assert int_to_bcd16(0) == (0x00, 0x00)

    def test_simple(self):
        assert int_to_bcd16(150) == (0x01, 0x50)

    def test_max(self):
        assert int_to_bcd16(9999) == (0x99, 0x99)

    def test_clamp_high(self):
        assert int_to_bcd16(20000) == (0x99, 0x99)

    def test_clamp_low(self):
        assert int_to_bcd16(-1) == (0x00, 0x00)


class TestRoundTrips:
    def test_single_roundtrip(self):
        for val in range(100):
            assert bcd_to_int(int_to_bcd(val)) == val

    def test_double_roundtrip(self):
        for val in [0, 1, 99, 100, 500, 1234, 9999]:
            hi, lo = int_to_bcd16(val)
            assert bcd16_to_int(hi, lo) == val


class TestIsValidBcd:
    def test_valid(self):
        assert is_valid_bcd(0x00)
        assert is_valid_bcd(0x99)
        assert is_valid_bcd(0x42)

    def test_invalid_low(self):
        assert not is_valid_bcd(0x0A)
        assert not is_valid_bcd(0x0F)

    def test_invalid_high(self):
        assert not is_valid_bcd(0xA0)
        assert not is_valid_bcd(0xF0)

    def test_invalid_both(self):
        assert not is_valid_bcd(0xFF)


# ── Migrated from test_new_features.py ──

class TestBcdEdgeCases:
    """Tests for BCD encoding edge cases."""

    def test_bcd_to_int_invalid_nibble(self):
        """bcd_to_int(0xFF) returns 165 (15*10 + 15) — undocumented but stable."""
        from ult3edit.bcd import bcd_to_int
        # 0xFF has nibbles F(15) and F(15): 15*10 + 15 = 165
        assert bcd_to_int(0xFF) == 165
        # 0xAB has nibbles A(10) and B(11): 10*10 + 11 = 111
        assert bcd_to_int(0xAB) == 111

    def test_bcd16_max_value(self):
        """bcd16_to_int(0x99, 0x99) returns 9999."""
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x99, 0x99) == 9999

    def test_int_to_bcd_negative_clamps(self):
        """int_to_bcd(-5) clamps to 0."""
        from ult3edit.bcd import int_to_bcd
        assert int_to_bcd(-5) == 0x00

    def test_int_to_bcd16_negative_clamps(self):
        """int_to_bcd16(-100) clamps to (0, 0)."""
        from ult3edit.bcd import int_to_bcd16
        assert int_to_bcd16(-100) == (0x00, 0x00)

    def test_int_to_bcd16_overflow_clamps(self):
        """int_to_bcd16(10000) clamps to 9999."""
        from ult3edit.bcd import int_to_bcd16
        assert int_to_bcd16(10000) == (0x99, 0x99)

    def test_bcd_roundtrip_all_valid(self):
        """Every value 0-99 round-trips through int_to_bcd→bcd_to_int."""
        from ult3edit.bcd import bcd_to_int, int_to_bcd
        for val in range(100):
            assert bcd_to_int(int_to_bcd(val)) == val


# =============================================================================
# Roster check_progress (endgame readiness)
# =============================================================================


class TestBcdEdgeCasesExtended:
    """Test BCD encoding edge cases."""

    def test_bcd_to_int_invalid_nibble(self):
        """bcd_to_int with value > 0x99 returns clamped result."""
        from ult3edit.bcd import bcd_to_int
        # 0xFF has nibbles F,F which are invalid BCD
        result = bcd_to_int(0xFF)
        # Implementation-dependent, but should not crash
        assert isinstance(result, int)

    def test_int_to_bcd_overflow(self):
        """int_to_bcd clamps values > 99."""
        from ult3edit.bcd import int_to_bcd
        result = int_to_bcd(150)
        assert result == 0x99  # Clamped to max

    def test_int_to_bcd_negative(self):
        """int_to_bcd clamps negative values to 0."""
        from ult3edit.bcd import int_to_bcd
        result = int_to_bcd(-5)
        assert result == 0x00

    def test_int_to_bcd16_overflow(self):
        """int_to_bcd16 clamps values > 9999."""
        from ult3edit.bcd import int_to_bcd16
        hi, lo = int_to_bcd16(12345)
        assert hi == 0x99 and lo == 0x99  # Clamped to 9999

    def test_int_to_bcd16_negative(self):
        """int_to_bcd16 clamps negative values to 0."""
        from ult3edit.bcd import int_to_bcd16
        hi, lo = int_to_bcd16(-100)
        assert hi == 0x00 and lo == 0x00


class TestBcdIsValidBcd:
    """Test is_valid_bcd function."""

    def test_valid_bcd_bytes(self):
        from ult3edit.bcd import is_valid_bcd
        assert is_valid_bcd(0x00)
        assert is_valid_bcd(0x99)
        assert is_valid_bcd(0x42)

    def test_invalid_high_nibble(self):
        from ult3edit.bcd import is_valid_bcd
        assert not is_valid_bcd(0xA0)
        assert not is_valid_bcd(0xF5)

    def test_invalid_low_nibble(self):
        from ult3edit.bcd import is_valid_bcd
        assert not is_valid_bcd(0x0A)
        assert not is_valid_bcd(0x1F)

    def test_both_nibbles_invalid(self):
        from ult3edit.bcd import is_valid_bcd
        assert not is_valid_bcd(0xFF)


class TestBcd16Docstring:
    """Test bcd16_to_int decodes correctly (verifying fixed docstring)."""

    def test_bcd16_1234(self):
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x12, 0x34) == 1234

    def test_bcd16_9999(self):
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x99, 0x99) == 9999

    def test_bcd16_0100(self):
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x01, 0x00) == 100


# ============================================================================
# Batch 11: Remaining gap coverage
# ============================================================================

