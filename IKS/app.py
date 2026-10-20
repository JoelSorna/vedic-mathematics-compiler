"""
app.py - Streamlit user interface for the Vedic Mathematics Compiler prototype.

This file only handles the web page.  All parsing and mathematics live in
vedic_compiler.py, so the interface can be changed without touching the
compiler.

Run with:  streamlit run app.py
"""

import streamlit as st

from vedic_compiler import (
    COMMANDS,
    MAX_DIGITS,
    METHODS,
    build_instruction,
    compile_and_run,
)

st.set_page_config(page_title="Vedic Mathematics Compiler", page_icon="🧮", layout="centered")

STATUS_ICON = {"success": "✅", "error": "❌", "skipped": "⏭️"}


def format_value(value):
    """Turn a list or number into plain readable text, e.g. [98, 97] -> '98, 97'."""
    if isinstance(value, list):
        if value and all(isinstance(item, list) for item in value):
            return "  |  ".join("[" + ", ".join(str(x) for x in item) + "]" for item in value)
        return ", ".join(str(item) for item in value)
    return str(value)


def data_to_markdown(data, indent=0):
    """Convert a stage's data dictionary into an indented bullet list with
    readable labels (e.g. 'base_zeros' -> 'Base zeros')."""
    lines = []
    for key, value in data.items():
        label = key.replace("_", " ").capitalize()
        if isinstance(value, dict):
            lines.append("    " * indent + f"- **{label}:**")
            lines.append(data_to_markdown(value, indent + 1))
        else:
            lines.append("    " * indent + f"- **{label}:** `{format_value(value)}`")
    return "\n".join(lines)


def show_stage(stage, source_text):
    """Display one compiler stage: icon, explanation, and any detail data."""
    with st.expander(f"{STATUS_ICON[stage.status]} {stage.name}", expanded=stage.status != "skipped"):
        if stage.status == "success":
            st.success(stage.message)
        elif stage.status == "error":
            st.error(stage.message)
            for error in stage.errors:
                st.write(f"- {error}")
        else:
            st.info(stage.message)

        if stage.name.startswith("1."):
            st.code(source_text if source_text.strip() else "(empty)", language=None)
        if stage.table:
            st.table(stage.table)
        if stage.data is not None:
            st.markdown(data_to_markdown(stage.data))


# ---------------------------------------------------------------------------
# A. Project introduction
# ---------------------------------------------------------------------------
st.title("🧮 Vedic Mathematics Compiler")
st.caption("An Indian Knowledge Systems (IKS) academic prototype - Python + Streamlit")

st.header("A. Project Introduction")
st.write(
    "**Vedic Mathematics** is a collection of arithmetic shortcuts popularly linked with Indian "
    "mathematical tradition. **Indian Knowledge Systems (IKS)** is the study of knowledge developed "
    "and preserved in India. This project does not make historical claims about the origin of the "
    "techniques; it treats them as well-defined procedures that a computer can represent and run."
)
st.write(
    "Following the literature review *\"A Study of Vedic Mathematics and Its Computational "
    "Representation Using Compiler Design\"*, an instruction written in a tiny language called "
    "**VM-DSL** is processed through compiler stages (lexical, syntax and semantic analysis, "
    "intermediate representation, execution) before a Vedic method calculates the answer."
)
st.info(
    "This is a **small educational compiler/interpreter prototype**. It understands only the three "
    "commands below. It is not a complete general-purpose programming language compiler."
)
with st.expander("VM-DSL language reference and input limits"):
    st.markdown(
        f"""
| Command | Method | Example |
|---|---|---|
| `NEARBASE a b` | Nikhilam Sutra | `NEARBASE 98 97` |
| `MULTIPLY a b` | Urdhva-Tiryagbhyam | `MULTIPLY 23 14` |
| `SQUARE5 n` | Ekadhikena Purvena | `SQUARE5 35` |

**Limits:** whole numbers only, at most {MAX_DIGITS} digits each. Command words are not case-sensitive.
`NEARBASE` needs positive numbers that are close to the *same* power of 10 (10, 100, 1000, ...);
"close" means the distance from the base is less than half of the base. `SQUARE5` needs a number ending in 5.
"""
    )

# ---------------------------------------------------------------------------
# B. Operation selection
# ---------------------------------------------------------------------------
st.header("B. Operation Selection")
command_keys = list(METHODS)
command = st.radio(
    "Choose a Vedic mathematical method:",
    command_keys,
    format_func=lambda key: METHODS[key]["label"],
)
st.caption(METHODS[command]["description"])

# ---------------------------------------------------------------------------
# C. Mathematical input
# ---------------------------------------------------------------------------
st.header("C. Mathematical Input")
operand_texts = []
for index, label in enumerate(METHODS[command]["operand_labels"]):
    # A separate key per method keeps each method's own example as its default.
    operand_texts.append(
        st.text_input(label, value=METHODS[command]["defaults"][index], key=f"{command}_operand_{index}")
    )

generated_instruction = build_instruction(command, operand_texts)

use_manual = st.checkbox("Advanced: type the VM-DSL instruction myself (useful for testing error handling)")
if use_manual:
    instruction = st.text_input("VM-DSL instruction", value="NEARBASE 98 97", key="manual_instruction")
    st.caption("In this mode the method and number boxes above are ignored.")
else:
    instruction = generated_instruction

# ---------------------------------------------------------------------------
# D. Compile and execute
# ---------------------------------------------------------------------------
st.header("D. Compile and Execute")
st.write("Instruction that will be compiled:")
st.code(instruction if instruction.strip() else "(empty)", language=None)

if st.button("Compile and Calculate", type="primary"):
    result = compile_and_run(instruction)

    # Work out the method name to display.
    if use_manual:
        first_word = instruction.split()[0].upper() if instruction.split() else ""
        method_label = METHODS[first_word]["label"] if first_word in COMMANDS else "Manual instruction (command not recognised)"
    else:
        method_label = METHODS[command]["label"]

    # -----------------------------------------------------------------
    # E. Compiler stages
    # -----------------------------------------------------------------
    st.header("E. Compiler Stages")
    st.caption("Each stage below was actually executed by a function in vedic_compiler.py. "
               "If a stage fails, the later stages are skipped.")
    for stage in result.stages:
        show_stage(stage, result.source)

    # -----------------------------------------------------------------
    # F. Step-by-step explanation
    # -----------------------------------------------------------------
    st.header("F. Step-by-Step Mathematical Explanation")
    if result.success:
        for line in result.steps:
            st.write(line)
    else:
        st.warning("No calculation steps are available because compilation failed. "
                   "See the error message in the failed stage above.")

    # -----------------------------------------------------------------
    # G. Final result
    # -----------------------------------------------------------------
    st.header("G. Final Result")
    st.write(f"**Selected method:** {method_label}")
    st.write("**Original instruction:**")
    st.code(result.source if result.source.strip() else "(empty)", language=None)
    if result.success:
        st.success(f"Final answer: **{result.answer}**")
    else:
        st.error(f"No answer was produced. Compilation stopped at: {result.failed_stage}.")

    st.write("**Compiler stage summary:**")
    st.table([{"Stage": s.name, "Result": f"{STATUS_ICON[s.status]} {s.status}"} for s in result.stages])
else:
    st.caption("Press the button to see the compiler stages and the calculation.")

st.divider()
st.caption("Educational prototype for an IKS course project. Calculations are performed by the "
           "Python implementations in vedic_compiler.py and cross-checked with ordinary arithmetic.")
