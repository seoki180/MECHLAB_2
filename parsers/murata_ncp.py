from .base import LegacyScriptParser


class MurataNcpParser(LegacyScriptParser):
    maker = "murata"
    model = "NCP"
    script_name = "murata_NCP.py"
    input_folder = "murata_NCP"
    legacy_output_csv = "murata_NCP_output.csv"
