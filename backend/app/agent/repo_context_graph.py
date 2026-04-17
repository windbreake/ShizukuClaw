# -*- coding: utf-8 -*-
"""Token-efficient repository context retrieval via a lightweight code context graph."""

import ast
import hashlib
import os
import pickle
import re
import threading
import time
from collections import defaultdict, deque


class CodeContextGraph:
    """Builds a compact repository graph and retrieves relevant code snippets."""

    KEYWORD_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
    CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")

    def __init__(self, project_root, source_dir="src"):
        self.project_root = project_root
        self.source_dir = os.path.join(project_root, source_dir)
        from app.core.config import DATA_DIR
        self.cache_dir = os.path.join(DATA_DIR, "cache")
        self.index_cache_path = os.path.join(self.cache_dir, "repo_context_graph_index.pkl")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._last_build_ts = 0.0
        self._cache_ttl_seconds = 30.0
        self._query_cache_ttl_seconds = 20.0
        self._query_cache = {}

        self.files = {}
        self.module_to_file = {}
        self.inverted_symbols = defaultdict(set)
        self.inverted_path_terms = defaultdict(set)
        self.import_graph = defaultdict(set)
        self._index_signature = ""

    def _iter_python_files(self):
        if not os.path.isdir(self.source_dir):
            return
        for root, _, filenames in os.walk(self.source_dir):
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                yield os.path.join(root, name)

    def _scan_python_file_stats(self):
        stats = []
        for abs_path in self._iter_python_files() or []:
            try:
                st = os.stat(abs_path)
                rel_path = os.path.relpath(abs_path, self.project_root).replace("\\", "/")
                stats.append((rel_path, float(st.st_mtime), int(st.st_size), abs_path))
            except Exception:
                continue
        stats.sort(key=lambda x: x[0])
        return stats

    @staticmethod
    def _compute_signature(file_stats):
        h = hashlib.sha1()
        for rel_path, mtime, size, _ in file_stats:
            h.update(rel_path.encode("utf-8", errors="ignore"))
            h.update(str(mtime).encode("utf-8"))
            h.update(str(size).encode("utf-8"))
        return h.hexdigest()

    def _load_index_cache(self, signature):
        try:
            if not os.path.exists(self.index_cache_path):
                return False
            with open(self.index_cache_path, "rb") as f:
                payload = pickle.load(f)
            if not isinstance(payload, dict):
                return False
            if payload.get("signature") != signature:
                return False

            self.files = payload.get("files", {}) or {}
            self.module_to_file = payload.get("module_to_file", {}) or {}
            self.inverted_symbols = defaultdict(set, payload.get("inverted_symbols", {}) or {})
            self.inverted_path_terms = defaultdict(set, payload.get("inverted_path_terms", {}) or {})
            self.import_graph = defaultdict(set, payload.get("import_graph", {}) or {})
            self._index_signature = signature
            self._last_build_ts = time.time()
            return True
        except Exception:
            return False

    def _save_index_cache(self, signature):
        try:
            payload = {
                "signature": signature,
                "files": self.files,
                "module_to_file": self.module_to_file,
                "inverted_symbols": dict(self.inverted_symbols),
                "inverted_path_terms": dict(self.inverted_path_terms),
                "import_graph": dict(self.import_graph),
                "saved_at": time.time(),
            }
            with open(self.index_cache_path, "wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            # 缓存失败不影响主流程
            return

    @staticmethod
    def _rel_module_from_path(base_src, abs_path):
        rel = os.path.relpath(abs_path, base_src).replace("\\", "/")
        if rel.endswith("/__init__.py"):
            rel = rel[:-12]
        elif rel.endswith(".py"):
            rel = rel[:-3]
        return rel.replace("/", ".")

    @staticmethod
    def _extract_path_terms(rel_path):
        rel_path = rel_path.replace("\\", "/")
        terms = set()
        for part in re.split(r"[/._-]+", rel_path.lower()):
            if len(part) >= 3:
                terms.add(part)
        return terms

    @staticmethod
    def _safe_read_text(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _index_file(self, file_path):
        rel_path = os.path.relpath(file_path, self.project_root).replace("\\", "/")
        text = self._safe_read_text(file_path)
        if not text:
            return None

        symbols = set()
        imports = set()
        lines = text.splitlines()
        def_spans = []

        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.add(node.name)
                    start = max(1, int(getattr(node, "lineno", 1)))
                    end = int(getattr(node, "end_lineno", start))
                    def_spans.append({"name": node.name, "start": start, "end": max(start, end)})
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name:
                            imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module:
                        imports.add(module)
        except Exception:
            pass

        module = self._rel_module_from_path(self.source_dir, file_path)
        mtime = os.path.getmtime(file_path)

        lexemes = set()
        for sym in symbols:
            lexemes.add(sym.lower())
        for term in self._extract_path_terms(rel_path):
            lexemes.add(term)
        for token in self.KEYWORD_PATTERN.findall(text.lower()):
            if len(token) >= 3:
                lexemes.add(token)

        return {
            "rel_path": rel_path,
            "module": module,
            "symbols": symbols,
            "imports": imports,
            "lines": lines,
            "def_spans": def_spans,
            "lexemes": lexemes,
            "mtime": mtime,
        }

    def build(self, force=False):
        with self._lock:
            now = time.time()
            if not force and self.files and (now - self._last_build_ts) < self._cache_ttl_seconds:
                return

            file_stats = self._scan_python_file_stats()
            signature = self._compute_signature(file_stats)

            if not force and self._load_index_cache(signature):
                return

            files = {}
            module_to_file = {}
            inverted_symbols = defaultdict(set)
            inverted_path_terms = defaultdict(set)
            import_graph = defaultdict(set)

            for _, _, _, abs_path in file_stats:
                node = self._index_file(abs_path)
                if not node:
                    continue

                rel_path = node["rel_path"]
                files[rel_path] = node
                module_to_file[node["module"]] = rel_path

                for sym in node["symbols"]:
                    inverted_symbols[sym.lower()].add(rel_path)
                for term in self._extract_path_terms(rel_path):
                    inverted_path_terms[term].add(rel_path)

            for rel_path, node in files.items():
                deps = self._resolve_imports(node.get("imports", set()), module_to_file)
                for dep in deps:
                    import_graph[rel_path].add(dep)
                    import_graph[dep].add(rel_path)

            self.files = files
            self.module_to_file = module_to_file
            self.inverted_symbols = inverted_symbols
            self.inverted_path_terms = inverted_path_terms
            self.import_graph = import_graph
            self._index_signature = signature
            self._last_build_ts = now
            self._save_index_cache(signature)

    def _resolve_imports(self, imports, module_to_file=None):
        module_to_file = module_to_file or self.module_to_file
        out = set()
        for imp in imports:
            imp = (imp or "").strip()
            if not imp:
                continue
            if imp in module_to_file:
                out.add(module_to_file[imp])
                continue
            parts = imp.split(".")
            while len(parts) > 1:
                parts = parts[:-1]
                parent = ".".join(parts)
                if parent in module_to_file:
                    out.add(module_to_file[parent])
                    break
        return out

    def _extract_query_terms(self, query):
        q = (query or "").strip().lower()
        raw_terms = self.KEYWORD_PATTERN.findall(q)
        stop = {
            "the", "and", "with", "that", "this", "from", "into", "what", "when", "where",
            "user", "please", "help", "code", "python", "system", "chat", "agent"
        }
        terms = []
        for t in raw_terms:
            if t in stop:
                continue
            if t not in terms:
                terms.append(t)

        # Minimal bilingual mapping for common coding intents in Chinese prompts.
        zh_map = {
            "记忆": ["memory"],
            "上下文": ["context"],
            "压缩": ["compress", "compression"],
            "检索": ["retrieve", "retrieval", "search"],
            "工具": ["tool"],
            "计划": ["plan", "planner"],
            "插件": ["plugin"],
            "技能": ["skill"],
            "数据库": ["database", "db"],
            "路径": ["path"],
        }
        cjk_terms = self.CJK_PATTERN.findall(q)
        for z in cjk_terms:
            for key, mapped in zh_map.items():
                if key in z:
                    for m in mapped:
                        if m not in terms:
                            terms.append(m)
        return terms[:12]

    def _fallback_content_scores(self, query, terms):
        scores = defaultdict(float)
        raw_cjk_terms = self.CJK_PATTERN.findall((query or "").strip())
        content_terms = [t for t in terms if len(t) >= 3]

        for rel_path, node in self.files.items():
            lexemes = node.get("lexemes", set())
            if not lexemes:
                continue

            local_score = 0.0
            for t in content_terms:
                if t in lexemes:
                    local_score += 1.2

            # If user query is Chinese, keep a weak lexical fallback via path and symbol hits.
            if raw_cjk_terms:
                for t in content_terms:
                    if t in rel_path.lower():
                        local_score += 0.8

            if local_score > 0:
                scores[rel_path] = local_score

        return scores

    @staticmethod
    def _collect_windows(lines, term_set, max_windows=2, radius=4):
        hits = []
        for idx, line in enumerate(lines):
            low = line.lower()
            if any(term in low for term in term_set):
                hits.append(idx)
        if not hits:
            return [(0, min(len(lines), 20))]

        windows = []
        for idx in hits[:max_windows]:
            left = max(0, idx - radius)
            right = min(len(lines), idx + radius + 1)
            windows.append((left, right))
        return windows

    def _format_snippet(self, rel_path, lines, terms, def_spans=None):
        term_set = set(terms)
        windows = []

        # Fine-grained selection: prefer function/class spans relevant to terms.
        if def_spans:
            ranked_spans = []
            for span in def_spans:
                name = (span.get("name") or "").lower()
                start = int(span.get("start", 1))
                end = int(span.get("end", start))
                score = 0.0
                for t in term_set:
                    if t in name:
                        score += 2.5
                if 1 <= start <= len(lines):
                    head_line = lines[start - 1].lower()
                    for t in term_set:
                        if t in head_line:
                            score += 1.0
                ranked_spans.append((score, start, end))

            ranked_spans.sort(key=lambda x: x[0], reverse=True)
            for score, start, end in ranked_spans[:2]:
                if score <= 0:
                    continue
                left = max(0, start - 1)
                right = min(len(lines), end)
                windows.append((left, right))

        if not windows:
            windows = self._collect_windows(lines, term_set)

        snippet_parts = []
        for left, right in windows:
            chunk = lines[left:right]
            numbered = [f"{left + i + 1:04d}: {text}" for i, text in enumerate(chunk)]
            snippet_parts.append("\n".join(numbered))
        snippet_text = "\n...\n".join(snippet_parts)
        return f"### {rel_path}\n```python\n{snippet_text}\n```\n"

    def _shortest_hops_to_seeds(self, seeds, max_hop=4):
        if not seeds:
            return {}
        dist = {}
        q = deque()
        for s in seeds:
            dist[s] = 0
            q.append(s)

        while q:
            curr = q.popleft()
            hop = dist[curr]
            if hop >= max_hop:
                continue
            for nxt in self.import_graph.get(curr, set()):
                if nxt in dist:
                    continue
                dist[nxt] = hop + 1
                q.append(nxt)
        return dist

    @staticmethod
    def _jaccard_score(a_set, b_set):
        if not a_set or not b_set:
            return 0.0
        inter = len(a_set & b_set)
        union = len(a_set | b_set)
        if union == 0:
            return 0.0
        return float(inter) / float(union)

    def _lexeme_similarity(self, file_a, file_b):
        node_a = self.files.get(file_a, {})
        node_b = self.files.get(file_b, {})
        return self._jaccard_score(node_a.get("lexemes", set()), node_b.get("lexemes", set()))

    def _coarse_scores(self, terms):
        scores = defaultdict(float)
        for term in terms:
            for rel_path in self.inverted_symbols.get(term, set()):
                scores[rel_path] += 3.0
            for rel_path in self.inverted_path_terms.get(term, set()):
                scores[rel_path] += 2.0
        return scores

    def _fine_rerank(self, terms, coarse_ranked, gamma=0.25, coarse_k=8):
        if not coarse_ranked:
            return []

        head = coarse_ranked[:coarse_k]
        seeds = [path for path, _ in head[:2]]
        hops = self._shortest_hops_to_seeds(seeds, max_hop=4)
        qset = set(terms)

        max_coarse = max([score for _, score in head]) if head else 1.0
        if max_coarse <= 0:
            max_coarse = 1.0

        fine = []
        for rel_path, c_score in head:
            node = self.files.get(rel_path, {})
            lexemes = node.get("lexemes", set())
            lexical = self._jaccard_score(qset, lexemes)

            hop = hops.get(rel_path, None)
            dist_score = (gamma ** hop) if hop is not None else 0.0
            norm_coarse = c_score / max_coarse

            final_score = 0.55 * norm_coarse + 0.30 * lexical + 0.15 * dist_score
            fine.append((rel_path, final_score))

        fine.sort(key=lambda x: x[1], reverse=True)
        return fine

    def _mmr_select(self, ranked, top_k=3, lambda_rel=0.78):
        if not ranked:
            return []

        selected = []
        candidates = list(ranked)
        while candidates and len(selected) < top_k:
            if not selected:
                selected.append(candidates.pop(0))
                continue

            best_idx = 0
            best_mmr = -1e9
            for idx, (path, rel_score) in enumerate(candidates):
                max_sim = 0.0
                for s_path, _ in selected:
                    max_sim = max(max_sim, self._lexeme_similarity(path, s_path))
                mmr = lambda_rel * rel_score - (1.0 - lambda_rel) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx

            selected.append(candidates.pop(best_idx))

        return selected

    @staticmethod
    def _maybe_code_query(query):
        q = (query or "").lower()
        if not q.strip():
            return False
        code_hints = [
            "code", "python", "function", "class", "bug", "error", "traceback", "import",
            "api", "token", "memory", "context", "repo", "module",
            "代码", "函数", "类", "报错", "错误", "导入", "接口", "路径", "记忆", "上下文", "仓库"
        ]
        return any(h in q for h in code_hints)

    def retrieve(self, query, max_chars=1600, top_k=3, mode="coarse2fine", gamma=0.25):
        result = self.retrieve_with_meta(query, max_chars=max_chars, top_k=top_k, mode=mode, gamma=gamma)
        return result.get("text", "")

    def retrieve_with_meta(self, query, max_chars=1600, top_k=3, mode="coarse2fine", gamma=0.25):
        if not self._maybe_code_query(query):
            return {
                "text": "",
                "snippet_blocks": [],
                "snippet_hashes": [],
                "selected_files": [],
                "terms": [],
                "stats": {"runtime_ms": 0, "cache_hit": False, "mode": mode, "coarse_candidates": 0}
            }

        start_ts = time.time()
        self.build()

        terms = self._extract_query_terms(query)
        if not terms:
            return {
                "text": "",
                "snippet_blocks": [],
                "snippet_hashes": [],
                "selected_files": [],
                "terms": [],
                "stats": {"runtime_ms": int((time.time() - start_ts) * 1000), "cache_hit": False, "mode": mode, "coarse_candidates": 0}
            }

        cache_key = (query.strip().lower(), int(max_chars), int(top_k), str(mode), float(gamma), int(self._last_build_ts))
        cached = self._query_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached["ts"]) <= self._query_cache_ttl_seconds:
            out = dict(cached["payload"])
            out["stats"] = dict(out.get("stats", {}))
            out["stats"]["cache_hit"] = True
            out["stats"]["runtime_ms"] = int((time.time() - start_ts) * 1000)
            return out

        scores = self._coarse_scores(terms)

        if not scores:
            scores = self._fallback_content_scores(query, terms)
            if not scores:
                return {
                    "text": "",
                    "snippet_blocks": [],
                    "snippet_hashes": [],
                    "selected_files": [],
                    "terms": terms,
                    "stats": {"runtime_ms": int((time.time() - start_ts) * 1000), "cache_hit": False, "mode": mode, "coarse_candidates": 0}
                }

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        coarse_candidates = len(ranked)

        if mode == "coarse":
            diversified = self._mmr_select(ranked, top_k=top_k)
            primary_files = [item[0] for item in diversified]
        else:
            fine_ranked = self._fine_rerank(terms, ranked, gamma=gamma, coarse_k=max(top_k * 3, 6))
            diversified = self._mmr_select(fine_ranked, top_k=top_k)
            primary_files = [item[0] for item in diversified]

        expanded = list(primary_files)
        for rel_path in primary_files[:2]:
            node = self.files.get(rel_path)
            if not node:
                continue
            for dep in self._resolve_imports(node.get("imports", set())):
                if dep not in expanded:
                    expanded.append(dep)
                if len(expanded) >= top_k + 2:
                    break

        sections = [
            "## Repository Context Graph Retrieval",
            f"Query terms: {', '.join(terms)}",
            "",
        ]
        snippet_blocks = []
        snippet_hashes = []

        for rel_path in expanded[: top_k + 2]:
            node = self.files.get(rel_path)
            if not node:
                continue
            block = self._format_snippet(
                    rel_path,
                    node.get("lines", []),
                    terms,
                    def_spans=node.get("def_spans", []),
                )
            sections.append(block)
            snippet_blocks.append(block)
            snippet_hashes.append(hashlib.sha1(block.encode("utf-8")).hexdigest())

        text = "\n".join(sections)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n(Repository context truncated for token budget.)"

        payload = {
            "text": text,
            "snippet_blocks": snippet_blocks,
            "snippet_hashes": snippet_hashes,
            "selected_files": expanded[: top_k + 2],
            "terms": terms,
            "stats": {
                "runtime_ms": int((time.time() - start_ts) * 1000),
                "cache_hit": False,
                "mode": mode,
                "coarse_candidates": coarse_candidates,
            }
        }

        # Keep cache bounded.
        if len(self._query_cache) > 64:
            oldest = sorted(self._query_cache.items(), key=lambda x: x[1]["ts"])[:16]
            for key, _ in oldest:
                self._query_cache.pop(key, None)
        self._query_cache[cache_key] = {"payload": payload, "ts": now}

        return payload
