import hashlib
import json
import sys
import zipfile
from pathlib import Path


source = Path(sys.argv[1])
output = Path(sys.argv[2])
records = []
with zipfile.ZipFile(source) as archive:
    for info in sorted(archive.infolist(), key=lambda item: item.filename):
        data = archive.read(info.filename)
        records.append(
            {
                "path": info.filename,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"PARTS={len(records)}")
