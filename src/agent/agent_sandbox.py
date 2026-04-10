# -*- coding: utf-8 -*-
"""
Agent 沙箱环境模块 (Agent Sandbox)

功能描述:
    为 AI 智能体通过代码执行任务提供隔离环境。
    支持在安全受控的环境中运行 Python 脚本或命令行工具，
    并捕获执行结果返回给智能体。
"""

import os
import sys
import subprocess
import shutil
import time
import json
import threading
import uuid
import shlex
import textwrap

OFFICE_BINARY_EXTS = {'.docx', '.pptx', '.xlsx', '.pdf'}

class SandboxError(Exception):
    pass

class AgentSandbox:
    TEXT_DECODE_CANDIDATES = (
        'utf-8-sig',
        'utf-8',
        'utf-16',
        'utf-16-le',
        'utf-16-be',
        'gb18030',
        'gbk',
        'cp936',
        'big5',
        'shift_jis',
        'latin-1',
    )

    def __init__(self, root_dir):
        # Allow operations ONLY within this 'root_dir'
        self.root_dir = os.path.abspath(root_dir)
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir, exist_ok=True)

        # root_dir itself is the workspace root
        self.workspace_dir = self.root_dir
        self.project_root = os.path.abspath(os.path.join(self.root_dir, '..', '..'))
        data_dir = os.path.join(self.project_root, 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.external_approvals_path = os.path.join(data_dir, 'sandbox_external_approvals.json')
        self._external_lock = threading.Lock()
        self._ensure_external_approval_storage()

    def _ensure_external_approval_storage(self):
        if not os.path.exists(self.external_approvals_path):
            with open(self.external_approvals_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def _load_external_approvals(self):
        try:
            with open(self.external_approvals_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_external_approvals(self, approvals):
        with open(self.external_approvals_path, 'w', encoding='utf-8') as f:
            json.dump(approvals, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _norm_path_value(path):
        return os.path.normcase(os.path.abspath(str(path or '').strip()))

    def _request_external_approval(self, abs_path, action='read'):
        now = int(time.time())
        with self._external_lock:
            approvals = self._load_external_approvals()
            norm = self._norm_path_value(abs_path)

            for item in reversed(approvals):
                if (
                    item.get('status') == 'pending'
                    and item.get('path_norm') == norm
                    and str(item.get('action', 'read')) == str(action)
                    and int(item.get('created_at', 0) or 0) >= now - 1800
                ):
                    return item

            req = {
                'id': str(uuid.uuid4())[:12],
                'status': 'pending',
                'action': str(action or 'read'),
                'path': abs_path,
                'path_norm': norm,
                'created_at': now,
                'resolved_at': 0,
                'reason': ''
            }
            approvals.append(req)
            approvals = approvals[-300:]
            self._save_external_approvals(approvals)
            return req

    def list_external_approvals(self, status='pending', limit=100):
        with self._external_lock:
            approvals = self._load_external_approvals()
        st = str(status or '').strip().lower()
        if st and st != 'all':
            approvals = [a for a in approvals if str(a.get('status', '')).lower() == st]
        approvals = sorted(approvals, key=lambda x: int(x.get('created_at', 0) or 0), reverse=True)
        try:
            max_items = max(1, min(int(limit), 300))
        except Exception:
            max_items = 100
        return approvals[:max_items]

    def resolve_external_approval(self, request_id, approve, reason=''):
        rid = str(request_id or '').strip()
        if not rid:
            return {'success': False, 'error': 'request_id is required'}
        now = int(time.time())
        with self._external_lock:
            approvals = self._load_external_approvals()
            found = None
            for item in approvals:
                if str(item.get('id')) == rid:
                    found = item
                    break
            if not found:
                return {'success': False, 'error': f'approval request not found: {rid}'}

            found['status'] = 'approved' if bool(approve) else 'rejected'
            found['resolved_at'] = now
            found['reason'] = str(reason or '')[:500]
            self._save_external_approvals(approvals)

        return {'success': True, 'request': found}

    def _is_external_access_allowed(self, abs_path, action='read', approval_id=''):
        rid = str(approval_id or '').strip()
        if not rid:
            return False
        with self._external_lock:
            approvals = self._load_external_approvals()
        norm = self._norm_path_value(abs_path)
        for item in approvals:
            if str(item.get('id')) != rid:
                continue
            if str(item.get('status')) != 'approved':
                continue
            if str(item.get('action', 'read')) != str(action or 'read'):
                continue
            req_norm = str(item.get('path_norm', ''))
            if norm == req_norm or norm.startswith(req_norm + os.sep):
                return True
        return False

    def validate_path(self, path, action='read', external_approval_id=''):
        """Ensure path is within sandbox root, or request external approval when configured."""
        # If path is absolute, check if it's inside root_dir
        if os.path.isabs(path):
            abs_path = os.path.abspath(path)
        else:
            # If relative, join with root_dir
            abs_path = os.path.abspath(os.path.join(self.root_dir, path))
            
        if abs_path.startswith(self.root_dir):
            return abs_path

        from src.core.config import CONFIG
        wm_cfg = CONFIG.get('work_mode', {}) if isinstance(CONFIG, dict) else {}
        features = wm_cfg.get('features', {}) if isinstance(wm_cfg, dict) else {}
        allow_external = bool(features.get('allow_external_access', False))
        require_approval = bool(features.get('require_external_approval', True))

        if not allow_external:
            raise SandboxError(
                f"Access Denied: Path '{path}' resolves to '{abs_path}' outside sandbox. "
                "Enable allow_external_access first."
            )

        if require_approval:
            if self._is_external_access_allowed(abs_path, action=action, approval_id=external_approval_id):
                return abs_path
            req = self._request_external_approval(abs_path, action=action)
            raise SandboxError(
                f"APPROVAL_REQUIRED: external path access requires approval. "
                f"request_id={req.get('id')} action={action} path={abs_path}"
            )

        return abs_path

    def read_file(self, path, external_approval_id=''):
        safe_path = self.validate_path(path, action='read', external_approval_id=external_approval_id)
        if not os.path.exists(safe_path):
            return f"Error: File not found: {path}"
        try:
            with open(safe_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def write_file(self, path, content, external_approval_id=''):
        safe_path = self.validate_path(path, action='write', external_approval_id=external_approval_id)
        ext = os.path.splitext(safe_path)[1].lower()
        if ext in OFFICE_BINARY_EXTS:
            return (
                f"Error: Binary office format '{ext}' cannot be created by plain text write_file. "
                "Use create_document/convert_document tools instead."
            )
        try:
            dir_path = os.path.dirname(safe_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Success: Wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def append_file_content(self, path, content, position=None, external_approval_id=''):
        safe_path = self.validate_path(path, action='write', external_approval_id=external_approval_id)
        ext = os.path.splitext(safe_path)[1].lower()
        if ext in OFFICE_BINARY_EXTS:
            return (
                f"Error: Binary office format '{ext}' cannot be modified by append_file_content. "
                "Use convert_document or regenerate with create_document."
            )
        try:
            dir_path = os.path.dirname(safe_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            if not os.path.exists(safe_path):
                if position not in (None, 0):
                    return "Error: position must be 0 when creating a new file"
                with open(safe_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Success: Appended to {path}"

            with open(safe_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            insert_at = len(original_content) if position is None else int(position)
            if insert_at < 0:
                return "Error: position must be non-negative"
            if insert_at > len(original_content):
                return "Error: position is out of range"

            updated_content = original_content[:insert_at] + content + original_content[insert_at:]

            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            return f"Success: Appended to {path} at position {insert_at}"
        except Exception as e:
            return f"Error appending file: {str(e)}"

    def delete_file_content(self, path, position, length, external_approval_id=''):
        safe_path = self.validate_path(path, action='delete', external_approval_id=external_approval_id)
        ext = os.path.splitext(safe_path)[1].lower()
        if ext in OFFICE_BINARY_EXTS:
            return (
                f"Error: Binary office format '{ext}' cannot be edited as plain text. "
                "Use convert_document then regenerate target format."
            )
        try:
            if not os.path.exists(safe_path):
                return f"Error: File not found: {path}"
            if os.path.isdir(safe_path):
                return f"Error: Path is a directory, not a file: {path}"

            with open(safe_path, 'r', encoding='utf-8') as f:
                content = f.read()

            start = int(position)
            delete_length = int(length)
            if start < 0 or delete_length < 0:
                return "Error: position and length must be non-negative"
            if start > len(content):
                return "Error: position is out of range"

            end = min(start + delete_length, len(content))
            updated_content = content[:start] + content[end:]

            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            return f"Success: Deleted content from {path}"
        except ValueError:
            return "Error: position and length must be integers"
        except Exception as e:
            return f"Error deleting file content: {str(e)}"

    def delete_file(self, path, external_approval_id=''):
        safe_path = self.validate_path(path, action='delete', external_approval_id=external_approval_id)
        try:
            if not os.path.exists(safe_path):
                return f"Error: File not found: {path}"
            if os.path.isdir(safe_path):
                return f"Error: Path is a directory, not a file: {path}"
            os.remove(safe_path)
            return f"Success: Deleted {path}"
        except Exception as e:
            return f"Error deleting file: {str(e)}"

    def list_dir(self, path='.', external_approval_id=''):
        target = os.path.join(self.workspace_dir, path)
        safe_path = self.validate_path(target, action='read', external_approval_id=external_approval_id)
        try:
            return str(os.listdir(safe_path))
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    @staticmethod
    def _load_optional_module(import_name, pip_hint):
        try:
            return __import__(import_name, fromlist=['*']), ""
        except Exception:
            return None, f"Missing dependency '{import_name}'. Install with: pip install {pip_hint}"

    @classmethod
    def _decode_text_bytes(cls, raw_bytes):
        """Decode text bytes with fallback encodings to avoid conversion failures/garbled text."""
        if isinstance(raw_bytes, str):
            return raw_bytes
        if not isinstance(raw_bytes, (bytes, bytearray)):
            return str(raw_bytes or '')

        for enc in cls.TEXT_DECODE_CANDIDATES:
            try:
                return bytes(raw_bytes).decode(enc)
            except Exception:
                continue
        return bytes(raw_bytes).decode('utf-8', errors='replace')

    def _read_text_file_with_fallback(self, safe_path):
        with open(safe_path, 'rb') as f:
            raw = f.read()
        return self._decode_text_bytes(raw)

    def _read_text_from_file_for_conversion(self, safe_path):
        ext = os.path.splitext(safe_path)[1].lower()
        if ext in {'.txt', '.md', '.py', '.json'}:
            return self._read_text_file_with_fallback(safe_path)

        if ext == '.docx':
            docx_mod, err = self._load_optional_module('docx', 'python-docx')
            if docx_mod is None:
                raise SandboxError(err)
            doc = docx_mod.Document(safe_path)
            return "\n".join([p.text for p in doc.paragraphs])

        if ext == '.pptx':
            pptx_mod, err = self._load_optional_module('pptx', 'python-pptx')
            if pptx_mod is None:
                raise SandboxError(err)
            prs = pptx_mod.Presentation(safe_path)
            lines = []
            for idx, slide in enumerate(prs.slides, start=1):
                lines.append(f"# Slide {idx}")
                for shape in slide.shapes:
                    if hasattr(shape, 'text') and str(shape.text or '').strip():
                        lines.append(str(shape.text))
            return "\n".join(lines)

        if ext == '.xlsx':
            openpyxl_mod, err = self._load_optional_module('openpyxl', 'openpyxl')
            if openpyxl_mod is None:
                raise SandboxError(err)
            wb = openpyxl_mod.load_workbook(safe_path, data_only=True)
            lines = []
            for ws in wb.worksheets:
                lines.append(f"# Sheet: {ws.title}")
                for row in ws.iter_rows(values_only=True):
                    vals = ["" if v is None else str(v) for v in row]
                    lines.append("\t".join(vals).rstrip())
            return "\n".join(lines)

        if ext == '.pdf':
            pypdf_mod, err = self._load_optional_module('pypdf', 'pypdf')
            if pypdf_mod is None:
                pypdf_mod, err = self._load_optional_module('PyPDF2', 'PyPDF2')
            if pypdf_mod is None:
                raise SandboxError(err)
            reader = pypdf_mod.PdfReader(safe_path)
            texts = []
            for page in reader.pages:
                texts.append(page.extract_text() or '')
            return "\n".join(texts)

        raise SandboxError(f"Unsupported source format for conversion: {ext}")

    def create_document(self, output_path, content, fmt=None, title='', external_approval_id=''):
        safe_path = self.validate_path(output_path, action='write', external_approval_id=external_approval_id)
        out_ext = (fmt or os.path.splitext(safe_path)[1].lower().lstrip('.')).lower().strip()
        if not out_ext:
            return "Error: target format is required"

        text_content = content
        if isinstance(text_content, (bytes, bytearray)):
            text_content = self._decode_text_bytes(text_content)
        if isinstance(content, (dict, list)):
            text_content = json.dumps(content, ensure_ascii=False, indent=2)
        text_content = str(text_content or '')

        try:
            dir_path = os.path.dirname(safe_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            if out_ext in {'txt', 'md', 'py'}:
                with open(safe_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                return f"Success: Created {output_path}"

            if out_ext == 'json':
                parsed = content if isinstance(content, (dict, list)) else json.loads(text_content)
                with open(safe_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed, f, ensure_ascii=False, indent=2)
                return f"Success: Created {output_path}"

            if out_ext == 'docx':
                docx_mod, err = self._load_optional_module('docx', 'python-docx')
                if docx_mod is None:
                    return f"Error: {err}"
                doc = docx_mod.Document()
                if title:
                    doc.add_heading(str(title), level=1)
                for line in text_content.splitlines() or [text_content]:
                    doc.add_paragraph(line)
                doc.save(safe_path)
                return f"Success: Created {output_path}"

            if out_ext == 'pptx':
                pptx_mod, err = self._load_optional_module('pptx', 'python-pptx')
                if pptx_mod is None:
                    return f"Error: {err}"
                prs = pptx_mod.Presentation()
                slides = [s.strip() for s in text_content.split('\n\n') if s.strip()] or [text_content]
                for idx, block in enumerate(slides, start=1):
                    slide = prs.slides.add_slide(prs.slide_layouts[1])
                    slide.shapes.title.text = title or f"Slide {idx}"
                    slide.placeholders[1].text = block[:2500]
                prs.save(safe_path)
                return f"Success: Created {output_path}"

            if out_ext == 'xlsx':
                openpyxl_mod, err = self._load_optional_module('openpyxl', 'openpyxl')
                if openpyxl_mod is None:
                    return f"Error: {err}"
                wb = openpyxl_mod.Workbook()
                ws = wb.active
                ws.title = 'Sheet1'
                rows = [line.split('\t') for line in text_content.splitlines()] or [[text_content]]
                for row in rows:
                    ws.append(row)
                wb.save(safe_path)
                return f"Success: Created {output_path}"

            if out_ext == 'pdf':
                canvas_mod, err_canvas = self._load_optional_module('reportlab.pdfgen.canvas', 'reportlab')
                pagesize_mod, err_pagesize = self._load_optional_module('reportlab.lib.pagesizes', 'reportlab')
                if canvas_mod is None or pagesize_mod is None:
                    return f"Error: {err_canvas or err_pagesize}"

                # Prefer CJK-capable font to avoid Chinese/Japanese text rendering as garbled blocks.
                pdfmetrics_mod, _ = self._load_optional_module('reportlab.pdfbase.pdfmetrics', 'reportlab')
                cidfonts_mod, _ = self._load_optional_module('reportlab.pdfbase.cidfonts', 'reportlab')

                title_font = 'Helvetica-Bold'
                body_font = 'Helvetica'
                if pdfmetrics_mod is not None and cidfonts_mod is not None:
                    try:
                        pdfmetrics_mod.registerFont(cidfonts_mod.UnicodeCIDFont('STSong-Light'))
                        title_font = 'STSong-Light'
                        body_font = 'STSong-Light'
                    except Exception:
                        pass

                canvas = canvas_mod.Canvas(safe_path, pagesize=pagesize_mod.letter)
                width, height = pagesize_mod.letter
                left = 40
                right = 40
                usable_width = max(120, int(width - left - right))
                y = height - 40

                def wrap_line(line_text):
                    # ASCII is narrower; CJK is wider. This heuristic keeps lines inside page width.
                    has_non_ascii = any(ord(ch) > 127 for ch in line_text)
                    max_chars = max(16, usable_width // (11 if has_non_ascii else 6))
                    return textwrap.wrap(line_text, width=max_chars) or ['']

                if title:
                    canvas.setFont(title_font, 14)
                    canvas.drawString(40, y, str(title)[:100])
                    y -= 24

                canvas.setFont(body_font, 10)
                normalized = text_content.replace('\r\n', '\n').replace('\r', '\n').expandtabs(4)
                for raw_line in (normalized.splitlines() or [normalized]):
                    for line in wrap_line(raw_line):
                        if y < 40:
                            canvas.showPage()
                            canvas.setFont(body_font, 10)
                            y = height - 40
                        canvas.drawString(left, y, line)
                        y -= 14

                if y < 40:
                    # Keep behavior deterministic when very long content exactly fills a page.
                    canvas.showPage()
                canvas.save()
                return f"Success: Created {output_path}"

            return f"Error: Unsupported target format: {out_ext}"
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON content: {e}"
        except Exception as e:
            return f"Error creating document: {str(e)}"

    def convert_document(self, source_path, target_path, target_format=None, title='', external_approval_id=''):
        try:
            safe_source = self.validate_path(source_path, action='read', external_approval_id=external_approval_id)
            self.validate_path(target_path, action='write', external_approval_id=external_approval_id)
            if not os.path.exists(safe_source):
                return f"Error: Source file not found: {source_path}"

            inferred = os.path.splitext(target_path)[1].lower().lstrip('.')
            out_fmt = (target_format or inferred).lower().strip()
            if not out_fmt:
                return "Error: target_format is required"

            text = self._read_text_from_file_for_conversion(safe_source)
            if out_fmt == 'json':
                payload = {
                    "source": os.path.basename(source_path),
                    "converted_at": int(time.time()),
                    "content": text,
                }
                return self.create_document(target_path, payload, fmt='json', title=title)

            return self.create_document(target_path, text, fmt=out_fmt, title=title)
        except SandboxError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error converting document: {str(e)}"

    def execute_python(self, code_str, filename="temp_script.py"):
        """Execute Python code and return a backward-compatible text output."""
        details = self.execute_python_with_details(code_str, filename=filename)
        return details.get("combined_output", "")

    def run_project_debug(self, target='.', run_tests=True, max_output_chars=12000, external_approval_id=''):
        """Run compile/test diagnostics to help Agent iterate until project is runnable."""
        try:
            safe_target = self.validate_path(target or '.', action='read', external_approval_id=external_approval_id)
            if not os.path.isdir(safe_target):
                safe_target = os.path.dirname(safe_target)

            outputs = []

            compile_cmd = [sys.executable, '-m', 'py_compile']
            py_files = []
            for root, _, files in os.walk(safe_target):
                for name in files:
                    if name.endswith('.py'):
                        py_files.append(os.path.join(root, name))
                if len(py_files) >= 120:
                    break

            if py_files:
                result_compile = subprocess.run(
                    compile_cmd + py_files,
                    cwd=safe_target,
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                outputs.append({
                    'step': 'py_compile',
                    'return_code': result_compile.returncode,
                    'stdout': result_compile.stdout,
                    'stderr': result_compile.stderr,
                })
            else:
                outputs.append({'step': 'py_compile', 'return_code': 0, 'stdout': 'No python files found', 'stderr': ''})

            if run_tests:
                try:
                    result_test = subprocess.run(
                        [sys.executable, '-m', 'pytest', '-q'],
                        cwd=safe_target,
                        capture_output=True,
                        text=True,
                        timeout=180,
                        check=False,
                    )
                    outputs.append({
                        'step': 'pytest',
                        'return_code': result_test.returncode,
                        'stdout': result_test.stdout,
                        'stderr': result_test.stderr,
                    })
                except Exception as e:
                    outputs.append({'step': 'pytest', 'return_code': -1, 'stdout': '', 'stderr': str(e)})

            ok = all(int(item.get('return_code', 1)) == 0 for item in outputs)
            payload = {
                'ok': bool(ok),
                'target': safe_target,
                'steps': outputs,
                'summary': 'Project diagnostics passed.' if ok else 'Project diagnostics found issues.'
            }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            if len(text) > max_output_chars:
                text = text[:max_output_chars] + '\n...truncated...'
            return text
        except SandboxError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error running project debug: {str(e)}"

    def generate_data_chart(self, source_path, output_image_path='analysis_chart.png', chart_type='line', x_column='', y_column='', external_approval_id=''):
        try:
            safe_source = self.validate_path(source_path, action='read', external_approval_id=external_approval_id)
            safe_output = self.validate_path(output_image_path, action='write', external_approval_id=external_approval_id)

            pandas_mod, pandas_err = self._load_optional_module('pandas', 'pandas')
            plt_mod, plt_err = self._load_optional_module('matplotlib.pyplot', 'matplotlib')
            if pandas_mod is None or plt_mod is None:
                return f"Error: {pandas_err or plt_err}"

            ext = os.path.splitext(safe_source)[1].lower()
            if ext == '.csv':
                df = pandas_mod.read_csv(safe_source)
            elif ext == '.json':
                df = pandas_mod.read_json(safe_source)
            elif ext in {'.xlsx', '.xls'}:
                df = pandas_mod.read_excel(safe_source)
            else:
                return f"Error: Unsupported data format for chart: {ext}. Use csv/json/xlsx."

            if df.empty:
                return "Error: Data file is empty."

            x_col = str(x_column or '').strip() or str(df.columns[0])
            if x_col not in df.columns:
                return f"Error: x_column '{x_col}' not found. Available: {list(df.columns)}"

            if y_column:
                y_cols = [c.strip() for c in str(y_column).split(',') if c.strip()]
            else:
                y_cols = [str(c) for c in df.columns if str(c) != x_col][:2]
            y_cols = [c for c in y_cols if c in df.columns]
            if not y_cols:
                return "Error: No valid y columns found."

            dir_path = os.path.dirname(safe_output)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            fig = plt_mod.figure(figsize=(10, 5))
            if chart_type == 'bar':
                for col in y_cols:
                    plt_mod.bar(df[x_col], df[col], alpha=0.65, label=col)
            elif chart_type == 'scatter':
                for col in y_cols:
                    plt_mod.scatter(df[x_col], df[col], s=18, label=col)
            else:
                for col in y_cols:
                    plt_mod.plot(df[x_col], df[col], marker='o', linewidth=1.5, label=col)

            plt_mod.xlabel(x_col)
            plt_mod.ylabel(', '.join(y_cols))
            plt_mod.title(f"Data Analysis Chart ({chart_type})")
            plt_mod.grid(True, linestyle='--', alpha=0.35)
            plt_mod.legend()
            plt_mod.tight_layout()
            plt_mod.savefig(safe_output, dpi=120)
            plt_mod.close(fig)

            summary = {
                'success': True,
                'source': source_path,
                'output_image': output_image_path,
                'chart_type': chart_type,
                'rows': int(len(df)),
                'columns': [str(c) for c in df.columns],
                'x_column': x_col,
                'y_columns': y_cols,
            }
            return json.dumps(summary, ensure_ascii=False, indent=2)
        except SandboxError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error generating chart: {str(e)}"

    def generate_markdown_diagram(self, output_path, diagram_type='flowchart', title='Diagram', content=''):
        try:
            safe_output = self.validate_path(output_path, action='write')
            dir_path = os.path.dirname(safe_output)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            d_type = str(diagram_type or 'flowchart').strip().lower()
            user_content = str(content or '').strip()
            if not user_content:
                user_content = 'A[Start] --> B[Process] --> C[Done]'

            if d_type == 'pie':
                mermaid = 'pie title {}\n{}'.format(title, user_content)
            elif d_type == 'mindmap':
                mermaid = 'mindmap\n  root(({}))\n    {}'.format(title, user_content.replace('\n', '\n    '))
            else:
                mermaid = 'flowchart TD\n{}'.format(user_content)

            md = f"# {title}\n\n```mermaid\n{mermaid}\n```\n"
            with open(safe_output, 'w', encoding='utf-8') as f:
                f.write(md)
            return f"Success: Markdown diagram generated at {output_path}"
        except SandboxError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error generating markdown diagram: {str(e)}"

    def start_web_preview(self, serve_path='.', port=8765, external_approval_id=''):
        try:
            safe_target = self.validate_path(serve_path, action='read', external_approval_id=external_approval_id)
            if not os.path.isdir(safe_target):
                safe_target = os.path.dirname(safe_target)

            try:
                port_num = int(port)
            except Exception:
                port_num = 8765
            port_num = max(1024, min(port_num, 65535))

            cmd = [sys.executable, '-m', 'http.server', str(port_num), '--bind', '127.0.0.1']
            proc = subprocess.Popen(
                cmd,
                cwd=safe_target,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            url = f"http://127.0.0.1:{port_num}/"
            payload = {
                'success': True,
                'pid': int(proc.pid),
                'path': safe_target,
                'url': url,
                'command': ' '.join(shlex.quote(p) for p in cmd),
            }
            return json.dumps(payload, ensure_ascii=False, indent=2)
        except SandboxError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error starting web preview: {str(e)}"

    def execute_python_with_details(self, code_str, filename="temp_script.py"):
        """
        Execute code in a safer runtime (Docker preferred, local fallback).
        Auto-detects language based on file extension (.py, .js, .ts).
        """
        script_path = os.path.join(self.workspace_dir, filename)
        try:
            self.write_file(script_path, code_str)
            from src.core.config import CONFIG

            wm_cfg = CONFIG.get('work_mode', {}) if isinstance(CONFIG, dict) else {}
            chat_settings = wm_cfg.get('chat_settings', {}) if isinstance(wm_cfg, dict) else {}
            prefer_docker = bool(chat_settings.get('sandbox_use_docker_runtime', True))

            # Detect language from file extension
            file_ext = os.path.splitext(filename)[1].lower()

            if file_ext == '.js':
                # Execute JavaScript with amala-sandbox
                return self.execute_javascript_with_amala(code_str)
            elif file_ext in {'.py'}:
                # Execute Python with Docker/local runtime
                if prefer_docker and shutil.which('docker'):
                    return self._execute_python_in_docker(filename)
                return self._execute_python_local(filename, docker_preferred=prefer_docker)
            else:
                # Unsupported file type
                return {
                    "ok": False,
                    "engine": "unknown",
                    "return_code": -1,
                    "stdout": "",
                    "stderr": f"Unsupported file type: {file_ext}. Only .py and .js are supported.",
                    "timed_out": False,
                    "duration_ms": 0,
                    "warning": "",
                    "combined_output": f"Error: Unsupported file type {file_ext}"
                }

        except Exception as e:
            return {
                "ok": False,
                "engine": "unknown",
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "timed_out": False,
                "duration_ms": 0,
                "warning": "",
                "combined_output": f"Error executing code: {str(e)}"
            }

    def _execute_python_local(self, filename, docker_preferred=False):
        start = time.time()
        warning = ""
        if docker_preferred and not shutil.which('docker'):
            warning = "Docker not found, fallback to local Python runtime."

        env = os.environ.copy()
        env['PYTHONNOUSERSITE'] = '1'
        # 添加 workspace_dir 到 PYTHONPATH，使 Agent 代码能正确导入模块
        existing_pythonpath = env.get('PYTHONPATH', '')
        env['PYTHONPATH'] = f"{self.workspace_dir}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else self.workspace_dir

        try:
            result = subprocess.run(
                [sys.executable, filename],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                check=False,
            )
            return self._format_exec_result(
                ok=(result.returncode == 0),
                engine="local-subprocess",
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                timed_out=False,
                duration_ms=int((time.time() - start) * 1000),
                warning=warning,
            )
        except subprocess.TimeoutExpired as e:
            return self._format_exec_result(
                ok=False,
                engine="local-subprocess",
                return_code=-1,
                stdout=(e.stdout or ""),
                stderr=(e.stderr or ""),
                timed_out=True,
                duration_ms=int((time.time() - start) * 1000),
                warning=warning,
            )

    def _execute_python_in_docker(self, filename):
        start = time.time()
        workspace = self.workspace_dir
        cmd = [
            'docker', 'run', '--rm',
            '--network', 'none',
            '--cpus', '1.0',
            '--memory', '256m',
            '--pids-limit', '64',
            '--read-only',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
            '--security-opt', 'no-new-privileges',
            '--cap-drop', 'ALL',
            '-v', f'{workspace}:/workspace:rw',
            '-w', '/workspace',
            'python:3.12-alpine',
            'python', filename,
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            return self._format_exec_result(
                ok=(result.returncode == 0),
                engine="docker-python:3.12-alpine",
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                timed_out=False,
                duration_ms=int((time.time() - start) * 1000),
                warning="",
            )
        except subprocess.TimeoutExpired as e:
            return self._format_exec_result(
                ok=False,
                engine="docker-python:3.12-alpine",
                return_code=-1,
                stdout=(e.stdout or ""),
                stderr=(e.stderr or ""),
                timed_out=True,
                duration_ms=int((time.time() - start) * 1000),
                warning="",
            )
        except Exception as e:
            fallback = self._execute_python_local(filename, docker_preferred=True)
            fallback['warning'] = (fallback.get('warning') + f" Docker runtime failed: {str(e)}").strip()
            fallback['combined_output'] = self._build_combined_output(fallback)
            return fallback

    @staticmethod
    def _build_combined_output(payload):
        lines = [
            f"Engine: {payload.get('engine', 'unknown')}",
            f"Exit Code: {payload.get('return_code', -1)}",
            f"Duration: {payload.get('duration_ms', 0)}ms",
        ]
        if payload.get('timed_out'):
            lines.append("Timed Out: yes")
        if payload.get('warning'):
            lines.append(f"Warning: {payload.get('warning')}")
        lines.append("Output:")
        lines.append(payload.get('stdout') or "")
        if payload.get('stderr'):
            lines.append("Errors:")
            lines.append(payload.get('stderr') or "")
        return "\n".join(lines).strip()

    def _format_exec_result(self, ok, engine, return_code, stdout, stderr, timed_out, duration_ms, warning=""):
        payload = {
            "ok": bool(ok),
            "engine": engine,
            "return_code": int(return_code),
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": bool(timed_out),
            "duration_ms": int(duration_ms),
            "warning": warning or "",
        }
        payload["combined_output"] = self._build_combined_output(payload)
        return payload

    def execute_javascript_with_amala(self, code_str):
        """
        Execute JavaScript code in vm2-based sandbox environment.
        Supports both Node.js local runtime and Docker-based execution.
        """
        try:
            # Write code to temporary file
            filename = f"temp_js_{uuid.uuid4().hex[:8]}.js"
            script_path = os.path.join(self.workspace_dir, filename)
            self.write_file(script_path, code_str)

            from src.core.config import CONFIG
            wm_cfg = CONFIG.get('work_mode', {}) if isinstance(CONFIG, dict) else {}
            chat_settings = wm_cfg.get('chat_settings', {}) if isinstance(wm_cfg, dict) else {}
            prefer_docker = bool(chat_settings.get('sandbox_use_docker_runtime', True))

            # Try Docker first if preferred and available
            if prefer_docker and shutil.which('docker'):
                result = self._execute_javascript_in_docker(filename)
                if result.get('ok') or result.get('engine', '').startswith('docker'):
                    return result

            # Fallback to local Node.js execution
            return self._execute_javascript_in_vm2(filename, docker_preferred=prefer_docker)

        except Exception as e:
            return {
                "ok": False,
                "engine": "amala-sandbox",
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "timed_out": False,
                "duration_ms": 0,
                "warning": "",
                "combined_output": f"Error executing JavaScript: {str(e)}"
            }

    def _execute_javascript_in_vm2(self, filename, docker_preferred=False):
        """Execute JS code using local Node.js + vm2 sandbox runner."""
        start = time.time()
        warning = ""
        
        if docker_preferred and not shutil.which('docker'):
            warning = "Docker not found, fallback to local Node.js runtime."

        # Check if Node.js is available
        node_path = shutil.which('node')
        if not node_path:
            return self._format_exec_result(
                ok=False,
                engine="vm2-sandbox-local",
                return_code=-1,
                stdout="",
                stderr="Node.js not found. Install Node.js 16+ or enable Docker runtime.",
                timed_out=False,
                duration_ms=int((time.time() - start) * 1000),
                warning="Node.js runtime not available",
            )

# Path to vm2 sandbox runner
            runner_path = os.path.join(
                self.project_root, 'src', 'runtimes', 'amala-sandbox', 'runner.js'
            )

            if not os.path.exists(runner_path):
                return self._format_exec_result(
                    ok=False,
                    engine="vm2-sandbox-local",
                    return_code=-1,
                    stdout="",
                    stderr=f"vm2 sandbox runner not found at {runner_path}. Run: npm install in src/runtimes/amala-sandbox/",
                    timed_out=False,
                    duration_ms=int((time.time() - start) * 1000),
                    warning="vm2 sandbox not initialized",
            )

        script_full_path = os.path.join(self.workspace_dir, filename)
        
        try:
            result = subprocess.run(
                [node_path, runner_path, script_full_path, '30000'],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=35,
                check=False,
                env=os.environ.copy(),
            )

            # Parse JSON result from runner
            try:
                output = json.loads(result.stdout)
                output['warning'] = (output.get('warning', '') + ('; ' + warning if warning else '')).strip()
                return output
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return self._format_exec_result(
                    ok=(result.returncode == 0),
                    engine="vm2-sandbox-local",
                    return_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    timed_out=False,
                    duration_ms=int((time.time() - start) * 1000),
                    warning=warning,
                )

        except subprocess.TimeoutExpired as e:
            return self._format_exec_result(
                ok=False,
                engine="vm2-sandbox-local",
                return_code=-1,
                stdout=(e.stdout or ""),
                stderr=(e.stderr or ""),
                timed_out=True,
                duration_ms=int((time.time() - start) * 1000),
                warning="JavaScript execution exceeded timeout limit",
            )
        except Exception as e:
            return self._format_exec_result(
                ok=False,
                engine="vm2-sandbox-local",
                return_code=-1,
                stdout="",
                stderr=str(e),
                timed_out=False,
                duration_ms=int((time.time() - start) * 1000),
                warning="Local Node.js execution failed",
            )

    def _execute_javascript_in_docker(self, filename):
        """
        Execute JavaScript code in Docker with vm2 sandbox.
        Creates an isolated Node.js container for execution.
        """
        start = time.time()
        workspace = self.workspace_dir
        script_name = filename

        # Build Docker command for Node.js with amala-sandbox
        cmd = [
            'docker', 'run', '--rm',
            '--network', 'none',
            '--cpus', '1.0',
            '--memory', '256m',
            '--pids-limit', '32',
            '--read-only',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
            '--security-opt', 'no-new-privileges',
            '--cap-drop', 'ALL',
            '-v', f'{workspace}:/workspace:rw',
            '-w', '/workspace',
            '--entrypoint', 'sh',
            'node:20-alpine',
            '-c',
            f'npm install amala-sandbox 2>/dev/null && node -e "const {{Sandbox}} = require(\'amala-sandbox\'); const fs = require(\'fs\'); const code = fs.readFileSync(\'{script_name}\', \'utf-8\'); const sandbox = new Sandbox({{timeout: 30000}}); try {{ sandbox.run(code); console.log(JSON.stringify({{ok: true, return_code: 0, stdout: \'\', stderr: \'\'}})); }} catch(e) {{ console.log(JSON.stringify({{ok: false, return_code: 1, stderr: e.message}}))); }}"',
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )

            # Try to parse JSON output
            try:
                output = json.loads(result.stdout.strip().split('\n')[-1])
                output['engine'] = 'docker-node:20-alpine-vm2'
                output['duration_ms'] = int((time.time() - start) * 1000)
                output['timed_out'] = False
                output['combined_output'] = self._build_combined_output(output)
                return output
            except (json.JSONDecodeError, IndexError):
                # Fallback
                return self._format_exec_result(
                    ok=(result.returncode == 0),
                    engine="docker-node:20-alpine-vm2",
                    return_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    timed_out=False,
                    duration_ms=int((time.time() - start) * 1000),
                    warning="",
                )

        except subprocess.TimeoutExpired as e:
            return self._format_exec_result(
                ok=False,
                engine="docker-node:20-alpine-vm2",
                return_code=-1,
                stdout=(e.stdout or ""),
                stderr=(e.stderr or ""),
                timed_out=True,
                duration_ms=int((time.time() - start) * 1000),
                warning="Docker JavaScript execution exceeded timeout",
            )
        except Exception as e:
            # Fallback to local execution
            return self._execute_javascript_in_vm2(filename, docker_preferred=True)
