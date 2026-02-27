"""PowerPoint (PPTX) 操作ツール。python-pptx を使用する。"""

import json
import os
from typing import Optional

from utils.file_guard import check_write_allowed
from utils.logger import get_logger

logger = get_logger(__name__)


def pptx_read(path: str) -> str:
    """PPTX ファイルのスライド内容を JSON 形式で取得する。

    Args:
        path: PPTX ファイルのパス

    Returns:
        スライド構造の JSON 文字列
    """
    try:
        from pptx import Presentation
    except ImportError:
        return "エラー: python-pptx がインストールされていません。pip install python-pptx"

    import os
    resolved = os.path.abspath(path)
    if not os.path.isfile(resolved):
        return f"エラー: ファイルが存在しません: {resolved}"

    logger.debug("pptx_read: %s", resolved)
    try:
        prs = Presentation(resolved)
        slides_data = []
        for i, slide in enumerate(prs.slides):
            slide_info: dict = {"index": i, "shapes": []}
            for shape in slide.shapes:
                shape_info: dict = {"shape_id": shape.shape_id, "name": shape.name}
                if shape.has_text_frame:
                    shape_info["text"] = shape.text_frame.text
                    shape_info["paragraphs"] = [
                        p.text for p in shape.text_frame.paragraphs
                    ]
                if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
                    shape_info["type"] = "picture"
                else:
                    shape_info["type"] = "text_or_other"
                slide_info["shapes"].append(shape_info)
            # スライドのタイトルを抽出
            if slide.shapes.title:
                slide_info["title"] = slide.shapes.title.text
            slides_data.append(slide_info)
        return json.dumps(
            {"slide_count": len(slides_data), "slides": slides_data},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        logger.error("pptx_read エラー: %s", e)
        return f"エラー: PPTX 読み込み失敗: {e}"


def pptx_edit_slide(
    path: str,
    slide_index: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> str:
    """スライドのタイトル・本文テキストを変更して保存する。

    Args:
        path: PPTX ファイルのパス
        slide_index: 編集するスライドのインデックス（0始まり）
        title: 新しいタイトル（省略可）
        content: 新しい本文テキスト（省略可）

    Returns:
        成功メッセージまたはエラーメッセージ
    """
    try:
        from pptx import Presentation
    except ImportError:
        return "エラー: python-pptx がインストールされていません。pip install python-pptx"

    resolved = os.path.abspath(path)
    if err := check_write_allowed(resolved):
        return err
    if not os.path.isfile(resolved):
        return f"エラー: ファイルが存在しません: {resolved}"

    logger.debug("pptx_edit_slide: %s slide=%d", resolved, slide_index)
    try:
        prs = Presentation(resolved)
        if slide_index < 0 or slide_index >= len(prs.slides):
            return (
                f"エラー: スライドインデックスが範囲外です "
                f"(0〜{len(prs.slides) - 1})"
            )
        slide = prs.slides[slide_index]

        if title is not None:
            title_shape = slide.shapes.title
            if title_shape and title_shape.has_text_frame:
                title_shape.text_frame.text = title
            else:
                return "エラー: このスライドにはタイトルシェイプがありません"

        if content is not None:
            # タイトル以外の最初のテキストフレームに書き込む
            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue
                if shape.has_text_frame:
                    shape.text_frame.text = content
                    break
            else:
                return "エラー: 本文を書き込めるシェイプが見つかりませんでした"

        prs.save(resolved)
        return f"スライド {slide_index} を更新しました: {resolved}"
    except Exception as e:
        logger.error("pptx_edit_slide エラー: %s", e)
        return f"エラー: PPTX 編集失敗: {e}"


def pptx_add_slide(
    path: str,
    title: str,
    content: str = "",
) -> str:
    """PPTX ファイルにスライドを追加する。

    Args:
        path: PPTX ファイルのパス
        title: 新しいスライドのタイトル
        content: 新しいスライドの本文テキスト

    Returns:
        成功メッセージまたはエラーメッセージ
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
    except ImportError:
        return "エラー: python-pptx がインストールされていません。pip install python-pptx"

    resolved = os.path.abspath(path)
    if err := check_write_allowed(resolved):
        return err
    if not os.path.isfile(resolved):
        return f"エラー: ファイルが存在しません: {resolved}"

    logger.debug("pptx_add_slide: %s title=%s", resolved, title)
    try:
        prs = Presentation(resolved)
        # レイアウト 1 (タイトルと本文) を使用、存在しなければ 0 を使用
        layout_index = 1 if len(prs.slide_layouts) > 1 else 0
        slide_layout = prs.slide_layouts[layout_index]
        slide = prs.slides.add_slide(slide_layout)

        # タイトル設定
        if slide.shapes.title:
            slide.shapes.title.text = title

        # 本文設定（タイトル以外の最初のプレースホルダ）
        if content:
            for ph in slide.placeholders:
                if ph.placeholder_format.idx != 0:
                    ph.text = content
                    break

        prs.save(resolved)
        new_index = len(prs.slides) - 1
        return f"スライドを追加しました (index={new_index}): {resolved}"
    except Exception as e:
        logger.error("pptx_add_slide エラー: %s", e)
        return f"エラー: PPTX スライド追加失敗: {e}"
