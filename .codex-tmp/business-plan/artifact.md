# AgroAgentOS challenge-cup business-plan template contract

## Reference

- Retained DOCX: `E:\GithubProgram\AgroAgentOS\.codex-tmp\business-plan\template.docx`
- Source DOC: `C:\Users\WangJH\Downloads\15th_tzb_bp_template_doc (1).doc`
- DOCX SHA-256: `AC19A0CE653793FCF7E3D99FF8C511636C8257B3B9372568EFC8609A5BD406C5`
- Size: 155301 bytes
- Word-rendered page count: 14
- Section count: 4
- Visual evidence: `.codex-tmp/business-plan/template-word-render/pages/page-1.png` through `page-14.png`
- Package inventory: `.codex-tmp/business-plan/template-package-inventory.json`
- Style evidence: `.codex-tmp/business-plan/template-style-evidence.json`
- Canonical renderer status: unavailable because LibreOffice/soffice is not installed. Microsoft Word PDF export is the visual evidence path.

## Page system

- A4 portrait: 11906 x 16838 DXA (8.27 x 11.69 in).
- Margins: top/bottom 1984 DXA (3.5 cm), left/right 1587 DXA (2.8 cm).
- Header distance: approximately 851 DXA (1.5 cm); footer distance: approximately 567-992 DXA depending on section.
- Cover, TOC, and body are separate page patterns. The body page number restarts at 1.
- Header on non-cover pages: centered `第十五届“挑战杯”中国大学生创业计划竞赛` with a thin horizontal rule.
- Footer on body pages: centered Arabic page number.

## Typography and paragraph roles

- Body: SimSun/宋体 14 pt; western text Times New Roman 14 pt; justified; fixed 28 pt line spacing; 0 pt before/after; first-line indent 28 pt for prose.
- First-level chapter: `一、...`; SimHei/黑体 16 pt; left aligned; no first-line indent; keep with next.
- Second-level heading: `1. ...`; KaiTi/楷体 16 pt; left aligned; no first-line indent; keep with next.
- Third-level heading: `1.1 ...`; SimSun/宋体 14 pt; left aligned; no first-line indent; keep with next.
- Figure/table caption: SimHei/黑体 12 pt, centered.
- Table body: SimSun 12-14 pt according to density; centered vertically; header row bold with restrained blue-gray fill.
- TOC title: centered; source template uses the `目录` paragraph role. TOC entries use `toc 1`/`toc 2` styles and dot leaders.

## Lists and tables

- Use real Word list numbering for bullets/numbered items where lists are needed.
- Tables use explicit DXA widths matching the 9360-DXA usable page width, with 120-DXA outer indent and at least 100-DXA cell padding.
- Header rows repeat on page breaks; rows have no fixed height; narrative columns are left aligned and short values centered.

## Components and content flow

1. Preserve cover artwork and title furniture.
2. Replace the cover project-name slot with `AgroAgentOS——面向中小农场的多智能体智慧农服平台`.
3. Replace the cover track slot with `乡村振兴和农业农村现代化`.
4. Rebuild the TOC from real heading styles and refresh it in Microsoft Word.
5. Replace all instructional content after the cover with the ten required business-plan chapters.
6. Remove the template-only `其他/正文内容要求/正文格式说明/图表格式说明` pages.
7. Add source-grounded market data, a competitor matrix, a three-year forecast, financing plan, risk matrix, and roadmap.

## Slot map and stable locators

- `word/document.xml`, body child 9: project-name paragraph. Rewrite text while preserving paragraph placement and cover styling.
- `word/document.xml`, body child 14, first table row, second cell: track name. Rewrite text only.
- `word/document.xml`, body child 22: cover-ending section paragraph. Preserve.
- Body children 23 onward: replaceable template instructions and legacy TOC. Remove and rebuild.
- Clone the original body child 47 section properties for the TOC-to-body section break.
- Clone the original body child 138 section properties for the final body section, including page-number restart and footer relationship.
- Preserve all header/footer relationships, cover VML artwork, theme, styles, numbering, font table, and settings unless a generated table/list requires a documented addition.

## Package preservation

- Preserve-only: `[Content_Types].xml`, theme, font table, cover VML/drawing markup, header/footer parts, embedded media, document relationships, and opaque custom XML.
- Editable: `word/document.xml`, `word/styles.xml` for explicit heading/body tokens, `word/numbering.xml` for real list definitions, and `word/settings.xml` for field refresh.
- Content-driven additions: generated PNG figures and their relationships.

## Fidelity gates

- Cover artwork, competition name, and blue visual identity remain recognizably unchanged.
- A4 dimensions, margins, header rule, centered page number, body page-number restart, and template font hierarchy remain intact.
- Final document contains no instructional placeholder prose from the template and no invented project achievements.
- TOC entries and page numbers refresh successfully in Microsoft Word.
- Every final page is inspected from the Word-exported PNG set for clipping, broken tables, orphaned headings, excessive blank gaps, and missing Chinese glyphs.
