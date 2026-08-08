from pathlib import Path
import re
import zipfile

from docx import Document
from docx.oxml.ns import qn


DOCX = Path(r"E:\GithubProgram\AgroAgentOS\output\AgroAgentOS_第十五届挑战杯商业计划书_更新版.docx")


def main():
    document = Document(DOCX)
    body_started = False
    body_text = []
    for child in document.element.body.iterchildren():
        texts = child.xpath(".//w:t")
        text = "".join(node.text or "" for node in texts)
        if not body_started and child.tag == qn("w:p"):
            p_style = child.find("./" + qn("w:pPr") + "/" + qn("w:pStyle"))
            style_id = p_style.get(qn("w:val")) if p_style is not None else ""
            if style_id == document.styles["Heading 1"].style_id and text.strip() == "一、执行摘要":
                body_started = True
        if body_started:
            body_text.append(text)
    compact = re.sub(r"\s+", "", "".join(body_text))
    markers = ["请简要", "该部分须", "待补充", "TODO", "TBD", "________________"]
    print(f"SECTIONS={len(document.sections)}")
    print(f"TABLES={len(document.tables)} INLINE_SHAPES={len(document.inline_shapes)}")
    print(f"BODY_NONSPACE_CHARS={len(compact)}")
    print("PLACEHOLDER_HITS=" + repr({m: compact.count(m) for m in markers if m in compact}))
    for index, section in enumerate(document.sections, 1):
        sect_pr = section._sectPr
        pg_num = sect_pr.find(qn("w:pgNumType"))
        start = pg_num.get(qn("w:start")) if pg_num is not None else None
        print(
            f"SECTION_{index}: start={start} "
            f"header={section.header.part.partname} footer={section.footer.part.partname}"
        )

    with zipfile.ZipFile(DOCX) as package:
        for name in sorted(
            n for n in package.namelist() if n.startswith("word/footer") and n.endswith(".xml")
        ):
            xml = package.read(name).decode("utf-8")
            shapes = re.findall(r'<v:shape[^>]+style="([^"]+)', xml)
            indents = re.findall(r"<w:ind[^>]*/>", xml)
            justifications = re.findall(r"<w:jc[^>]*/>", xml)
            fields = re.findall(r"<w:instrText[^>]*>(.*?)</w:instrText>", xml)
            print(f"{name}: shapes={shapes} indents={indents} jc={justifications} fields={fields}")


if __name__ == "__main__":
    main()
