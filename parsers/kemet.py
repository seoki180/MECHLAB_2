from .base import LegacyScriptParser


class KemetParser(LegacyScriptParser):
    maker = "kemet"
    model = "default"
    script_name = "kemet.py"
    input_folder = "kemet"
    legacy_output_csv = "kemet_output.csv"
