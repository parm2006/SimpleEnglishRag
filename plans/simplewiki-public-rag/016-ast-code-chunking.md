# 016 — AST-Based Code Chunking

Status: READY TO EXECUTE. Dependencies: 004, 015.
Outcome: Replace naive character-sliding windowing on code files with AST-aware and syntax-boundary chunking. Preserves complete atomic units of meaning (functions, methods, classes, signatures, and docstrings) with contextual breadcrumbs (`file.py > class ClassName > def method_name()`) and zero external dependencies.

---

## 1. Problem & Motivation

Currently, when `ser add` ingests code files (`.py`, `.rs`, `.ts`, `.cpp`, `.go`), the router wraps the entire file in a fenced code block under a single top-level header (`# File: name.ext`). The generic chunker then splits it every 1,200 characters with a 200-character sliding window.

For real codebases, this naive splitting produces several severe retrieval defects:
1. **Severed Functions**: Functions spanning >40 lines are split mid-body or mid-loop, destroying semantic completeness.
2. **Orphaned Bodies**: A chunk containing a function's implementation often lacks its signature, parameter types, and docstring.
3. **Lost Class Hierarchy**: Class methods retrieved in isolation lose the context of the enclosing class name, class docstring, and member variables.
4. **Syntax Fragmentation**: Incomplete syntax trees confuse LLMs attempting to reason over or cite retrieved code.

---

## 2. Core Architecture & Dispatch

```
src/ser/ingest/
  handlers/
    text.py          # Detects CODE_EXTS, assigns source_type="code"
  chunk_code.py      # AST-aware chunking dispatcher
    ├── chunk_python_ast(doc, chunk_size, overlap)     # stdlib `ast` parser (0 deps)
    └── chunk_polyglot_code(doc, chunk_size, overlap)  # Brace/regex boundary parser
```

When `create_chunks(doc)` in `src/ser/chunk.py` encounters `doc.source_type == "code"`:
- If file extension is `.py` $\to$ dispatches to `chunk_python_ast()`.
- If file extension is in `{".rs", ".ts", ".js", ".jsx", ".tsx", ".go", ".c", ".cpp", ".h", ".hpp", ".java"}` $\to$ dispatches to `chunk_polyglot_code()`.
- If parsing encounters a syntax error or unsupported format $\to$ falls back gracefully to indentation/block windowing without failing.

---

## 3. Python AST Specification (`chunk_python_ast`)

Built exclusively on Python's standard library **`ast`** module (0 MB download, native C speed in CPython):

### A. Module Preamble Chunk
- Collects:
  - File-level docstring (`ast.get_docstring(tree)`).
  - All top-level imports (`ast.Import`, `ast.ImportFrom`).
  - Top-level constants and type aliases (`ast.Assign`, `ast.AnnAssign`).
- Breadcrumb: `{doc.title} > Module Preamble`
- Emitted as chunk index `0` if non-empty.

### B. Standalone Functions (`ast.FunctionDef`, `ast.AsyncFunctionDef`)
- Line range: `decorator_list[0].lineno` (if decorated) to `node.end_lineno`.
- Extracted verbatim via line slicing to preserve exact indentation, comments, and formatting.
- Breadcrumb: `{doc.title} > def {node.name}()`
- If function length $\le$ `chunk_size` (1,200 chars), emitted as a single atomic chunk.
- If function is oversized (>1,200 chars), chunked internally along statement/block boundaries while retaining the function signature and docstring header.

### C. Classes & Methods (`ast.ClassDef`)
- If the entire class fits within `chunk_size` (e.g. `@dataclass class Document:`):
  - Emitted as an atomic class chunk.
  - Breadcrumb: `{doc.title} > class {node.name}`
- If the class exceeds `chunk_size`:
  1. **Class Preamble Chunk**:
     - Decorators, class signature, base classes, class-level docstring, and class attributes.
     - Breadcrumb: `{doc.title} > class {node.name} (Overview)`
  2. **Individual Method Chunks**:
     - For each method (`FunctionDef` / `AsyncFunctionDef` inside `node.body`):
       - Prefixed with class context header: `# class {node.name}\n`
       - Includes full method decorators, signature, docstrings, and body.
       - Breadcrumb: `{doc.title} > class {class_name} > def {method_name}()`

---

## 4. Polyglot Code Specification (`chunk_polyglot_code`)

For Rust, TypeScript, JavaScript, Go, and C/C++:
1. Fast regex scanner detecting top-level block declarations:
   - Rust: `pub fn`, `fn`, `impl`, `struct`, `enum`, `trait`
   - TypeScript / JS: `export function`, `function`, `class`, `interface`, `type`, `const ... = (...) =>`
   - Go: `func (...)`, `func`, `type ... struct`, `type ... interface`
   - C / C++: function definitions with return types, `class`, `struct`, `namespace`
2. Brace matching (`{` / `}`) tracking block nesting depth:
   - Level 0 $\to$ Level 1 transition identifies the start of an atomic block.
   - Return to Level 0 identifies the end of the block.
3. Breadcrumb extracted from declaration signature.
4. Fallback to double-newline / paragraph sliding window if braces are unbalanced.

---

## 5. Verification & Acceptance Criteria

1. **Self-Ingestion Test**:
   - Run `ser add src/ser/pipeline.py` or `ser add src/ser/db.py`.
   - Inspect generated chunks in Qdrant:
     - Verify `get_client`, `init_collection`, `insert_points`, and `search_query` each exist as complete, unsevered functions.
     - Verify breadcrumbs match `db.py > def init_collection()`.
2. **Retrieval Precision Test**:
   - Query: `ser search "retry wrapper for upserting points into Qdrant"`
   - Must retrieve the unsevered `insert_points` function with its docstring and `max_retries` loop intact.
3. **Zero New Dependencies**:
   - No `tree-sitter` binaries, no C compilation steps, fully cross-platform and instant on Windows ARM64.
