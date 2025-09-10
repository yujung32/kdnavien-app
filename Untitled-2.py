# -*- coding: utf-8 -*-
# KD Navien 설치·시공 현황(단일 페이지) 생성 앱
# - 모바일 카메라 촬영(st.camera_input) 또는 앨범 업로드(st.file_uploader)
# - 3x2 이미지 그리드(보일러 전면, 연도, 명판, 터미널, 가스밸브, 추가)
# - 메타데이터 테이블 + 이미지 그리드가 포함된 단일 PDF 생성(ReportLab)

import io
from datetime import date
from typing import List, Tuple

import streamlit as st
from PIL import Image

# ReportLab# -*- coding: utf-8 -*-
# KD Navien 설치·시공 현황(단일 페이지) 생성 앱
# - 모바일 카메라 촬영(st.camera_input) 또는 앨범 업로드(st.file_uploader)
# - 3x2 이미지 그리드(보일러 전면, 연도, 명판, 터미널, 가스밸브, 추가)
# - 메타데이터 테이블 + 이미지 그리드가 포함된 단일 PDF 생성(ReportLab)

import io
from datetime import date
from typing import List, Tuple

import streamlit as st
from PIL import Image

# ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ────────────────────────────────────────────────
# 페이지 & 스타일 설정
# ────────────────────────────────────────────────
st.set_page_config(page_title="경동나비엔 가스보일러 설치·시공 현황", layout="wide")

# 기본 폰트 등록 시도 (나눔고딕) - 같은 폴더에 NanumGothic.ttf 있으면 한글이 깨지지 않습니다.
FONT_NAME = "NanumGothic"
try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, "NanumGothic.ttf"))
    BASE_FONT = FONT_NAME
except Exception:
    BASE_FONT = "Helvetica"  # 폰트 파일 없으면 영문 기본(한글은 깨질 수 있음)

ss = getSampleStyleSheet()
styles = {
    "title": ParagraphStyle(
        name="title",
        parent=ss["Heading1"],
        fontName=BASE_FONT,
        fontSize=16,
        leading=20,
        alignment=1,  # center
        spaceAfter=8,
    ),
    "sub": ParagraphStyle(
        name="sub",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=10,
        leading=14,
        spaceAfter=6,
    ),
    "cell": ParagraphStyle(
        name="cell",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=9,
        leading=12,
    ),
}

# ────────────────────────────────────────────────
# 유틸
# ────────────────────────────────────────────────
def _pick_image(file_uploader, camera_input) -> Image.Image | None:
    """업로드 우선, 없으면 카메라. 둘 다 없으면 None."""
    if file_uploader is not None:
        return Image.open(file_uploader).convert("RGB")
    if camera_input is not None:
        return Image.open(camera_input).convert("RGB")
    return None


def _pil_to_bytesio(img: Image.Image, quality=85) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return buf


def build_pdf(
    meta: dict,
    titled_images: List[Tuple[str, Image.Image | None]],
) -> bytes:
    """메타 정보 + 3x2 이미지 그리드로 단일 페이지 PDF 생성."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18,
        bottomMargin=18,
        leftMargin=18,
        rightMargin=18,
        title="경동나비엔 가스보일러 설치·시공 현황",
    )

    story = []

    # 제목
    story.append(Paragraph("경동나비엔 가스보일러 설치·시공 현황", styles["title"]))

    # 메타 테이블 (2열)
    meta_rows = [
        [Paragraph("현장명", styles["cell"]), Paragraph(meta["site"], styles["cell"])],
        [Paragraph("설치모델", styles["cell"]), Paragraph(meta["model"], styles["cell"])],
        [Paragraph("용량 (kcal/h, kg/h)", styles["cell"]), Paragraph(meta["capacity"], styles["cell"])],
        [Paragraph("급배기방식", styles["cell"]), Paragraph(meta["flue"], styles["cell"])],
        [Paragraph("설치대리점", styles["cell"]), Paragraph(meta["dealer"], styles["cell"])],
        [Paragraph("시공자 (이름/전화번호)", styles["cell"]), Paragraph(meta["installer"], styles["cell"])],
        [Paragraph("시공연월일", styles["cell"]), Paragraph(meta["date"], styles["cell"])],
    ]

    meta_tbl = Table(meta_rows, colWidths=[80, 415])
    meta_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(meta_tbl)
    story.append(Spacer(1, 6))

    # 이미지 그리드 3x2 (각 칸: 이미지 + 캡션)
    # 각 셀 폭을 균등 분배 (페이지 폭 - 마진 - 테이블 패딩 추정) → 3등분
    grid_data = []
    row: List
    row = []

    # Render each titled image as a vertical stack: [image, caption]
    # For RLImage sizing, set width to column width (~ (A4 width - margins)/3 - padding)
    PAGE_W, PAGE_H = A4
    col_width = (PAGE_W - 36 - 36) / 3  # 좌우 마진 18씩 고려 후 3등분(대략치)

    image_cells: List
    image_cells = []
    for title, pil_img in titled_images:
        if pil_img is None:
            # 빈 프레임 + 캡션
            cell = Table(
                [[Paragraph("(사진 없음)", styles["cell"])], [Paragraph(title, styles["cell"])]],
                style=TableStyle([
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]),
            )
        else:
            # PIL → BytesIO → RLImage, 비율 유지, 폭을 열 너비에 맞춤
            bio = _pil_to_bytesio(pil_img)
            rl_img = RLImage(bio, width=col_width - 6, preserveAspectRatio=True, hAlign="CENTER")
            cell = Table(
                [[rl_img], [Paragraph(title, styles["cell"])]],
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]),
            )
        image_cells.append(cell)

    # 3열씩 끊어서 2행 구성
    for i in range(0, 6, 3):
        grid_data.append(image_cells[i:i+3])

    grid_tbl = Table(
        grid_data,
        colWidths=[col_width, col_width, col_width],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )

    story.append(grid_tbl)

    doc.build(story)
    return buf.getvalue()


# ────────────────────────────────────────────────
# UI
# ────────────────────────────────────────────────
st.markdown("### 경동나비엔 가스보일러 설치·시공 현황")
st.info("모바일에서는 각 사진 칸에서 '카메라로 촬영' 또는 '앨범에서 선택' 둘 다 가능합니다.")

with st.form("meta_form"):
    colA, colB = st.columns(2)
    with colA:
        site = st.text_input("현장명")
        model = st.text_input("설치모델")
        capacity = st.text_input("용량 (kcal/h, kg/h)")
        flue = st.selectbox("급배기방식", ["FF", "FE"], index=0)
    with colB:
        dealer = st.text_input("설치대리점")
        installer_name = st.text_input("시공자 이름")
        installer_phone = st.text_input("시공자 전화번호")
        work_date = st.date_input("시공연월일", value=date.today(), format="YYYY-MM-DD")

    st.markdown("#### 사진 업로드/촬영 (3열 × 2행)")

    # 각 칸: 업로더 + 카메라 중 선택 입력
    labels = [
        "1. 보일러 전면",
        "2. 연도 사진",
        "3. 가스보일러 명판",
        "4. 연통 터미널",
        "5. 가스밸브 접속구",
        "6. 추가 사진",
    ]

    up_cols = st.columns(3)
    uploads = []  # [(file_uploader, camera_input), ...]

    for i, label in enumerate(labels):
        if i in (0, 1, 2):
            col = up_cols[i]
        else:
            col = up_cols[i - 3]
        with col:
            st.caption(label)
            fu = st.file_uploader(f"{label} - 앨범에서 선택", type=["jpg", "jpeg", "png"], key=f"fu_{i}")
            cam = st.camera_input(f"{label} - 카메라로 촬영", key=f"cam_{i}")
            uploads.append((fu, cam))

    submitted = st.form_submit_button("📄 단일 페이지 PDF 생성")

if submitted:
    images: List[Tuple[str, Image.Image | None]] = []
    for (fu, cam), label in zip(uploads, labels):
        pil_img = _pick_image(fu, cam)
        images.append((label, pil_img))

    meta = {
        "site": site.strip(),
        "model": model.strip(),
        "capacity": capacity.strip(),
        "flue": flue,
        "dealer": dealer.strip(),
        "installer": f"{installer_name.strip()} / {installer_phone.strip()}",
        "date": str(work_date),
    }

    # 간단 유효성 체크
    missing = []
    for k, v in [
        ("현장명", meta["site"]),
        ("설치모델", meta["model"]),
        ("용량", meta["capacity"]),
        ("설치대리점", meta["dealer"]),
        ("시공자 이름", installer_name.strip()),
        ("시공자 전화번호", installer_phone.strip()),
    ]:
        if not v:
            missing.append(k)

    if missing:
        st.error("필수 항목 누락: " + ", ".join(missing))
    else:
        try:
            pdf_bytes = build_pdf(meta, images)
            st.success("PDF 생성 완료! 아래 버튼으로 다운로드하세요.")
            st.download_button(
                label="⬇️ 설치·시공 현황 PDF 다운로드",
                data=pdf_bytes,
                file_name=f"{meta['site']}_설치시공현황.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.exception(e)

# 하단 도움말
with st.expander("도움말 / 안내"):
    st.markdown(
        """
        - **카메라 촬영이 안 뜨면**: 브라우저 카메라 권한을 허용해 주세요. iOS Safari/Chrome, Android Chrome에서 지원됩니다.\
        - **한글이 깨질 때**: 앱 파일과 같은 폴더에 `NanumGothic.ttf`를 넣어두면 PDF 글자가 정상 표시됩니다.\
        - **한 페이지 유지 팁**: 사진이 너무 크면 자동 리사이즈되지만, 6장을 모두 채울 때는 1~2MB 내외로 권장합니다.
        """
    )

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ────────────────────────────────────────────────
# 페이지 & 스타일 설정
# ────────────────────────────────────────────────
st.set_page_config(page_title="경동나비엔 가스보일러 설치·시공 현황", layout="wide")

# 기본 폰트 등록 시도 (나눔고딕) - 같은 폴더에 NanumGothic.ttf 있으면 한글이 깨지지 않습니다.
FONT_NAME = "NanumGothic"
try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, "NanumGothic.ttf"))
    BASE_FONT = FONT_NAME
except Exception:
    BASE_FONT = "Helvetica"  # 폰트 파일 없으면 영문 기본(한글은 깨질 수 있음)

ss = getSampleStyleSheet()
styles = {
    "title": ParagraphStyle(
        name="title",
        parent=ss["Heading1"],
        fontName=BASE_FONT,
        fontSize=16,
        leading=20,
        alignment=1,  # center
        spaceAfter=8,
    ),
    "sub": ParagraphStyle(
        name="sub",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=10,
        leading=14,
        spaceAfter=6,
    ),
    "cell": ParagraphStyle(
        name="cell",
        parent=ss["Normal"],
        fontName=BASE_FONT,
        fontSize=9,
        leading=12,
    ),
}

# ────────────────────────────────────────────────
# 유틸
# ────────────────────────────────────────────────
def _pick_image(file_uploader, camera_input) -> Image.Image | None:
    """업로드 우선, 없으면 카메라. 둘 다 없으면 None."""
    if file_uploader is not None:
        return Image.open(file_uploader).convert("RGB")
    if camera_input is not None:
        return Image.open(camera_input).convert("RGB")
    return None


def _pil_to_bytesio(img: Image.Image, quality=85) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return buf


def build_pdf(
    meta: dict,
    titled_images: List[Tuple[str, Image.Image | None]],
) -> bytes:
    """메타 정보 + 3x2 이미지 그리드로 단일 페이지 PDF 생성."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18,
        bottomMargin=18,
        leftMargin=18,
        rightMargin=18,
        title="경동나비엔 가스보일러 설치·시공 현황",
    )

    story = []

    # 제목
    story.append(Paragraph("경동나비엔 가스보일러 설치·시공 현황", styles["title"]))

    # 메타 테이블 (2열)
    meta_rows = [
        [Paragraph("현장명", styles["cell"]), Paragraph(meta["site"], styles["cell"])],
        [Paragraph("설치모델", styles["cell"]), Paragraph(meta["model"], styles["cell"])],
        [Paragraph("용량 (kcal/h, kg/h)", styles["cell"]), Paragraph(meta["capacity"], styles["cell"])],
        [Paragraph("급배기방식", styles["cell"]), Paragraph(meta["flue"], styles["cell"])],
        [Paragraph("설치대리점", styles["cell"]), Paragraph(meta["dealer"], styles["cell"])],
        [Paragraph("시공자 (이름/전화번호)", styles["cell"]), Paragraph(meta["installer"], styles["cell"])],
        [Paragraph("시공연월일", styles["cell"]), Paragraph(meta["date"], styles["cell"])],
    ]

    meta_tbl = Table(meta_rows, colWidths=[80, 415])
    meta_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(meta_tbl)
    story.append(Spacer(1, 6))

    # 이미지 그리드 3x2 (각 칸: 이미지 + 캡션)
    # 각 셀 폭을 균등 분배 (페이지 폭 - 마진 - 테이블 패딩 추정) → 3등분
    grid_data = []
    row: List
    row = []

    # Render each titled image as a vertical stack: [image, caption]
    # For RLImage sizing, set width to column width (~ (A4 width - margins)/3 - padding)
    PAGE_W, PAGE_H = A4
    col_width = (PAGE_W - 36 - 36) / 3  # 좌우 마진 18씩 고려 후 3등분(대략치)

    image_cells: List
    image_cells = []
    for title, pil_img in titled_images:
        if pil_img is None:
            # 빈 프레임 + 캡션
            cell = Table(
                [[Paragraph("(사진 없음)", styles["cell"])], [Paragraph(title, styles["cell"])]],
                style=TableStyle([
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]),
            )
        else:
            # PIL → BytesIO → RLImage, 비율 유지, 폭을 열 너비에 맞춤
            bio = _pil_to_bytesio(pil_img)
            rl_img = RLImage(bio, width=col_width - 6, preserveAspectRatio=True, hAlign="CENTER")
            cell = Table(
                [[rl_img], [Paragraph(title, styles["cell"])]],
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]),
            )
        image_cells.append(cell)

    # 3열씩 끊어서 2행 구성
    for i in range(0, 6, 3):
        grid_data.append(image_cells[i:i+3])

    grid_tbl = Table(
        grid_data,
        colWidths=[col_width, col_width, col_width],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )

    story.append(grid_tbl)

    doc.build(story)
    return buf.getvalue()


# ────────────────────────────────────────────────
# UI
# ────────────────────────────────────────────────
st.markdown("### 경동나비엔 가스보일러 설치·시공 현황")
st.info("모바일에서는 각 사진 칸에서 '카메라로 촬영' 또는 '앨범에서 선택' 둘 다 가능합니다.")

with st.form("meta_form"):
    colA, colB = st.columns(2)
    with colA:
        site = st.text_input("현장명")
        model = st.text_input("설치모델")
        capacity = st.text_input("용량 (kcal/h, kg/h)")
        flue = st.selectbox("급배기방식", ["FF", "FE"], index=0)
    with colB:
        dealer = st.text_input("설치대리점")
        installer_name = st.text_input("시공자 이름")
        installer_phone = st.text_input("시공자 전화번호")
        work_date = st.date_input("시공연월일", value=date.today(), format="YYYY-MM-DD")

    st.markdown("#### 사진 업로드/촬영 (3열 × 2행)")

    # 각 칸: 업로더 + 카메라 중 선택 입력
    labels = [
        "1. 보일러 전면",
        "2. 연도 사진",
        "3. 가스보일러 명판",
        "4. 연통 터미널",
        "5. 가스밸브 접속구",
        "6. 추가 사진",
    ]

    up_cols = st.columns(3)
    uploads = []  # [(file_uploader, camera_input), ...]

    for i, label in enumerate(labels):
        if i in (0, 1, 2):
            col = up_cols[i]
        else:
            col = up_cols[i - 3]
        with col:
            st.caption(label)
            fu = st.file_uploader(f"{label} - 앨범에서 선택", type=["jpg", "jpeg", "png"], key=f"fu_{i}")
            cam = st.camera_input(f"{label} - 카메라로 촬영", key=f"cam_{i}")
            uploads.append((fu, cam))

    submitted = st.form_submit_button("📄 단일 페이지 PDF 생성")

if submitted:
    images: List[Tuple[str, Image.Image | None]] = []
    for (fu, cam), label in zip(uploads, labels):
        pil_img = _pick_image(fu, cam)
        images.append((label, pil_img))

    meta = {
        "site": site.strip(),
        "model": model.strip(),
        "capacity": capacity.strip(),
        "flue": flue,
        "dealer": dealer.strip(),
        "installer": f"{installer_name.strip()} / {installer_phone.strip()}",
        "date": str(work_date),
    }

    # 간단 유효성 체크
    missing = []
    for k, v in [
        ("현장명", meta["site"]),
        ("설치모델", meta["model"]),
        ("용량", meta["capacity"]),
        ("설치대리점", meta["dealer"]),
        ("시공자 이름", installer_name.strip()),
        ("시공자 전화번호", installer_phone.strip()),
    ]:
        if not v:
            missing.append(k)

    if missing:
        st.error("필수 항목 누락: " + ", ".join(missing))
    else:
        try:
            pdf_bytes = build_pdf(meta, images)
            st.success("PDF 생성 완료! 아래 버튼으로 다운로드하세요.")
            st.download_button(
                label="⬇️ 설치·시공 현황 PDF 다운로드",
                data=pdf_bytes,
                file_name=f"{meta['site']}_설치시공현황.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.exception(e)

# 하단 도움말
with st.expander("도움말 / 안내"):
    st.markdown(
        """
        - **카메라 촬영이 안 뜨면**: 브라우저 카메라 권한을 허용해 주세요. iOS Safari/Chrome, Android Chrome에서 지원됩니다.\
        - **한글이 깨질 때**: 앱 파일과 같은 폴더에 `NanumGothic.ttf`를 넣어두면 PDF 글자가 정상 표시됩니다.\
        - **한 페이지 유지 팁**: 사진이 너무 크면 자동 리사이즈되지만, 6장을 모두 채울 때는 1~2MB 내외로 권장합니다.
        """
    )

