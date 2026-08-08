from docx import Document
from docx.oxml.ns import qn

doc = Document(r"E:\GithubProgram\AgroAgentOS\.codex-tmp\business-plan\template.docx")
body = doc.element.body
for i, child in enumerate(body.iterchildren()):
    kind = child.tag.rsplit("}", 1)[-1]
    text = "".join(child.itertext()).replace("\t", "<TAB>").replace("\n", " ").strip()
    has_sect = child.find(".//" + qn("w:sectPr")) is not None or kind == "sectPr"
    print(f"{i:03d} {kind:7s} sect={has_sect!s:5s} {text[:100]}")
