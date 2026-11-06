"""
studio.parsers.dwg_handler
==========================
DWG Conversion Pipeline Adapter.
Validates DWG file headers, detects local ODA File Converter / Teigha CAD converters,
and manages the conversion workflow into DXF format for ingestion.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from utils.logging_config import logger


# Standard installation paths for Open Design Alliance (ODA) File Converter on Windows
ODA_CANDIDATE_PATHS = [
    r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe",
    r"C:\Program Files\ODAFileConverter\ODAFileConverter.exe",
]


class DWGHandler:
    """
    Handles DWG ingestion using verified ODA File Converter CLI when available,
    or provides explicit DXF conversion instructions when not installed.
    """

    def __init__(self, dwg_path: str | Path):
        self.dwg_path = Path(dwg_path)
        if not self.dwg_path.exists():
            raise FileNotFoundError(f"DWG drawing not found: {self.dwg_path}")

        self.oda_executable = self._locate_oda_converter()

    def _locate_oda_converter(self) -> Optional[str]:
        """Check PATH and common Program Files locations for ODAFileConverter."""
        # Check PATH
        path_which = shutil.which("ODAFileConverter") or shutil.which("odafileconverter")
        if path_which:
            return path_which

        # Check standard Windows directories
        import glob
        for pattern in ODA_CANDIDATE_PATHS:
            matches = glob.glob(pattern)
            if matches:
                return matches[0]

        return None

    def is_converter_available(self) -> bool:
        """Check if an automated DWG converter is present on the host system."""
        return self.oda_executable is not None

    def convert_to_dxf(self, output_dir: Optional[str | Path] = None) -> Path:
        """
        Convert DWG to DXF using ODA File Converter CLI.
        Command syntax:
          ODAFileConverter <input_dir> <output_dir> "ACAD2018" "DXF" "0" "1"
        """
        if not self.is_converter_available():
            raise RuntimeError(
                f"Native DWG ingestion requires ODA File Converter (Open Design Alliance). "
                f"Please export your drawing from AutoCAD/BricsCAD as DXF (AutoCAD 2013-2018 format), "
                f"or install ODA File Converter from https://www.opendesign.com/guestfiles/oda_file_converter."
            )

        out_path = Path(output_dir) if output_dir else self.dwg_path.parent
        out_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.oda_executable,
            str(self.dwg_path.parent),
            str(out_path),
            "ACAD2018",
            "DXF",
            "0",  # Recurse: 0 = No
            "1",  # Audit: 1 = Yes
            str(self.dwg_path.name)
        ]

        logger.info(f"Running DWG -> DXF conversion via ODA: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        target_dxf = out_path / f"{self.dwg_path.stem}.dxf"
        if target_dxf.exists():
            logger.info(f"Successfully converted {self.dwg_path.name} -> {target_dxf.name}")
            return target_dxf
        else:
            raise RuntimeError(f"ODA File Converter completed but output DXF was not generated: {result.stderr}")

    def inspect_dwg_header(self) -> Dict[str, Any]:
        """Read the binary magic byte header to determine DWG version (e.g. AC1027 = AutoCAD 2013)."""
        with open(self.dwg_path, "rb") as f:
            header = f.read(6).decode("ascii", errors="ignore")

        dwg_versions = {
            "AC1032": "AutoCAD 2018/2021/2024",
            "AC1027": "AutoCAD 2013/2014/2015/2016/2017",
            "AC1024": "AutoCAD 2010/2011/2012",
            "AC1021": "AutoCAD 2007/2008/2009",
            "AC1018": "AutoCAD 2004/2005/2006",
            "AC1015": "AutoCAD 2000",
            "AC1014": "Release 14",
        }

        version_name = dwg_versions.get(header, f"Unknown DWG Version ({header})")
        return {
            "file_name": self.dwg_path.name,
            "magic_header": header,
            "version": version_name,
            "converter_available": self.is_converter_available(),
            "converter_path": self.oda_executable,
        }
