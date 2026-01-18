from executable_organs import ExecutableOrganRegistry


def test_math_organ_basic():
    registry = ExecutableOrganRegistry()
    result, organ_id, record_id = registry.process_command("2 + 2")
    assert "4" in result
    assert organ_id == "math_organ"
