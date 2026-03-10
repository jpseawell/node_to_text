"""Parser for the Node to Text."""

from __future__ import annotations

import json
import re
import shlex

from node_to_text.models import EdgeDef, GraphDefinition, InterfaceSocketDef, NodeDef, ValidationError

_CODE_BLOCK_RE = re.compile(r"```(?:[A-Za-z0-9_-]+)?\s*\n(.*?)```", re.DOTALL)
_SCHEMA_SECTION_PREFIXES = ("inputs:", "outputs:", "properties:")
_NODE_TYPE_LINE_RE = re.compile(r"^[A-Z][A-Za-z0-9_]+$")


class DSLParseError(ValueError):
    """Raised when DSL text cannot be parsed."""

    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        super().__init__("\n".join(str(error) for error in errors))


def parse_dsl(text: str) -> GraphDefinition:
    text = extract_dsl_text(text)
    nodes: list[NodeDef] = []
    edges: list[EdgeDef] = []
    interface_sockets: list[InterfaceSocketDef] = []
    errors: list[ValidationError] = []
    tree_type: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("tree "):
            parsed_tree_type, tree_errors = _parse_tree_line(line, line_number)
            if parsed_tree_type is not None:
                tree_type = parsed_tree_type
            errors.extend(tree_errors)
            continue
        if line.startswith("interface "):
            interface_socket, interface_errors = _parse_interface_line(line, line_number)
            if interface_socket is not None:
                interface_sockets.append(interface_socket)
            errors.extend(interface_errors)
            continue
        if line.startswith("node "):
            node, node_errors = _parse_node_line(line, line_number)
            if node is not None:
                nodes.append(node)
            errors.extend(node_errors)
            continue
        if line.startswith("connect "):
            edge, edge_errors = _parse_connect_line(line, line_number)
            if edge is not None:
                edges.append(edge)
            errors.extend(edge_errors)
            continue
        schema_error = _parse_schema_like_error(line, line_number)
        if schema_error is not None:
            errors.append(schema_error)
            continue
        errors.append(
            ValidationError(line_number, "SyntaxError", f"Unknown declaration: {line}")
        )

    if errors:
        raise DSLParseError(errors)
    return GraphDefinition(
        nodes=nodes,
        edges=edges,
        tree_type=tree_type,
        interface_sockets=interface_sockets,
    )


def extract_dsl_text(text: str) -> str:
    stripped_text = text.strip()
    if not stripped_text:
        return text

    for code_block in _CODE_BLOCK_RE.findall(text):
        extracted = _extract_candidate_lines(code_block)
        if extracted is not None:
            return extracted

    extracted = _extract_candidate_lines(text)
    if extracted is not None:
        return extracted
    return text


def _parse_tree_line(line: str, line_number: int) -> tuple[str | None, list[ValidationError]]:
    tree_type = line[len("tree ") :].strip()
    if not tree_type:
        return None, [ValidationError(line_number, "SyntaxError", "Tree declarations require a node tree type.")]
    return tree_type, []


def _parse_interface_line(
    line: str, line_number: int
) -> tuple[InterfaceSocketDef | None, list[ValidationError]]:
    body = line[len("interface ") :].strip()
    try:
        tokens = shlex.split(body, posix=True)
    except ValueError as exc:
        return None, [ValidationError(line_number, "SyntaxError", str(exc))]

    if len(tokens) != 3:
        return None, [
            ValidationError(
                line_number,
                "SyntaxError",
                "Interface declarations require: interface <input|output> <name> <socket_type>.",
            )
        ]

    direction_token, name, socket_type = tokens
    direction = {"input": "INPUT", "output": "OUTPUT"}.get(direction_token.lower())
    if direction is None:
        return None, [
            ValidationError(
                line_number,
                "SyntaxError",
                f"Unknown interface direction {direction_token!r}; expected 'input' or 'output'.",
            )
        ]
    return InterfaceSocketDef(direction=direction, name=name, socket_type=socket_type, line_number=line_number), []


def _parse_node_line(line: str, line_number: int) -> tuple[NodeDef | None, list[ValidationError]]:
    body = line[len("node ") :].strip()
    try:
        token_spans = _split_shell_tokens_with_spans(body)
    except ValueError as exc:
        return None, [ValidationError(line_number, "SyntaxError", str(exc))]

    tokens = [token for token, _, _ in token_spans]

    if len(tokens) < 2:
        return None, [ValidationError(line_number, "SyntaxError", "Node declarations require an id and node type.")]

    type_index = next((index for index, token in enumerate(tokens) if _looks_like_node_type(token)), None)
    if type_index is None or type_index == 0:
        return None, [ValidationError(line_number, "SyntaxError", "Node declarations require an id and node type.")]

    node_type = tokens[type_index]
    node_id = " ".join(tokens[:type_index]).strip()
    if not node_id:
        return None, [ValidationError(line_number, "SyntaxError", "Node declarations require an id and node type.")]

    assignment_text = body[token_spans[type_index][2] :].strip()
    properties: dict[str, object] = {}
    errors: list[ValidationError] = []
    for token in _split_assignments(assignment_text):
        if "=" not in token:
            errors.append(
                ValidationError(
                    line_number,
                    "SyntaxError",
                    f"Invalid property token {token!r}; expected key=value.",
                )
            )
            continue
        key, raw_value = token.split("=", 1)
        key = key.strip()
        if not key:
            errors.append(
                ValidationError(line_number, "SyntaxError", f"Invalid property token {token!r}.")
            )
            continue
        properties[key] = _parse_value(raw_value)

    if errors:
        return None, errors
    return NodeDef(id=node_id, type=node_type, properties=properties, line_number=line_number), []


def _parse_connect_line(
    line: str, line_number: int
) -> tuple[EdgeDef | None, list[ValidationError]]:
    body = line[len("connect ") :]
    left, arrow, right = body.partition("->")
    if not arrow:
        return None, [ValidationError(line_number, "SyntaxError", "Connection declarations require '->'.")]

    from_endpoint, from_error = _parse_endpoint(left.strip(), line_number, "source")
    to_endpoint, to_error = _parse_endpoint(right.strip(), line_number, "target")
    errors = [error for error in (from_error, to_error) if error is not None]
    if errors:
        return None, errors

    assert from_endpoint is not None
    assert to_endpoint is not None
    return (
        EdgeDef(
            from_node=from_endpoint[0],
            from_socket=from_endpoint[1],
            to_node=to_endpoint[0],
            to_socket=to_endpoint[1],
            line_number=line_number,
        ),
        [],
    )


def _parse_endpoint(
    endpoint: str, line_number: int, side: str
) -> tuple[tuple[str, str] | None, ValidationError | None]:
    node_id, dot, socket_name = endpoint.rpartition(".")
    if not dot or not node_id.strip() or not socket_name.strip():
        return None, ValidationError(
            line_number,
            "SyntaxError",
            f"Invalid {side} endpoint {endpoint!r}; expected <node>.<socket>.",
        )
    node_id = _unquote_identifier(node_id.strip())
    return (node_id, _unquote_identifier(socket_name.strip())), None


def _parse_value(raw_value: str) -> object:
    raw_value = raw_value.strip()
    lowered = raw_value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "none":
        return None
    try:
        return int(raw_value)
    except ValueError:
        pass
    try:
        return float(raw_value)
    except ValueError:
        pass
    if raw_value.startswith("(") and raw_value.endswith(")"):
        tuple_parts = [part.strip() for part in raw_value[1:-1].split(",")]
        if tuple_parts == [""]:
            return tuple()
        return tuple(_parse_value(part) for part in tuple_parts)
    if raw_value and raw_value[0] in {'"', "["}:
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return raw_value
    return raw_value


def _parse_schema_like_error(line: str, line_number: int) -> ValidationError | None:
    lowered = line.lower()
    if lowered.startswith("output:"):
        return ValidationError(
            line_number,
            "SchemaLikeOutput",
            "This looks like an LLM preamble, not DSL. Return only lines starting with 'node' or 'connect'.",
        )
    if lowered.startswith(_SCHEMA_SECTION_PREFIXES):
        return ValidationError(
            line_number,
            "SchemaLikeOutput",
            "This looks like schema/reference text, not graph DSL. Use 'node <id> <type>' and 'connect ... -> ...' lines.",
        )
    if _NODE_TYPE_LINE_RE.match(line):
        return ValidationError(
            line_number,
            "SchemaLikeOutput",
            "This looks like a node type name from schema output, not a DSL node declaration. Use 'node <id> <type>'.",
        )
    return None


def _extract_candidate_lines(text: str) -> str | None:
    lines = text.splitlines()
    candidate_lines: list[str] = []
    found_dsl_line = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            if found_dsl_line:
                candidate_lines.append("")
            continue
        if stripped.startswith(("#", "tree ", "interface ", "node ", "connect ")):
            candidate_lines.append(stripped)
            found_dsl_line = found_dsl_line or stripped.startswith(("tree ", "interface ", "node ", "connect "))

    if not found_dsl_line:
        return None
    return "\n".join(candidate_lines).strip()


def _split_assignments(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    parts: list[str] = []
    start = 0
    depth = 0
    quote_char = ""
    saw_equals = False
    index = 0

    while index < len(stripped):
        char = stripped[index]
        if quote_char:
            if char == quote_char and stripped[index - 1] != "\\":
                quote_char = ""
            index += 1
            continue

        if char in {'"', "'"}:
            quote_char = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "=" and depth == 0:
            saw_equals = True
        elif (
            char.isspace()
            and depth == 0
            and saw_equals
            and _looks_like_assignment_start(stripped[index + 1 :])
        ):
            parts.append(stripped[start:index].strip())
            while index < len(stripped) and stripped[index].isspace():
                index += 1
            start = index
            saw_equals = False
            continue
        index += 1

    tail = stripped[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _split_shell_tokens_with_spans(text: str) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    index = 0
    length = len(text)

    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break

        start = index
        quote_char = ""
        while index < length:
            char = text[index]
            if quote_char:
                if char == "\\" and index + 1 < length:
                    index += 2
                    continue
                if char == quote_char:
                    quote_char = ""
                index += 1
                continue

            if char in {'"', "'"}:
                quote_char = char
                index += 1
                continue
            if char == "\\" and index + 1 < length:
                index += 2
                continue
            if char.isspace():
                break
            index += 1

        end = index
        raw_token = text[start:end]
        parsed_token = shlex.split(raw_token, posix=True)
        if parsed_token:
            tokens.append((parsed_token[0], start, end))

    return tokens


def _unquote_identifier(identifier: str) -> str:
    if len(identifier) >= 2 and identifier[0] == identifier[-1] and identifier[0] in {'"', "'"}:
        try:
            return shlex.split(identifier, posix=True)[0]
        except ValueError:
            return identifier[1:-1]
    return identifier


def _looks_like_node_type(token: str) -> bool:
    return bool(re.match(r"^(?:[A-Za-z_][A-Za-z0-9_]*)?Node[A-Za-z0-9_]+$", token))


def _looks_like_assignment_start(text: str) -> bool:
    if not text:
        return False
    equals_index = text.find("=")
    if equals_index <= 0:
        return False
    key = text[:equals_index].strip()
    if not key:
        return False
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?: [A-Za-z0-9_]+)*$", key))
