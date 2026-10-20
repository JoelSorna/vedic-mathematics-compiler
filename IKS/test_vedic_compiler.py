"""
Automated tests for vedic_compiler.py

Run with:   python -m unittest test_vedic_compiler.py -v

The Vedic algorithms are checked against ordinary Python arithmetic
(a * b and n * n), which is independent of the Vedic methods.
"""

import random
import unittest

from vedic_compiler import (
    MAX_DIGITS,
    build_instruction,
    choose_base,
    compile_and_run,
    ekadhikena_square,
    execute_operation,
    generate_ir,
    lexical_analysis,
    nikhilam_multiply,
    semantic_analysis,
    syntax_analysis,
    urdhva_tiryagbhyam_multiply,
    ExecutionError,
)


class TestAlgorithms(unittest.TestCase):
    """The three Vedic algorithms must agree with ordinary arithmetic."""

    def test_nikhilam_example(self):
        self.assertEqual(nikhilam_multiply(98, 97, 100)["answer"], 9506)

    def test_nikhilam_above_base(self):
        self.assertEqual(nikhilam_multiply(103, 104, 100)["answer"], 10712)

    def test_nikhilam_mixed_sides_needs_borrow(self):
        self.assertEqual(nikhilam_multiply(98, 102, 100)["answer"], 9996)

    def test_nikhilam_carry_case(self):
        # deviations -15 and -12 -> right part 180 has 3 digits, needs carry
        self.assertEqual(nikhilam_multiply(85, 88, 100)["answer"], 85 * 88)

    def test_nikhilam_base_10_and_1000(self):
        self.assertEqual(nikhilam_multiply(9, 8, 10)["answer"], 72)
        self.assertEqual(nikhilam_multiply(997, 995, 1000)["answer"], 997 * 995)

    def test_nikhilam_number_equal_to_base(self):
        self.assertEqual(nikhilam_multiply(100, 87, 100)["answer"], 8700)

    def test_nikhilam_exhaustive_around_base_100(self):
        for a in range(51, 150):
            for b in range(51, 150):
                self.assertEqual(nikhilam_multiply(a, b, 100)["answer"], a * b, (a, b))

    def test_urdhva_example(self):
        self.assertEqual(urdhva_tiryagbhyam_multiply(23, 14)["answer"], 322)

    def test_urdhva_zero_and_one(self):
        self.assertEqual(urdhva_tiryagbhyam_multiply(0, 0)["answer"], 0)
        self.assertEqual(urdhva_tiryagbhyam_multiply(0, 987)["answer"], 0)
        self.assertEqual(urdhva_tiryagbhyam_multiply(1, 987)["answer"], 987)

    def test_urdhva_different_lengths(self):
        self.assertEqual(urdhva_tiryagbhyam_multiply(5, 123)["answer"], 615)
        self.assertEqual(urdhva_tiryagbhyam_multiply(12345, 6)["answer"], 74070)

    def test_urdhva_heavy_carries(self):
        self.assertEqual(urdhva_tiryagbhyam_multiply(999999, 999999)["answer"], 999999 ** 2)

    def test_urdhva_all_two_digit_pairs(self):
        for a in range(0, 100):
            for b in range(0, 100):
                self.assertEqual(urdhva_tiryagbhyam_multiply(a, b)["answer"], a * b, (a, b))

    def test_urdhva_random_pairs(self):
        rng = random.Random(2024)
        for _ in range(2000):
            a = rng.randint(0, 10 ** MAX_DIGITS - 1)
            b = rng.randint(0, 10 ** MAX_DIGITS - 1)
            self.assertEqual(urdhva_tiryagbhyam_multiply(a, b)["answer"], a * b, (a, b))

    def test_square5_example(self):
        self.assertEqual(ekadhikena_square(35)["answer"], 1225)

    def test_square5_smallest_and_large(self):
        self.assertEqual(ekadhikena_square(5)["answer"], 25)
        self.assertEqual(ekadhikena_square(995)["answer"], 995 ** 2)
        self.assertEqual(ekadhikena_square(999995)["answer"], 999995 ** 2)

    def test_square5_all_up_to_100000(self):
        for n in range(5, 100000, 10):
            self.assertEqual(ekadhikena_square(n)["answer"], n * n, n)


class TestLexicalAnalysis(unittest.TestCase):
    def test_tokens_for_valid_instruction(self):
        tokens, errors = lexical_analysis("NEARBASE 98 97")
        self.assertEqual(errors, [])
        self.assertEqual([t.type for t in tokens], ["COMMAND", "INTEGER", "INTEGER"])
        self.assertEqual([t.value for t in tokens], ["NEARBASE", "98", "97"])

    def test_command_is_case_insensitive(self):
        tokens, _ = lexical_analysis("square5 35")
        self.assertEqual(tokens[0].type, "COMMAND")
        self.assertEqual(tokens[0].value, "SQUARE5")

    def test_unknown_word_is_ident(self):
        tokens, errors = lexical_analysis("ADD 1 2")
        self.assertEqual(errors, [])
        self.assertEqual(tokens[0].type, "IDENT")

    def test_decimal_is_float_token(self):
        tokens, _ = lexical_analysis("MULTIPLY 2.5 3")
        self.assertEqual(tokens[1].type, "FLOAT")

    def test_illegal_character(self):
        _, errors = lexical_analysis("MULTIPLY 12;3 4")
        self.assertEqual(len(errors), 1)
        self.assertIn("Illegal character", errors[0])

    def test_empty_and_blank(self):
        self.assertTrue(lexical_analysis("")[1])
        self.assertTrue(lexical_analysis("    ")[1])


class TestSyntaxAnalysis(unittest.TestCase):
    def parse(self, text):
        tokens, _ = lexical_analysis(text)
        return syntax_analysis(tokens)

    def test_valid_commands(self):
        for text, count in [("NEARBASE 98 97", 2), ("MULTIPLY 23 14", 2), ("SQUARE5 35", 1)]:
            tree, errors = self.parse(text)
            self.assertEqual(errors, [], text)
            self.assertEqual(len(tree["operands"]), count)

    def test_unsupported_command(self):
        tree, errors = self.parse("DIVIDE 10 2")
        self.assertIsNone(tree)
        self.assertIn("Unsupported command", errors[0])

    def test_missing_command(self):
        tree, errors = self.parse("98 97")
        self.assertIsNone(tree)
        self.assertTrue(errors)

    def test_wrong_operand_counts(self):
        for text in ["NEARBASE 98", "NEARBASE 98 97 96", "MULTIPLY", "SQUARE5", "SQUARE5 5 5"]:
            tree, errors = self.parse(text)
            self.assertIsNone(tree, text)
            self.assertTrue(any("operand" in e for e in errors), text)

    def test_non_integer_operands(self):
        for text in ["MULTIPLY 2.5 3", "MULTIPLY abc 3", "SQUARE5 NEARBASE"]:
            tree, errors = self.parse(text)
            self.assertIsNone(tree, text)
            self.assertTrue(errors, text)


class TestSemanticAnalysis(unittest.TestCase):
    def check(self, command, *operands):
        return semantic_analysis({"command": command, "operands": [str(o) for o in operands]})

    def test_valid_inputs(self):
        self.assertEqual(self.check("NEARBASE", 98, 97)[1], [])
        self.assertEqual(self.check("MULTIPLY", 23, 14)[1], [])
        self.assertEqual(self.check("SQUARE5", 35)[1], [])

    def test_nearbase_selects_common_base(self):
        checked, _ = self.check("NEARBASE", 98, 97)
        self.assertEqual(checked["base"], 100)
        checked, _ = self.check("NEARBASE", 1003, 996)
        self.assertEqual(checked["base"], 1000)

    def test_nearbase_rejects_different_bases(self):
        checked, errors = self.check("NEARBASE", 98, 1003)
        self.assertIsNone(checked)
        self.assertIn("different bases", errors[0])

    def test_nearbase_rejects_numbers_far_from_base(self):
        self.assertTrue(self.check("NEARBASE", 300, 301)[1])
        self.assertTrue(self.check("NEARBASE", 3, 4)[1])

    def test_nearbase_rejects_zero(self):
        self.assertTrue(self.check("NEARBASE", 0, 98)[1])

    def test_negative_numbers_rejected(self):
        for command, ops in [("MULTIPLY", (-3, 4)), ("NEARBASE", (-98, 97)), ("SQUARE5", (-5,))]:
            self.assertTrue(self.check(command, *ops)[1], command)

    def test_too_many_digits_rejected(self):
        too_big = 10 ** MAX_DIGITS
        self.assertTrue(self.check("MULTIPLY", too_big, 2)[1])
        self.assertTrue(self.check("SQUARE5", too_big + 5)[1])

    def test_square5_must_end_in_5(self):
        checked, errors = self.check("SQUARE5", 36)
        self.assertIsNone(checked)
        self.assertIn("does not end in 5", errors[0])

    def test_choose_base(self):
        self.assertEqual(choose_base(98), 100)
        self.assertEqual(choose_base(1012), 1000)
        self.assertEqual(choose_base(55), 100)   # tie between 10 and 100 -> larger base


class TestIntermediateRepresentation(unittest.TestCase):
    def test_nearbase_ir(self):
        ir = generate_ir({"command": "NEARBASE", "operands": [98, 97], "base": 100})
        self.assertEqual(ir["operation"], "NEAR_BASE_MULTIPLY")
        self.assertEqual(ir["operands"], [98, 97])
        self.assertEqual(ir["parameters"]["deviations"], [-2, -3])
        self.assertEqual(ir["parameters"]["base_zeros"], 2)

    def test_multiply_ir(self):
        ir = generate_ir({"command": "MULTIPLY", "operands": [23, 14]})
        self.assertEqual(ir["operation"], "VERTICAL_CROSSWISE_MULTIPLY")
        self.assertEqual(ir["parameters"]["digits"], [[2, 3], [1, 4]])

    def test_square5_ir(self):
        ir = generate_ir({"command": "SQUARE5", "operands": [35]})
        self.assertEqual(ir["operation"], "SQUARE_ENDING_IN_5")
        self.assertEqual(ir["parameters"]["prefix"], 3)

    def test_unknown_operation_cannot_execute(self):
        with self.assertRaises(ExecutionError):
            execute_operation({"operation": "MYSTERY", "operands": [1, 2], "parameters": {}})

    def test_execution_is_correct_for_any_valid_ir_base(self):
        # The IR here uses base 10 for 98 and 97 (not what semantic analysis would choose).
        # Nikhilam is algebraically valid for any base, so the answer must still be correct.
        ir = {"operation": "NEAR_BASE_MULTIPLY", "operands": [98, 97],
              "parameters": {"base": 10, "base_zeros": 1, "deviations": [88, 87]}}
        self.assertEqual(execute_operation(ir)["answer"], 98 * 97)


class TestFullPipeline(unittest.TestCase):
    def test_required_examples(self):
        for source, expected in [("NEARBASE 98 97", 9506),
                                 ("MULTIPLY 23 14", 322),
                                 ("SQUARE5 35", 1225)]:
            result = compile_and_run(source)
            self.assertTrue(result.success, source)
            self.assertEqual(result.answer, expected, source)
            self.assertEqual(len(result.stages), 6)
            self.assertTrue(all(s.status == "success" for s in result.stages))
            self.assertTrue(result.steps)
            self.assertIsNotNone(result.ir)

    def test_build_instruction(self):
        self.assertEqual(build_instruction("NEARBASE", [" 98 ", "97"]), "NEARBASE 98 97")
        self.assertEqual(build_instruction("MULTIPLY", ["23", ""]), "MULTIPLY 23")

    def test_failure_stops_pipeline_and_skips_later_stages(self):
        cases = {
            "": "1. Source Instruction",
            "MULTIPLY 12;3 4": "2. Lexical Analysis",
            "ADD 1 2": "3. Syntax Analysis",
            "NEARBASE 98": "3. Syntax Analysis",
            "MULTIPLY 2.5 3": "3. Syntax Analysis",
            "SQUARE5 36": "4. Semantic Analysis",
            "NEARBASE 98 1003": "4. Semantic Analysis",
            "MULTIPLY -4 3": "4. Semantic Analysis",
        }
        for source, failed in cases.items():
            result = compile_and_run(source)
            self.assertFalse(result.success, source)
            self.assertIsNone(result.answer, source)
            self.assertEqual(result.failed_stage, failed, source)
            self.assertEqual(len(result.stages), 6, source)
            index = [s.name for s in result.stages].index(failed)
            self.assertEqual(result.stages[index].status, "error")
            self.assertTrue(result.stages[index].errors)
            for later in result.stages[index + 1:]:
                self.assertEqual(later.status, "skipped")
            for earlier in result.stages[:index]:
                self.assertEqual(earlier.status, "success")

    def test_ui_style_bad_inputs(self):
        # Inputs as they would arrive from the web form.
        for command, fields in [("NEARBASE", ["", "97"]), ("MULTIPLY", ["abc", "14"]),
                                ("SQUARE5", ["3.5"]), ("SQUARE5", [""]), ("MULTIPLY", ["23", "1 4"])]:
            result = compile_and_run(build_instruction(command, fields))
            self.assertFalse(result.success, (command, fields))
            self.assertIsNone(result.answer)

    def test_random_valid_pipeline_runs_match_python_arithmetic(self):
        rng = random.Random(7)
        for _ in range(300):
            a, b = rng.randint(0, 999999), rng.randint(0, 999999)
            result = compile_and_run(f"MULTIPLY {a} {b}")
            self.assertEqual(result.answer, a * b)
        for _ in range(300):
            n = rng.randint(0, 99999) * 10 + 5
            result = compile_and_run(f"SQUARE5 {n}")
            self.assertEqual(result.answer, n * n)
        for _ in range(300):
            a, b = rng.randint(80, 120), rng.randint(80, 120)
            result = compile_and_run(f"NEARBASE {a} {b}")
            self.assertTrue(result.success, (a, b))
            self.assertEqual(result.answer, a * b)


if __name__ == "__main__":
    unittest.main()
