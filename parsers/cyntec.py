from .base import LegacyScriptParser


class CyntecParser(LegacyScriptParser):
    maker = "cyntec"
    model = "default"
    script_name = "cyntec.py"
    input_folder = "CYNTEC"
    legacy_output_csv = "cyntec_output.csv"
