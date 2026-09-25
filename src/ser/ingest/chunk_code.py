"""AST and Syntax-Aware Code Chunker for SER.

Provides atomic function, class, and method chunking for Python codebases using the
standard library `ast` module, as well as syntax-aware block extraction for polyglot
languages (.rs, .ts, .js, .go, .c, .cpp).
"""

import ast
import re
from typing import Optional
from ser.chunk import Chunk
from ser.ingest.models import Document

# Regex patterns for polyglot top-level definitions
_POLYGLOT_BLOCK_RE = re.compile(
    r"^(?:(?:\b(?:pub|export|default|async|static|inline|virtual|override|explicit)\s+)*)"
    r"(?:fn|function|func|class|struct|enum|trait|interface|impl|namespace|type)\b",
    re.MULTILINE,
)


def _get_node_lines(code_lines: list[str], node: ast.AST) -> tuple[int, int, str]:
    """Returns (start_lineno_1based, end_lineno_1based, source_text) including decorators."""
    if hasattr(node, "decorator_list") and node.decorator_list:
        start_lineno = node.decorator_list[0].lineno
    elif hasattr(node, "lineno"):
        start_lineno = node.lineno
    else:
        start_lineno = 1

    end_lineno = getattr(node, "end_lineno", start_lineno)
    # Clamp to valid line numbers
    start_lineno = max(1, min(start_lineno, len(code_lines)))
    end_lineno = max(start_lineno, min(end_lineno, len(code_lines)))

    source_text = "\n".join(code_lines[start_lineno - 1 : end_lineno]).strip()
    return start_lineno, end_lineno, source_text


def _count_code_braces(line: str, state: dict) -> tuple[int, int]:
    """Lexical brace counter that ignores braces inside comments, strings, template literals, and raw literals."""
    opens = 0
    closes = 0
    i = 0
    n = len(line)

    if "stack" not in state:
        state["stack"] = []
    if "depth" not in state:
        state["depth"] = 0

    stack = state["stack"]

    while i < n:
        c = line[i]
        nxt = line[i + 1] if i + 1 < n else ""
        current_ctx = stack[-1] if stack else None
        ctx_name = current_ctx[0] if isinstance(current_ctx, tuple) else current_ctx

        # 1. Block comment mode (/* ... */)
        if ctx_name == "BLOCK_COMMENT":
            if c == "*" and nxt == "/":
                stack.pop()
                i += 2
                continue
            i += 1
            continue

        # 2. C++ raw string R"( ... )" or Rust raw string r#" ... "#
        if ctx_name == "RAW_STRING":
            if (c == ")" and nxt == '"') or (c == '"' and nxt == "#"):
                stack.pop()
                i += 2
                continue
            i += 1
            continue

        # 3. Regular strings
        if ctx_name in ("STRING_DOUBLE", "STRING_SINGLE"):
            if c == "\\":
                i += 2
                continue
            if (ctx_name == "STRING_DOUBLE" and c == '"') or (ctx_name == "STRING_SINGLE" and c == "'"):
                stack.pop()
            i += 1
            continue

        # 4. JS/TS Template literals ` ... ${ ... } ... `
        if ctx_name == "TEMPLATE_STR":
            if c == "\\":
                i += 2
                continue
            if c == "`":
                stack.pop()
                i += 1
                continue
            if c == "$" and nxt == "{":
                stack.append(("TEMPLATE_EXPR", state["depth"] + opens - closes))
                i += 2
                continue
            i += 1
            continue

        # 5. Code mode
        if c == "/" and nxt == "/":
            break  # Single-line comment, rest of line ignored
        if c == "/" and nxt == "*":
            stack.append("BLOCK_COMMENT")
            i += 2
            continue

        # Raw string literal start (C++ R"( or Rust r#")
        if (c == "R" and nxt == '"' and i + 2 < n and line[i + 2] == "(") or (
            c == "r" and nxt == "#" and i + 2 < n and line[i + 2] == '"'
        ):
            stack.append("RAW_STRING")
            i += 3
            continue

        if c == '"':
            stack.append("STRING_DOUBLE")
            i += 1
            continue
        if c == "'":
            # Disambiguate Rust lifetime 'a or char literal 'x'
            if i + 2 < n and line[i + 2] == "'":
                i += 3
                continue
            elif i + 1 < n and line[i + 1].isalpha() and (i + 2 >= n or not line[i + 2].isalpha()):
                i += 2
                continue
            else:
                stack.append("STRING_SINGLE")
                i += 1
                continue
        if c == "`":
            stack.append("TEMPLATE_STR")
            i += 1
            continue

        # Real code braces
        if c == "{":
            opens += 1
        elif c == "}":
            cur_depth = state["depth"] + opens - closes
            if ctx_name == "TEMPLATE_EXPR" and cur_depth <= current_ctx[1]:
                stack.pop()
            else:
                closes += 1
        i += 1

    state["depth"] += (opens - closes)
    return opens, closes


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
    """Splits an oversized code block along line boundaries, preserving the header context on each part."""
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

            # Retain overlap lines if possible
            overlap_lines: list[str] = []
            overlap_len = 0
            for prev_line in reversed(current_part):
                if overlap_len + len(prev_line) > overlap:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_len += len(prev_line) + 1

            current_part = list(overlap_lines)
            current_len = len(header_context) + overlap_len

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
    doc: Document, chunk_size: int = 1200, overlap: int = 200
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
        # Fall back to polyglot boundary chunker if code contains syntax errors
        return chunk_polyglot_code(doc, chunk_size=chunk_size, overlap=overlap)

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

    # Preamble lines before first function or class
    preamble_end_line = (first_def_lineno - 1) if first_def_lineno else len(code_lines)
    if preamble_end_line > 0:
        raw_preamble = "\n".join(code_lines[:preamble_end_line]).strip()
        if raw_preamble and raw_preamble != preamble_parts[0] if preamble_parts else True:
            # Only include if there's actual logic/imports (not just blank lines or standalone docstring)
            non_doc_lines = [
                line for line in code_lines[:preamble_end_line]
                if line.strip() and not line.strip().startswith(('"""', "'''", "#"))
            ]
            if non_doc_lines:
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
                    overlap=overlap,
                    content_hash=content_hash,
                )
                chunks.extend(p_chunks)

    # 2. Process top-level Classes and Functions
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
                    overlap=overlap,
                    content_hash=content_hash,
                )
                chunks.extend(f_chunks)

        elif isinstance(node, ast.ClassDef):
            _, _, class_source = _get_node_lines(code_lines, node)
            class_breadcrumb = f"{title} > class {node.name}"

            # If small class (e.g. dataclass, model, enum), keep intact as 1 atomic chunk
            if len(class_source) <= chunk_size:
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
                # Class exceeds chunk size: extract class preamble/overview + individual methods
                class_doc = ast.get_docstring(node)
                first_method_line: Optional[int] = None
                methods: list[ast.AST] = []

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if first_method_line is None:
                            first_method_line = item.decorator_list[0].lineno if item.decorator_list else item.lineno
                        methods.append(item)

                # Class overview chunk: class header, docstring, and any class-level variables
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
                    # Prepend enclosing class declaration so the method retains its structural home
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
                            overlap=overlap,
                            content_hash=content_hash,
                        )
                        chunks.extend(m_chunks)

    # If the file had no top-level functions/classes (e.g. pure script or config), chunk by double newlines
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
            overlap=overlap,
            content_hash=content_hash,
        )

    return chunks


def chunk_polyglot_code(
    doc: Document, chunk_size: int = 1200, overlap: int = 0
) -> list[Chunk]:
    """Chunker for non-Python languages (Rust, TypeScript, Go, C/C++) using block & lexical brace matching."""
    code = doc.text
    lines = code.splitlines()
    doc_id = doc.page_id
    title = doc.title
    url = doc.url
    content_hash = getattr(doc, "content_hash", "")

    if len(code.strip()) < 20:
        return []

    chunks: list[Chunk] = []
    chunk_index = 0

    # Scan for top-level block boundaries via indentation 0 and lexical brace balancing
    blocks: list[tuple[str, str]] = []  # (breadcrumb_hint, block_text)
    current_block: list[str] = []
    current_breadcrumb = f"{title} > Preamble"
    brace_depth = 0
    in_block = False
    lex_state: dict = {}

    for line in lines:
        stripped = line.strip()
        open_braces, close_braces = _count_code_braces(line, lex_state)

        # Check if line initiates a top-level block at indentation 0
        if not in_block and (
            line.startswith((
                "pub ", "export ", "async ", "fn ", "function ", "func ",
                "class ", "struct ", "impl", "trait ", "interface ", "type ",
                "template ", "namespace ", "inline ", "static ", "enum ",
                "#[", "macro_rules!", "int main", "void ", "bool ", "auto "
            ))
            or (open_braces > 0 and not line.startswith(" "))
        ):
            if current_block:
                block_body = "\n".join(current_block).strip()
                if len(block_body) >= 20:
                    blocks.append((current_breadcrumb, block_body))
                current_block = []

            in_block = True
            # Build breadcrumb hint from declaration line (up to opening brace or 60 chars)
            hint = stripped.split("{")[0].strip()
            current_breadcrumb = f"{title} > {hint[:50]}"

        current_block.append(line)
        brace_depth += open_braces - close_braces

        # Block terminates when brace depth returns to 0
        if in_block and brace_depth <= 0 and (open_braces > 0 or close_braces > 0):
            block_body = "\n".join(current_block).strip()
            if len(block_body) >= 20:
                blocks.append((current_breadcrumb, block_body))
            current_block = []
            in_block = False
            brace_depth = 0
            current_breadcrumb = f"{title} > Code"

    if current_block:
        block_body = "\n".join(current_block).strip()
        if len(block_body) >= 20:
            blocks.append((current_breadcrumb, block_body))

    # Convert detected blocks into chunks, splitting oversized blocks if necessary
    for bcrumb, body in blocks:
        if len(body) <= chunk_size:
            chk = Chunk(
                chunk_id=f"{doc_id}-{chunk_index}",
                doc_id=doc_id,
                title=title,
                url=url,
                chunk_index=chunk_index,
                text=body,
                breadcrumb=bcrumb,
                source_type="code",
                content_hash=content_hash,
            )
            chunks.append(chk)
            chunk_index += 1
        else:
            b_chunks, chunk_index = _split_oversized_code(
                header_context="",
                body_text=body,
                doc_id=doc_id,
                title=title,
                url=url,
                breadcrumb=bcrumb,
                start_index=chunk_index,
                chunk_size=chunk_size,
                overlap=overlap,
                content_hash=content_hash,
            )
            chunks.extend(b_chunks)

    # Fallback if no blocks were parsed
    if not chunks:
        chunks, _ = _split_oversized_code(
            header_context="",
            body_text=code.strip(),
            doc_id=doc_id,
            title=title,
            url=url,
            breadcrumb=f"{title} > Source",
            start_index=0,
            chunk_size=chunk_size,
            overlap=overlap,
            content_hash=content_hash,
        )

    return chunks


def chunk_code(
    doc: Document, chunk_size: int = 1200, overlap: int = 200
) -> list[Chunk]:
    """Dispatches code document chunking based on file extension."""
    title_lower = (doc.title or "").lower()
    url_lower = (doc.url or "").lower()

    if title_lower.endswith(".py") or url_lower.endswith(".py"):
        return chunk_python_ast(doc, chunk_size=chunk_size, overlap=overlap)
    else:
        return chunk_polyglot_code(doc, chunk_size=chunk_size, overlap=overlap)
