from pyatrea.registers import REGISTERS, RegisterDef, modbus_ranges, by_role


def test_register_defs_well_formed():
    for rid, d in REGISTERS.items():
        assert isinstance(d, RegisterDef)
        assert rid[0] in "IHCD"
        assert d.kind in ("input", "holding", "coil", "discrete")
        assert d.coef > 0


def test_known_registers_present():
    for rid in ("H10705", "H10706", "H10704", "H10714", "H10715", "H10716",
                "H10707", "H10717", "H10700", "H10712",
                "I10211", "I10212", "I10213", "I10214", "I10215", "I11420",
                "I00020", "I00021", "I00022", "I10007", "I10008", "I10009",
                "H10520", "H10521", "H10522", "H12300", "H12309",
                "H13500", "H13502", "D11183", "D11122", "I12004", "H11700"):
        assert rid in REGISTERS


def test_control_registers_are_read_side_metadata():
    # controls describe READ-side state; writes go to proven write targets
    # (H10708/H10709/H10710) handled by CommandBuilder, not via write_id.
    assert REGISTERS["H10704"].role == "control"
    assert REGISTERS["H10705"].role == "control"
    assert REGISTERS["H10706"].role == "control"
    assert REGISTERS["H10706"].coef == 10  # temp ×10


def test_warning_alert_roles_populated():
    # params.xml has 27 flag=W and 53 flag=A — all must be present with roles
    assert len(by_role("warning")) == 27
    assert len(by_role("alert")) == 53


def test_temperatures_have_coef_10():
    for rid in ("I10211", "I10212", "I10213", "I10214", "I10215", "I11420"):
        assert REGISTERS[rid].coef == 10


def test_entity_read_registers_present():
    for rid in ("C10215", "C10216", "D10200", "D10201", "D10202", "D10203", "I10005"):
        assert rid in REGISTERS


def test_modbus_ranges_groups_contiguous():
    ranges = modbus_ranges()
    assert all(len(r) == 3 and r[0] in ("input", "holding", "coil", "discrete") for r in ranges)
    assert any(k == "input" for k, _s, _c in ranges)
