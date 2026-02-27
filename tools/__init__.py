from tools.registry import ToolRegistry


def build_registry() -> ToolRegistry:
    """全ツールを登録した ToolRegistry を返す。"""
    from config import settings
    from tools import file_ops, shell, code_exec
    from tools.office import pptx_tool, docx_tool, xlsx_tool

    registry = ToolRegistry()

    # ファイル操作ツール
    registry.register(
        name="read_file",
        description="ファイルの内容を読み込む。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "読み込むファイルのパス"},
            },
            "required": ["path"],
        },
        handler=file_ops.read_file,
    )
    registry.register(
        name="write_file",
        description="ファイルに内容を書き込む（新規作成・上書き）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "書き込み先ファイルのパス"},
                "content": {"type": "string", "description": "書き込む内容"},
            },
            "required": ["path", "content"],
        },
        handler=file_ops.write_file,
    )
    registry.register(
        name="edit_file",
        description="既存ファイルの指定文字列を別の文字列に置換して編集する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "編集するファイルのパス"},
                "old_string": {"type": "string", "description": "置換前の文字列"},
                "new_string": {"type": "string", "description": "置換後の文字列"},
            },
            "required": ["path", "old_string", "new_string"],
        },
        handler=file_ops.edit_file,
    )
    registry.register(
        name="list_directory",
        description="ディレクトリの一覧を取得する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "一覧を取得するディレクトリのパス"},
            },
            "required": ["path"],
        },
        handler=file_ops.list_directory,
    )
    registry.register(
        name="search_files",
        description="ディレクトリ内のファイル内容をパターン検索する（grep 相当）。",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "検索する正規表現パターン"},
                "path": {
                    "type": "string",
                    "description": "検索対象のディレクトリまたはファイルパス",
                },
            },
            "required": ["pattern", "path"],
        },
        handler=file_ops.search_files,
    )

    # シェル実行
    if settings.allow_shell_exec:
        registry.register(
            name="run_shell",
            description="シェルコマンドを実行し stdout/stderr を返す。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "実行するシェルコマンド"},
                },
                "required": ["command"],
            },
            handler=shell.run_shell,
        )

    # Python コード実行
    if settings.allow_code_exec:
        registry.register(
            name="run_python",
            description="Python コードをサンドボックス内で実行し結果を返す。",
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "実行する Python コード"},
                },
                "required": ["code"],
            },
            handler=code_exec.run_python,
        )

    # Office ツール
    registry.register(
        name="pptx_read",
        description="PPTX ファイルのスライド内容を JSON 形式で取得する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "PPTX ファイルのパス"},
            },
            "required": ["path"],
        },
        handler=pptx_tool.pptx_read,
    )
    registry.register(
        name="pptx_edit_slide",
        description="スライドのタイトル・本文テキストを変更して保存する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "PPTX ファイルのパス"},
                "slide_index": {
                    "type": "integer",
                    "description": "編集するスライドのインデックス（0始まり）",
                },
                "title": {"type": "string", "description": "新しいタイトル（省略可）"},
                "content": {
                    "type": "string",
                    "description": "新しい本文テキスト（省略可）",
                },
            },
            "required": ["path", "slide_index"],
        },
        handler=pptx_tool.pptx_edit_slide,
    )
    registry.register(
        name="pptx_add_slide",
        description="PPTX ファイルにスライドを追加する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "PPTX ファイルのパス"},
                "title": {"type": "string", "description": "新しいスライドのタイトル"},
                "content": {
                    "type": "string",
                    "description": "新しいスライドの本文テキスト",
                },
            },
            "required": ["path", "title"],
        },
        handler=pptx_tool.pptx_add_slide,
    )
    registry.register(
        name="docx_read",
        description="DOCX ファイルの内容をテキストとして抽出する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "DOCX ファイルのパス"},
            },
            "required": ["path"],
        },
        handler=docx_tool.docx_read,
    )
    registry.register(
        name="docx_edit",
        description="DOCX の指定インデックスの段落テキストを編集する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "DOCX ファイルのパス"},
                "paragraph_index": {
                    "type": "integer",
                    "description": "編集する段落のインデックス（0始まり）",
                },
                "new_text": {"type": "string", "description": "新しい段落テキスト"},
            },
            "required": ["path", "paragraph_index", "new_text"],
        },
        handler=docx_tool.docx_edit,
    )
    registry.register(
        name="xlsx_read",
        description="XLSX ファイルのセル内容を取得する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "XLSX ファイルのパス"},
                "sheet_name": {
                    "type": "string",
                    "description": "読み込むシート名（省略時はアクティブシート）",
                },
            },
            "required": ["path"],
        },
        handler=xlsx_tool.xlsx_read,
    )
    registry.register(
        name="xlsx_write_cell",
        description="XLSX の指定セルに値を書き込んで保存する。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "XLSX ファイルのパス"},
                "sheet_name": {"type": "string", "description": "書き込み先シート名"},
                "cell": {"type": "string", "description": "セル番地 (例: A1, B3)"},
                "value": {"description": "書き込む値"},
            },
            "required": ["path", "sheet_name", "cell", "value"],
        },
        handler=xlsx_tool.xlsx_write_cell,
    )

    return registry


__all__ = ["ToolRegistry", "build_registry"]
