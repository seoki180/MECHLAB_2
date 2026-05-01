from .base import LegacyScriptParser


class InfineonParser(LegacyScriptParser):
    maker = "infineon"
    model = "default"
    script_name = "infineon.py"
    input_folder = "infineon"
    legacy_output_csv = "infineon_output.csv"
