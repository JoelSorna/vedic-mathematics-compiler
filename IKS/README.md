# Vedic Mathematics Compiler (IKS Project Prototype)

A small educational compiler/interpreter for a Vedic Mathematics Domain-Specific Language (VM-DSL),
built with **Python** and **Streamlit**. It is *not* a general-purpose programming language compiler.

It demonstrates three techniques:

| VM-DSL command | Method | Example | Result |
|---|---|---|---|
| `NEARBASE a b` | Nikhilam Sutra (near a power of 10) | `NEARBASE 98 97` | 9506 |
| `MULTIPLY a b` | Urdhva-Tiryagbhyam (vertical and crosswise) | `MULTIPLY 23 14` | 322 |
| `SQUARE5 n` | Ekadhikena Purvena (square of a number ending in 5) | `SQUARE5 35` | 1225 |

Each instruction passes through six real stages: source instruction, lexical analysis, syntax analysis,
semantic analysis, intermediate representation (a Python dictionary) and execution.

## Files

| File | Purpose |
|---|---|
| `vedic_compiler.py` | Compiler stages and the three algorithms (no Streamlit code) |
| `app.py` | Streamlit web page |
| `test_vedic_compiler.py` | 46 automated tests (`unittest`) |
| `requirements.txt` | Dependencies (Streamlit only) |
| `Vedic_Mathematics_Compiler_Report.pdf` | Project report (7 pages) |

## Input limits

- Whole numbers only, at most **6 digits** each; negative numbers and decimals are rejected.
- `NEARBASE`: positive numbers near the **same** power of 10 (10, 100, 1000, ...); "near" means the
  distance from the base is less than half the base. Carry and borrow are handled.
- `MULTIPLY`: any two non-negative whole numbers (carries between columns are handled).
- `SQUARE5`: a non-negative whole number whose last digit is 5.
- Command words are not case-sensitive.

## Windows setup (step by step)

**1. Install Python (skip if `python --version` already works).**
Go to https://www.python.org/downloads/ , download Python 3.10 or newer, run the installer and
**tick "Add python.exe to PATH"** on the first screen, then click *Install Now*.
Close and reopen Command Prompt afterwards and check:

```
python --version
```

**2. Create a project folder**, for example `C:\VedicCompiler` (File Explorer -> New folder).

**3. Save the files** `app.py`, `vedic_compiler.py`, `requirements.txt`, `test_vedic_compiler.py`
and this `README.md` into that folder.

**4. Open a terminal in the folder.** In File Explorer open the folder, click the address bar, type `cmd`
and press Enter (or right-click an empty area -> "Open in Terminal" for PowerShell).

**5. Create and activate a virtual environment.**

```
python -m venv venv
```

Command Prompt:

```
venv\Scripts\activate
```

PowerShell:

```
venv\Scripts\Activate.ps1
```

If PowerShell says scripts are disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
and activate again. You should see `(venv)` at the start of the prompt.

**6. Install the dependency.**

```
pip install -r requirements.txt
```

**7. Start the website.**

```
streamlit run app.py
```

**8. Open the app.** Streamlit prints a Local URL (normally `http://localhost:8501`) and usually opens
your browser by itself. If not, copy the URL into your browser. Stop the app with `Ctrl + C` in the terminal.

**9. Run the automated tests** (in the same folder, venv active):

```
python -m unittest test_vedic_compiler.py -v
```

All 46 tests should report `OK`.

## How to use the app

1. Choose a method with the radio buttons.
2. Edit the numbers (examples are pre-filled).
3. Click **Compile and Calculate**.
4. Read the six compiler stages, the step-by-step explanation and the final answer.

To see error handling, tick **Advanced** and type an instruction such as `ADD 1 2`, `NEARBASE 98`,
`MULTIPLY 2.5 3` or `SQUARE5 36`. The failing stage is shown in red and later stages are skipped.

## Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Reinstall Python and tick "Add python.exe to PATH", or try `py` instead of `python`. |
| `'pip' is not recognized` | Use `python -m pip install -r requirements.txt`. |
| `'streamlit' is not recognized` | Activate the venv first, or run `python -m streamlit run app.py`. |
| PowerShell blocks `Activate.ps1` | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, or use Command Prompt. |
| `ModuleNotFoundError: vedic_compiler` | Run commands from the folder that contains all the files. |
| `ModuleNotFoundError: streamlit` | The venv is not active, or step 6 was skipped. |
| Port 8501 already in use | `streamlit run app.py --server.port 8502` |
| Browser does not open | Copy the Local URL from the terminal into the browser. |
| Page shows old content | Click "Rerun" in the top-right menu, or press `R` in the browser tab. |
| pip install fails (network or proxy) | Check your internet connection or use a different network, then retry. |

## Testing status

The code and tests were run on Linux with Python 3.12 and Streamlit 1.66 (all 46 tests pass, and the app was
driven through a headless browser). It has **not** been run on Windows by the author of these files; the
instructions above are the standard Windows procedure.
