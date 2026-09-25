"""Python AST Code Chunker for SER.

Provides atomic function, class, and method chunking for Python codebases using the
standard library `ast` module (0 external dependencies).
"""

import ast
from typing import Optional
from ser.chunk import Chunk
from ser.ingest.models import Document


def _get_node_lines(code_lines: list[str], node: ast.AST) -> tuple[int, int, str]:
    """Returns (start_lineno_1based, end_lineno_1based, source_text) including decorators."""
    if hasattr(node, "decorator_list") and node.decorator_list:
        start_lineno = node.decorator_list[0].lineno
    elif hasattr(node, "lineno"):
        start_lineno = node.lineno
    else:
        start_lineno = 1

    end_lineno = getattr(node, "end_lineno", start_lineno)
    start_lineno = max(1, min(start_lineno, len(code_lines)))
    end_lineno = max(start_lineno, min(end_lineno, len(code_lines)))

    source_text = "\n".join(code_lines[start_lineno - 1 : end_lineno]).strip()
    return start_lineno, end_lineno, source_text


def _split_oversized_code(
    header_context: str,
    body_text: str,
    doc_id: str,
    title: str,
    url: str,
    breadcrumb: str,
    start_index: int,
    chunk_size: int = 1200,
    overlap: int = 0,
    content_hash: str = "",
) -> tuple[list[Chunk], int]:
    """Splits an oversized code block along line boundaries without duplicating statements across parts."""
    chunks: list[Chunk] = []
    lines = body_text.splitlines()
    curr_idx = start_index

    if not lines:
        return chunks, curr_idx

    current_part: list[str] = []
    current_len = len(header_context)

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > chunk_size and current_part:
            part_body = "\n".join(current_part).strip("\r\n")
            full_text = f"{header_context}\n{part_body}" if header_context else part_body
            chk = Chunk(
                chunk_id=f"{doc_id}-{curr_idx}",
                doc_id=doc_id,
                title=title,
                url=url,
                chunk_index=curr_idx,
                text=full_text,
                breadcrumb=f"{breadcrumb} (part {len(chunks) + 1})",
                source_type="code",
                content_hash=content_hash,
            )
            chunks.append(chk)
            curr_idx += 1
            current_part = []
            current_len = len(header_context)

        current_part.append(line)
        current_len += line_len

    if current_part:
        part_body = "\n".join(current_part).strip("\r\n")
        full_text = f"{header_context}\n{part_body}" if header_context else part_body
        chk = Chunk(
            chunk_id=f"{doc_id}-{curr_idx}",
            doc_id=doc_id,
            title=title,
            url=url,
            chunk_index=curr_idx,
            text=full_text,
            breadcrumb=f"{breadcrumb} (part {len(chunks) + 1})" if chunks else breadcrumb,
            source_type="code",
            content_hash=content_hash,
        )
        chunks.append(chk)
        curr_idx += 1

    return chunks, curr_idx


def chunk_python_ast(
    doc: Document, chunk_size: int = 1200, overlap: int = 0
) -> list[Chunk]:
    """Parses a Python document using standard library `ast` into atomic units.

    Emits:
    1. Module Preamble (docstring, imports, module-level constants).
    2. Atomic Functions (with decorators, full signature, and docstrings).
    3. Atomic Classes or Method-level units (with enclosing class header context).
    """
    code = doc.text
    code_lines = code.splitlines()
    doc_id = doc.page_id
    title = doc.title
    url = doc.url
    content_hash = getattr(doc, "content_hash", "")

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fall back to line-based sliding window if code has invalid syntax
        chunks, _ = _split_oversized_code(
            header_context="",
            body_text=code.strip(),
            doc_id=doc_id,
            title=title,
            url=url,
            breadcrumb=f"{title} > Source",
            start_index=0,
            chunk_size=chunk_size,
            overlap=0,
            content_hash=content_hash,
        )
        return chunks

    chunks: list[Chunk] = []
    chunk_index = 0

    # 1. Extract Module Preamble (docstring + imports + global assignments before first function/class)
    preamble_parts: list[str] = []
    module_docstring = ast.get_docstring(tree)
    if module_docstring:
        preamble_parts.append(f'"""{module_docstring}"""')

    first_def_lineno: Optional[int] = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first_def_lineno = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            break

    preamble_end_line = (first_def_lineno - 1) if first_def_lineno else len(code_lines)
    if preamble_end_line > 0:
        non_doc_lines = [
            line for line in code_lines[:preamble_end_line]
            if line.strip() and not line.strip().startswith(('"""', "'''", "#"))
        ]
        if non_doc_lines:
            raw_preamble = "\n".join(code_lines[:preamble_end_line]).strip()
            preamble_parts.append(raw_preamble)

    if preamble_parts:
        preamble_text = "\n\n".join(preamble_parts).strip()
        if len(preamble_text) >= 20:
            if len(preamble_text) <= chunk_size:
                chk = Chunk(
                    chunk_id=f"{doc_id}-{chunk_index}",
                    doc_id=doc_id,
                    title=title,
                    url=url,
                    chunk_index=chunk_index,
                    text=preamble_text,
                    breadcrumb=f"{title} > Module Preamble",
                    source_type="code",
                    content_hash=content_hash,
                )
                chunks.append(chk)
                chunk_index += 1
            else:
                p_chunks, chunk_index = _split_oversized_code(
                    header_context="",
                    body_text=preamble_text,
                    doc_id=doc_id,
                    title=title,
                    url=url,
                    breadcrumb=f"{title} > Module Preamble",
                    start_index=chunk_index,
                    chunk_size=chunk_size,
                    overlap=0,
                    content_hash=content_hash,
                )
                chunks.extend(p_chunks)

    # 2. Process top-level Classes and Functions
    CLASS_ATOMIC_THRESHOLD = 1500

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _, _, fn_source = _get_node_lines(code_lines, node)
            breadcrumb = f"{title} > def {node.name}()"

            if len(fn_source) <= chunk_size:
                chk = Chunk(
                    chunk_id=f"{doc_id}-{chunk_index}",
                    doc_id=doc_id,
                    title=title,
                    url=url,
                    chunk_index=chunk_index,
                    text=fn_source,
                    breadcrumb=breadcrumb,
                    source_type="code",
                    content_hash=content_hash,
                )
                chunks.append(chk)
                chunk_index += 1
            else:
                # Oversized function: extract signature header and chunk body
                fn_lines = fn_source.splitlines()
                sig_lines = []
                for l in fn_lines:
                    sig_lines.append(l)
                    if l.rstrip().endswith(":"):
                        break
                header_context = "\n".join(sig_lines)
                body_remainder = "\n".join(fn_lines[len(sig_lines):])

                f_chunks, chunk_index = _split_oversized_code(
                    header_context=header_context,
                    body_text=body_remainder,
                    doc_id=doc_id,
                    title=title,
                    url=url,
                    breadcrumb=breadcrumb,
                    start_index=chunk_index,
                    chunk_size=chunk_size,
                    overlap=0,
                    content_hash=content_hash,
                )
                chunks.extend(f_chunks)

        elif isinstance(node, ast.ClassDef):
            _, _, class_source = _get_node_lines(code_lines, node)
            class_breadcrumb = f"{title} > class {node.name}"

            # If small class (e.g. dataclass, model, enum), keep intact as 1 atomic chunk
            if len(class_source) <= CLASS_ATOMIC_THRESHOLD:
                chk = Chunk(
                    chunk_id=f"{doc_id}-{chunk_index}",
                    doc_id=doc_id,
                    title=title,
                    url=url,
                    chunk_index=chunk_index,
                    text=class_source,
                    breadcrumb=class_breadcrumb,
                    source_type="code",
                    content_hash=content_hash,
                )
                chunks.append(chk)
                chunk_index += 1
            else:
                # Class exceeds threshold: extract class preamble/overview + individual methods
                first_method_line: Optional[int] = None
                methods: list[ast.AST] = []

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if first_method_line is None:
                            first_method_line = item.decorator_list[0].lineno if item.decorator_list else item.lineno
                        methods.append(item)

                class_start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
                class_header_end = (first_method_line - 1) if first_method_line else node.end_lineno
                class_header_text = "\n".join(code_lines[class_start_line - 1 : class_header_end]).strip()

                if len(class_header_text) >= 20:
                    chk = Chunk(
                        chunk_id=f"{doc_id}-{chunk_index}",
                        doc_id=doc_id,
                        title=title,
                        url=url,
                        chunk_index=chunk_index,
                        text=class_header_text,
                        breadcrumb=f"{class_breadcrumb} (Overview)",
                        source_type="code",
                        content_hash=content_hash,
                    )
                    chunks.append(chk)
                    chunk_index += 1

                # Individual methods
                for m in methods:
                    _, _, m_source = _get_node_lines(code_lines, m)
                    m_breadcrumb = f"{class_breadcrumb} > def {m.name}()"
                    method_with_context = f"# class {node.name}\n{m_source}"

                    if len(method_with_context) <= chunk_size:
                        chk = Chunk(
                            chunk_id=f"{doc_id}-{chunk_index}",
                            doc_id=doc_id,
                            title=title,
                            url=url,
                            chunk_index=chunk_index,
                            text=method_with_context,
                            breadcrumb=m_breadcrumb,
                            source_type="code",
                            content_hash=content_hash,
                        )
                        chunks.append(chk)
                        chunk_index += 1
                    else:
                        m_chunks, chunk_index = _split_oversized_code(
                            header_context=f"# class {node.name}",
                            body_text=m_source,
                            doc_id=doc_id,
                            title=title,
                            url=url,
                            breadcrumb=m_breadcrumb,
                            start_index=chunk_index,
                            chunk_size=chunk_size,
                            overlap=0,
                            content_hash=content_hash,
                        )
                        chunks.extend(m_chunks)

    # Fallback if no functions/classes found
    if not chunks and len(code.strip()) >= 20:
        chunks, _ = _split_oversized_code(
            header_context="",
            body_text=code.strip(),
            doc_id=doc_id,
            title=title,
            url=url,
            breadcrumb=f"{title} > Script",
            start_index=0,
            chunk_size=chunk_size,
            overlap=0,
            content_hash=content_hash,
        )

    return chunks


# Backward-compatible alias
chunk_code = chunk_python_ast
