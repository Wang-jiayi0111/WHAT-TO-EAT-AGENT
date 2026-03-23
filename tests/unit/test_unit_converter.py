import pytest
from src.libs.utils.unit_converter import UnitConverter

def test_normalize():
    assert UnitConverter.normalize(1, "kg") == 1000
    assert UnitConverter.normalize(500, "g") == 500
    assert UnitConverter.normalize(1000, "mg") == 1
    assert UnitConverter.normalize(1, "lb") == pytest.approx(453.592, rel=1e-3)
    assert UnitConverter.normalize(1, "oz") == pytest.approx(28.3495, rel=1e-3)

def test_convert():
    assert UnitConverter.convert(1, "kg", "g") == 1000
    assert UnitConverter.convert(1000, "g", "kg") == 1
    assert UnitConverter.convert(1, "lb", "kg") == pytest.approx(0.453592, rel=1e-3)
    assert UnitConverter.convert(16, "oz", "lb") == pytest.approx(1, rel=1e-3)

def test_unsupported_unit():
    with pytest.raises(ValueError):
        UnitConverter.normalize(1, "unsupported_unit")
    with pytest.raises(ValueError):
        UnitConverter.convert(1, "g", "unsupported_unit")