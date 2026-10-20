"""
vedic_compiler.py
=================
A small educational compiler / interpreter for a Vedic Mathematics
Domain-Specific Language (VM-DSL).

It is NOT a general-purpose programming language compiler.  It understands
exactly three one-line commands:

    NEARBASE a b     -> Nikhilam Sutra (multiplication of numbers near a power of 10)
    MULTIPLY a b     -> Urdhva-Tiryagbhyam (vertical and crosswise multiplication)
    SQUARE5  n       -> Ekadhikena Purvena (squaring a number that ends in 5)

The instruction is processed by six stages, each implemented as a real
function that can fail with a helpful message:

    1. Source instruction   (checked inside compile_and_run)
    2. lexical_analysis()   text  -> tokens
    3. syntax_analysis()    tokens -> parse tree (command + operands)
    4. semantic_analysis()  parse tree -> validated, annotated tree
    5. generate_ir()        validated tree -> intermediate representation (dict)
    6. execute_operation()  IR -> answer + step-by-step explanation

This file contains no Streamlit code, so it can be tested on its own.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Language definition and limits
# ---------------------------------------------------------------------------

# Supported commands and the number of operands each one needs.
COMMANDS: Dict[str, int] = {"NEARBASE": 2, "MULTIPLY": 2, "SQUARE5": 1}

# Largest number of digits accepted for any operand (keeps the steps readable).
MAX_DIGITS = 6

# Information used by the user interface (labels, example inputs, descriptions).
METHODS: Dict[str, Dict[str, Any]] = {
    "NEARBASE": {
        "label": "Nikhilam Sutra (Near Base)",
        "operand_labels": ["First number", "Second number"],
        "defaults": ["98", "97"],
        "description": "Multiplies two numbers that are both close to the same "
                       "power of 10 (10, 100, 1000, ...).",
    },
    "MULTIPLY": {
        "label": "Urdhva-Tiryagbhyam (Vertical and Crosswise)",
        "operand_labels": ["First number", "Second number"],
        "defaults": ["23", "14"],
        "description": "Multiplies any two non-negative whole numbers by adding "
                       "vertical and crosswise digit products column by column.",
    },
    "SQUARE5": {
        "label": "Ekadhikena Purvena (One More Than the Previous)",
        "operand_labels": ["Number ending in 5"],
        "defaults": ["35"],
        "description": "Squares a whole number whose last digit is 5.",
    },
}


# ---------------------------------------------------------------------------
# Small data containers
# ---------------------------------------------------------------------------

@dataclass
class Token:
    """One lexical token: its type (COMMAND, INTEGER, ...), text and position."""
    type: str
    value: str
    position: int


@dataclass
class StageResult:
    """The outcome of one compiler stage, ready to be shown to the user."""
    name: str
    status: str                      # "success", "error" or "skipped"
    message: str                     # short explanation of what happened
    errors: List[str] = field(default_factory=list)
    table: Optional[List[Dict[str, Any]]] = None   # e.g. the token list
    data: Optional[Dict[str, Any]] = None          # e.g. parse tree / IR


@dataclass
class CompilationResult:
    """Everything produced by compile_and_run()."""
    source: str
    stages: List[StageResult] = field(default_factory=list)
    ir: Optional[Dict[str, Any]] = None
    answer: Optional[int] = None
    steps: List[str] = field(default_factory=list)
    success: bool = False
    failed_stage: Optional[str] = None


class ExecutionError(Exception):
    """Raised when the execution stage cannot (or should not) give an answer."""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def build_instruction(command: str, operand_texts: List[str]) -> str:
    """Build a VM-DSL instruction from a command word and the text typed by
    the user.  Blank fields are dropped, so a missing operand is reported
    later by the syntax stage (wrong operand count)."""
    parts = [command] + [text.strip() for text in operand_texts if text.strip()]
    return " ".join(parts)


def count_digits(number: int) -> int:
    """Number of decimal digits in a non-negative integer."""
    return len(str(number))


def choose_base(number: int) -> int:
    """Return the power of 10 (10, 100, 1000, ...) nearest to `number`.
    If two bases are equally near, the larger one is chosen."""
    candidates = [10 ** k for k in range(1, MAX_DIGITS + 2)]
    return min(candidates, key=lambda base: (abs(number - base), -base))


# ---------------------------------------------------------------------------
# Stage 2: Lexical analysis
# ---------------------------------------------------------------------------

# Regular expression with one named group per kind of lexeme.
_TOKEN_REGEX = re.compile(
    r"""
      (?P<SPACE>\s+)
    | (?P<FLOAT>-?\d+\.\d+)
    | (?P<INTEGER>-?\d+)
    | (?P<WORD>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<ILLEGAL>.)
    """,
    re.VERBOSE,
)


def lexical_analysis(source: str) -> Tuple[List[Token], List[str]]:
    """Split the instruction text into tokens.

    Token types:
        COMMAND  a supported command word (NEARBASE, MULTIPLY, SQUARE5)
        IDENT    any other word (kept so the syntax stage can complain)
        INTEGER  a whole number such as 98 or -4
        FLOAT    a number with a decimal point (rejected later by syntax)
        ILLEGAL  a character that is not part of the language

    Returns (tokens, errors).  Only illegal characters or an empty
    instruction are lexical errors.
    """
    tokens: List[Token] = []
    errors: List[str] = []

    for match in _TOKEN_REGEX.finditer(source):
        kind = match.lastgroup
        text = match.group()
        if kind == "SPACE":
            continue
        if kind == "WORD":
            if text.upper() in COMMANDS:
                tokens.append(Token("COMMAND", text.upper(), match.start()))
            else:
                tokens.append(Token("IDENT", text, match.start()))
        else:
            tokens.append(Token(kind, text, match.start()))
            if kind == "ILLEGAL":
                errors.append(
                    f"Illegal character {text!r} at position {match.start()}. "
                    "Only command words and whole numbers are allowed."
                )

    if not tokens:
        errors.append("The instruction is empty - there is nothing to tokenize.")
    return tokens, errors


# ---------------------------------------------------------------------------
# Stage 3: Syntax analysis
# ---------------------------------------------------------------------------

def syntax_analysis(tokens: List[Token]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Check the token list against the grammar

        instruction := COMMAND INTEGER{n}

    where n is 2 for NEARBASE / MULTIPLY and 1 for SQUARE5.
    Returns (parse_tree, errors); parse_tree is None if there are errors.
    """
    errors: List[str] = []
    if not tokens:
        return None, ["No tokens to parse."]

    first = tokens[0]
    if first.type == "IDENT":
        return None, [
            f"Unsupported command '{first.value}'. "
            f"Supported commands are: {', '.join(COMMANDS)}."
        ]
    if first.type != "COMMAND":
        return None, [
            f"An instruction must start with a command word, but it starts "
            f"with '{first.value}'. Supported commands: {', '.join(COMMANDS)}."
        ]

    command = first.value
    expected = COMMANDS[command]
    operand_tokens = tokens[1:]

    # Every operand must be a whole number.
    for tok in operand_tokens:
        if tok.type == "FLOAT":
            errors.append(f"Operand '{tok.value}' is a decimal number; whole numbers are required.")
        elif tok.type in ("COMMAND", "IDENT"):
            errors.append(f"Operand '{tok.value}' is a word, not a whole number.")
        elif tok.type == "ILLEGAL":
            errors.append(f"Operand '{tok.value}' is not a number.")

    if len(operand_tokens) != expected:
        errors.append(
            f"{command} needs exactly {expected} operand(s), "
            f"but {len(operand_tokens)} were given."
        )

    if errors:
        return None, errors
    return {"command": command, "operands": [t.value for t in operand_tokens]}, []


# ---------------------------------------------------------------------------
# Stage 4: Semantic analysis
# ---------------------------------------------------------------------------

def semantic_analysis(parse_tree: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Check that the operands make sense for the chosen operation.

    Rules
      NEARBASE : positive integers of at most MAX_DIGITS digits; both must be
                 near the SAME power of 10 (distance from the base less than
                 half of the base).
      MULTIPLY : non-negative integers of at most MAX_DIGITS digits.
      SQUARE5  : a non-negative integer of at most MAX_DIGITS digits whose
                 last digit is 5.

    Returns (checked_tree, errors).  checked_tree holds integer operands and,
    for NEARBASE, the chosen base.
    """
    command = parse_tree["command"]
    errors: List[str] = []
    numbers = [int(text) for text in parse_tree["operands"]]

    # ---- rules common to all commands ---------------------------------
    for n in numbers:
        if n < 0:
            errors.append(f"{n} is negative. Only non-negative whole numbers are supported.")
        elif count_digits(n) > MAX_DIGITS:
            errors.append(f"{n} has more than {MAX_DIGITS} digits, which is the supported limit.")
    if errors:
        return None, errors

    checked: Dict[str, Any] = {"command": command, "operands": numbers}

    # ---- rules specific to each command -------------------------------
    if command == "NEARBASE":
        for n in numbers:
            if n == 0:
                errors.append("0 is not allowed for NEARBASE; use positive numbers near a power of 10.")
        if not errors:
            bases = [choose_base(n) for n in numbers]
            seen = set()   # report each distinct number only once
            for n, base in zip(numbers, bases):
                if n in seen:
                    continue
                seen.add(n)
                if abs(n - base) * 2 >= base:
                    errors.append(
                        f"{n} is not near a power of 10 (nearest base is {base}, "
                        f"but the distance {abs(n - base)} is at least half of it). "
                        "Try the vertical-and-crosswise method (MULTIPLY) instead."
                    )
            if not errors and bases[0] != bases[1]:
                errors.append(
                    f"The numbers are near different bases ({bases[0]} and {bases[1]}). "
                    "Nikhilam needs one common base for both numbers."
                )
            if not errors:
                checked["base"] = bases[0]

    elif command == "SQUARE5":
        if numbers[0] % 10 != 5:
            errors.append(f"{numbers[0]} does not end in 5, so this shortcut cannot be used.")

    # MULTIPLY has no extra rules beyond the common ones.

    if errors:
        return None, errors
    return checked, []


# ---------------------------------------------------------------------------
# Stage 5: Intermediate representation
# ---------------------------------------------------------------------------

def generate_ir(checked: Dict[str, Any]) -> Dict[str, Any]:
    """Turn the validated tree into a structured intermediate representation
    (a plain dictionary) that fully describes what must be computed."""
    command = checked["command"]
    numbers = checked["operands"]

    if command == "NEARBASE":
        base = checked["base"]
        return {
            "operation": "NEAR_BASE_MULTIPLY",
            "technique": "Nikhilam Sutra",
            "operands": numbers,
            "parameters": {
                "base": base,
                "base_zeros": len(str(base)) - 1,
                "deviations": [n - base for n in numbers],
            },
        }
    if command == "MULTIPLY":
        return {
            "operation": "VERTICAL_CROSSWISE_MULTIPLY",
            "technique": "Urdhva-Tiryagbhyam",
            "operands": numbers,
            "parameters": {
                "digits": [[int(d) for d in str(n)] for n in numbers],
            },
        }
    if command == "SQUARE5":
        n = numbers[0]
        return {
            "operation": "SQUARE_ENDING_IN_5",
            "technique": "Ekadhikena Purvena",
            "operands": numbers,
            "parameters": {"prefix": n // 10, "suffix": 5},
        }
    raise ValueError(f"No IR rule for command {command}")  # unreachable after semantics


# ---------------------------------------------------------------------------
# Stage 6: Execution (the three Vedic algorithms)
# ---------------------------------------------------------------------------

def nikhilam_multiply(a: int, b: int, base: int) -> Dict[str, Any]:
    """Multiply a and b using the Nikhilam (near base) method.

    a = base + da,  b = base + db   (deviations da, db may be negative)
    left part  = a + db  (= b + da)
    right part = da * db
    answer     = left * base + right      (carry/borrow handled explicitly)

    Each step is a short Markdown string that the web page displays.
    """
    zeros = len(str(base)) - 1
    da, db = a - base, b - base

    left = a + db
    if left != b + da:  # cannot happen, but never hide an inconsistency
        raise ExecutionError("Internal inconsistency in the left part of Nikhilam.")
    right = da * db
    carry, right_digits = divmod(right, base)   # divmod also handles negative values
    right_text = str(right_digits).zfill(zeros)

    steps = [
        f"**We want to calculate:** {a} × {b}  (base = {base})",
        f"**Step 1: Differences from the base**\n\n{a} - {base} = {da}\n\n{b} - {base} = {db}",
        f"**Step 2: Crosswise (left part)**\n\n{a} + ({db}) = {left}",
    ]
    if carry == 0:
        steps.append(f"**Step 3: Vertically (right part)**\n\n({da}) × ({db}) = {right}\n\n"
                     f"Write {right_text} ({zeros} digit(s) because the base has {zeros} zero(s)).")
    else:
        steps.append(f"**Step 3: Vertically (right part)**\n\n({da}) × ({db}) = {right}\n\n"
                     f"The right part must have {zeros} digit(s): {right} = ({carry} × {base}) + {right_digits}\n\n"
                     f"Move {carry} to the left: {left} + ({carry}) = {left + carry}\n\n"
                     f"Right part = {right_text}")
    left += carry
    answer = left * base + right_digits
    steps.append(f"**Final answer**\n\nJoin left and right: {left} and {right_text}\n\n{a} × {b} = {answer}")
    return {"answer": answer, "steps": steps}


def urdhva_tiryagbhyam_multiply(a: int, b: int) -> Dict[str, Any]:
    """Multiply a and b with vertical and crosswise products.

    Both numbers are padded with leading zeros to the same length n.  The
    answer is built from 2n-1 columns, starting at the right.  In column k we
    add every product a_i x b_j with i + j = k (counting positions from the
    right), add the carry from the previous column, write the last digit and
    carry the rest.

    Each step is a short Markdown string that the web page displays.
    """
    digits_a = [int(c) for c in str(a)]
    digits_b = [int(c) for c in str(b)]
    n = max(len(digits_a), len(digits_b))
    padded_a = [0] * (n - len(digits_a)) + digits_a
    padded_b = [0] * (n - len(digits_b)) + digits_b
    right_a, right_b = padded_a[::-1], padded_b[::-1]    # position 0 = units digit

    # Header: the two numbers written one above the other.
    top = "   " + "  ".join(map(str, padded_a))
    bottom = "×  " + "  ".join(map(str, padded_b))
    header = f"**We want to calculate:** {a} × {b}\n\n```\n{top}\n{bottom}\n{'-' * (3 * n + 1)}\n```"
    if len(digits_a) != len(digits_b):
        header += f"\n\nLeading zeros are added so both numbers have {n} digit(s)."
    steps = [header]

    columns = 2 * n - 1
    slots = ["_"] * columns          # the answer digits written so far (right to left)
    written: List[int] = []
    carry = 0

    for column in range(columns):
        pairs = [(i, column - i) for i in range(n) if 0 <= column - i < n]
        products = [right_a[i] * right_b[j] for i, j in pairs]
        column_sum = sum(products)
        total = column_sum + carry
        digit, new_carry = total % 10, total // 10
        is_last = column == columns - 1

        if columns == 1:
            title = "Vertically"
        elif column == 0:
            title = "Vertically (rightmost digits)"
        elif is_last:
            title = "Vertically (leftmost digits)"
        else:
            title = "Crosswise"

        text = f"**Step {column + 1}: {title}**\n\n"
        if len(pairs) == 1:
            text += f"{right_a[pairs[0][0]]}×{right_b[pairs[0][1]]} = {column_sum}"
        else:
            expression = "+".join(f"({right_a[i]}×{right_b[j]})" for i, j in pairs)
            text += f"{expression}\n\n{' + '.join(map(str, products))} = {column_sum}"
        if carry:
            text += f"\n\nAdd the carry:\n\n{column_sum} + {carry} = {total}"

        if is_last and new_carry:
            text += f"\n\nWrite {digit}, and put the carry {new_carry} in front."
        elif is_last:
            text += f"\n\nWrite {digit}."
        else:
            text += f"\n\nWrite {digit} and carry {new_carry}."
            slots[columns - 1 - column] = str(digit)
            text += f"\n\n```\nResult: {' '.join(slots)}\nCarry:  {new_carry}\n```"
        steps.append(text)
        written.append(digit)
        carry = new_carry

    digit_string = (str(carry) if carry else "") + "".join(str(d) for d in reversed(written))
    answer = int(digit_string)
    steps.append(f"**Final answer**\n\n{a} × {b} = {answer}")
    return {"answer": answer, "steps": steps}


def ekadhikena_square(n: int) -> Dict[str, Any]:
    """Square a number ending in 5: if n = 10p + 5 then n^2 = p(p+1) followed by 25."""
    prefix = n // 10
    product = prefix * (prefix + 1)
    answer = product * 100 + 25
    steps = [
        f"**We want to calculate:** {n}²",
        f"**Step 1: Split the number**\n\n{n} = front part {prefix}, last digit 5",
        f"**Step 2: Multiply the front part by one more than itself**\n\n"
        f"{prefix} + 1 = {prefix + 1}\n\n{prefix} × {prefix + 1} = {product}",
        f"**Step 3: Write 25 after it**\n\n{product} followed by 25 = {answer}",
        f"**Final answer**\n\n{n}² = {answer}",
    ]
    return {"answer": answer, "steps": steps}


def execute_operation(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Run the algorithm named in the IR and return answer + steps.

    As a safety net, the answer is compared with ordinary Python arithmetic.
    If they ever disagree an ExecutionError is raised, so the program can
    never silently display a wrong result.
    """
    operation = ir["operation"]
    operands = ir["operands"]

    if operation == "NEAR_BASE_MULTIPLY":
        result = nikhilam_multiply(operands[0], operands[1], ir["parameters"]["base"])
        expected = operands[0] * operands[1]
    elif operation == "VERTICAL_CROSSWISE_MULTIPLY":
        result = urdhva_tiryagbhyam_multiply(operands[0], operands[1])
        expected = operands[0] * operands[1]
    elif operation == "SQUARE_ENDING_IN_5":
        result = ekadhikena_square(operands[0])
        expected = operands[0] ** 2
    else:
        raise ExecutionError(f"Unknown operation '{operation}' in the intermediate representation.")

    if result["answer"] != expected:
        raise ExecutionError(
            f"Self-check failed: the algorithm gave {result['answer']} but ordinary arithmetic gives {expected}. "
            "The result is withheld."
        )
    result["verified_with"] = f"Ordinary arithmetic also gives {expected}."
    return result


# ---------------------------------------------------------------------------
# The complete pipeline
# ---------------------------------------------------------------------------

STAGE_NAMES = [
    "1. Source Instruction",
    "2. Lexical Analysis",
    "3. Syntax Analysis",
    "4. Semantic Analysis",
    "5. Intermediate Representation (IR)",
    "6. Execution",
]


def compile_and_run(source: str) -> CompilationResult:
    """Run an instruction through all six stages.  The first stage that fails
    stops the pipeline; the remaining stages are reported as 'skipped'."""
    result = CompilationResult(source=source)

    def fail(index: int, message: str, errors: List[str], **extra: Any) -> CompilationResult:
        """Record a failed stage, mark later stages skipped, and return."""
        result.stages.append(StageResult(STAGE_NAMES[index], "error", message, errors, **extra))
        result.failed_stage = STAGE_NAMES[index]
        for name in STAGE_NAMES[index + 1:]:
            result.stages.append(StageResult(name, "skipped", "Not run because an earlier stage failed."))
        return result

    # ---- Stage 1: source instruction ---------------------------------
    if not isinstance(source, str) or not source.strip():
        return fail(0, "No instruction was supplied.", ["The instruction is empty."])
    result.stages.append(StageResult(
        STAGE_NAMES[0], "success",
        "The VM-DSL instruction below is the program that will be compiled."))

    # ---- Stage 2: lexical analysis -----------------------------------
    tokens, errors = lexical_analysis(source)
    token_rows = [{"Position": t.position, "Type": t.type, "Value": t.value} for t in tokens]
    if errors:
        return fail(1, "The text could not be split into valid tokens.", errors, table=token_rows or None)
    result.stages.append(StageResult(
        STAGE_NAMES[1], "success",
        f"The text was split into {len(tokens)} token(s).", table=token_rows))

    # ---- Stage 3: syntax analysis ------------------------------------
    parse_tree, errors = syntax_analysis(tokens)
    if errors:
        return fail(2, "The token sequence does not follow the VM-DSL grammar.", errors)
    result.stages.append(StageResult(
        STAGE_NAMES[2], "success",
        f"Valid syntax: command {parse_tree['command']} followed by "
        f"{len(parse_tree['operands'])} whole-number operand(s).", data=parse_tree))

    # ---- Stage 4: semantic analysis ----------------------------------
    checked, errors = semantic_analysis(parse_tree)
    if errors:
        return fail(3, "The operands are not valid for this operation.", errors)
    detail = f" Common base chosen: {checked['base']}." if "base" in checked else ""
    result.stages.append(StageResult(
        STAGE_NAMES[3], "success",
        "The operands are valid for the selected operation." + detail, data=checked))

    # ---- Stage 5: intermediate representation ------------------------
    ir = generate_ir(checked)
    result.ir = ir
    result.stages.append(StageResult(
        STAGE_NAMES[4], "success",
        f"Built a structured IR for operation {ir['operation']} ({ir['technique']}).", data=ir))

    # ---- Stage 6: execution ------------------------------------------
    try:
        outcome = execute_operation(ir)
    except ExecutionError as error:
        return fail(5, "The operation could not be completed.", [str(error)])
    result.stages.append(StageResult(
        STAGE_NAMES[5], "success",
        f"The {ir['technique']} algorithm produced {outcome['answer']}. {outcome['verified_with']}",
        data={"answer": outcome["answer"]}))

    result.answer = outcome["answer"]
    result.steps = outcome["steps"]
    result.success = True
    return result
