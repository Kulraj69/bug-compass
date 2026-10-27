"""Pure localization functions. Gold labels never enter retrieval rankings."""
from __future__ import annotations

import ast
import math
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass
class ParsedFile:
    imports: list[tuple[str, int, list[str]]]
    symbols: list[str]
    ranges: list[tuple[str, int, int]]
    chars: int
    parsed: bool = True


def parse_source(source: str) -> ParsedFile:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return ParsedFile([], [], [], len(source), False)
    imports, symbols, ranges = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, 0, []) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "", node.level, [a.name for a in node.names]))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            ranges.append((node.name, start, node.end_lineno or node.lineno))
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.extend([child.name, f"{node.name}.{child.name}"])
                        start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                        ranges.append((f"{node.name}.{child.name}", start, child.end_lineno or child.lineno))
    return ParsedFile(imports, symbols, ranges, len(source))


def module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def module_index(paths: list[str]) -> dict[str, set[str]]:
    modules: dict[str, set[str]] = defaultdict(set)
    # Accommodate the standard src/ layout and matplotlib's lib/ layout.
    for path in paths:
        name = module_name(path)
        modules[name].add(path)
        if path.startswith(("src/", "lib/")):
            modules[name.split(".", 1)[1]].add(path)
    return dict(modules)


def resolve_import(path: str, module: str, level: int, names: list[str], modules: dict[str, set[str]]) -> set[str]:
    if level:
        package = module_name(path).split(".")
        if not path.endswith("/__init__.py"):
            package = package[:-1]
        if level > len(package):
            return set()
        prefix = package[:len(package) - level + 1]
        base = ".".join(prefix + ([module] if module else []))
    else:
        base = module
    candidates = {base}
    candidates.update(f"{base}.{name}" if base else name for name in names if name != "*")
    resolved: set[str] = set()
    for candidate in candidates:
        resolved.update(modules.get(candidate, set()))
    return resolved - {path}


def build_index(files: dict[str, ParsedFile]):
    modules = module_index(list(files))
    graph = {path: set() for path in files}
    symbols: dict[str, set[str]] = defaultdict(set)
    for path, parsed in files.items():
        for symbol in parsed.symbols:
            symbols[symbol].add(path)
            symbols[f"{module_name(path)}.{symbol}"].add(path)
            if path.startswith(("src/", "lib/")):
                symbols[f"{module_name(path).split('.', 1)[1]}.{symbol}"].add(path)
        for module, level, names in parsed.imports:
            for target in resolve_import(path, module, level, names, modules):
                graph[path].add(target)
                graph[target].add(path)
    return graph, dict(symbols), modules


IDENTIFIER = re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\b")
PATH = re.compile(r"(?<![\w])(?:[\w.\-]+[/\\])*[\w\-]+\.py\b")


def extract_mentions(text: str, paths: list[str], symbols: dict[str, set[str]], modules: dict[str, set[str]]):
    """Unique textual mentions; ambiguous matches retain every candidate file."""
    candidates: dict[str, str] = {}
    for match in PATH.finditer(text):
        candidates[match.group()] = "file"
    for token in IDENTIFIER.findall(text):
        if "." in token and not token.endswith(".py"):
            candidates.setdefault(token, "dotted")
    # Inline and fenced backticks, plus conventional Python traceback frames.
    snippets = re.findall(r"`+([^`]+)`+", text, re.S)
    snippets += re.findall(r'^\s*File [^\n]+, in ([^\n]+)', text, re.M)
    for snippet in snippets:
        for token in IDENTIFIER.findall(snippet):
            if token in symbols:
                candidates.setdefault(token, "symbol")
    mentions = []
    for token, kind in sorted(candidates.items()):
        matched: set[str] = set()
        normalized = token.replace("\\", "/").removeprefix("./")
        if kind == "file":
            matched = {p for p in paths if p == normalized or p.endswith("/" + normalized) or normalized.endswith("/" + p)}
        else:
            matched.update(modules.get(token, set()))
            matched.update(symbols.get(token, set()))
        mentions.append({"text": token, "kind": kind, "files": sorted(matched)})
    return mentions


def parse_patch(patch: str, files: dict[str, ParsedFile]):
    """Map changed old-side lines to the narrowest enclosing base-commit symbol.

    Added definitions only present on the new side are reported separately. For
    insertions, the preceding old line anchors the enclosing base function.
    """
    changes: dict[str, dict] = {}
    current = None
    old_line = 0
    in_hunk = False
    pending_old = None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            current, pending_old, in_hunk = None, None, False
        elif line.startswith("--- ") and not in_hunk:
            pending_old = line[4:].removeprefix("a/")
        elif line.startswith("+++ ") and not in_hunk:
            new = line[4:].removeprefix("b/")
            current = pending_old if new == "/dev/null" else new
            changes[current] = {"file": current, "base_file": pending_old, "lines": set(), "hunk_contexts": [], "added_definitions": set()}
        elif line.startswith("@@") and current:
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@(.*)", line)
            if match:
                old_line = int(match.group(1))
                changes[current]["hunk_contexts"].append(match.group(2).strip())
                in_hunk = True
        elif in_hunk and current:
            if line.startswith("-"):
                changes[current]["lines"].add(old_line)
                old_line += 1
            elif line.startswith("+"):
                changes[current]["lines"].add(max(1, old_line - 1))
                definition = re.match(r"\+\s*(?:async\s+)?(?:def|class)\s+(\w+)", line)
                if definition:
                    changes[current]["added_definitions"].add(definition.group(1))
            elif line.startswith(" "):
                old_line += 1
    result = []
    for change in changes.values():
        parsed = files.get(change["base_file"] or change["file"])
        edited = set()
        if parsed:
            for lineno in change["lines"]:
                containing = [(end - start, name) for name, start, end in parsed.ranges if start <= lineno <= end]
                if containing:
                    edited.add(min(containing)[1])
        result.append({"file": change["file"], "functions": sorted(edited), "added_definitions": sorted(change["added_definitions"]), "hunk_contexts": change["hunk_contexts"]})
    return result


def bfs_ranking(graph: dict[str, set[str]], seeds: list[str]):
    queue = deque(sorted(set(seeds) & graph.keys()))
    parent = {path: None for path in queue}
    distance = {path: 0 for path in queue}
    ranking = []
    while queue:
        path = queue.popleft()
        ranking.append(path)
        for neighbor in sorted(graph[path]):
            if neighbor not in parent:
                parent[neighbor] = path
                distance[neighbor] = distance[path] + 1
                queue.append(neighbor)
    return ranking, parent, distance


def radius_metrics(graph, seeds, edited, sizes):
    ranking, parent, distance = bfs_ranking(graph, seeds)
    reached = next((p for p in ranking if p in edited), None)
    path = []
    cursor = reached
    while cursor is not None:
        path.append(cursor)
        cursor = parent[cursor]
    visited = ranking[:ranking.index(reached) + 1] if reached else ranking
    return {
        "radius": distance[reached] if reached else None,
        "radius_status": "reached" if reached else ("unreachable" if ranking else "no_mentions"),
        "hop_path": path[::-1],
        "context_budget_tokens": sum(sizes[p] for p in visited) / 4 if ranking else None,
        "visited_files": len(visited),
        "reachable_files": len(ranking),
        "seed_fan_out": len({n for p in seeds for n in graph.get(p, set())} - set(seeds)),
    }, ranking


def tokenize(text: str) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_ranking(files: dict[str, ParsedFile], query: str, limit: int = 10) -> list[str]:
    docs = {p: Counter(tokenize(p + " " + " ".join(s.symbols))) for p, s in files.items()}
    if not docs:
        return []
    df = Counter(term for terms in docs.values() for term in terms)
    lengths = {p: sum(terms.values()) for p, terms in docs.items()}
    average = sum(lengths.values()) / len(docs) or 1
    query_terms = set(tokenize(query))
    scores = {}
    for path, terms in docs.items():
        score = 0.0
        for term in query_terms & terms.keys():
            freq = terms[term]
            idf = math.log(1 + (len(docs) - df[term] + .5) / (df[term] + .5))
            score += idf * freq * 2.5 / (freq + 1.5 * (.25 + .75 * lengths[path] / average))
        scores[path] = score
    # Even zero-score ties have a deterministic path order; no gold fallback.
    return sorted(scores, key=lambda p: (-scores[p], p))[:limit]


def recall_at(ranking: list[str], edited: list[str], k: int) -> float:
    gold = set(edited)
    return len(set(ranking[:k]) & gold) / len(gold) if gold else 0.0
