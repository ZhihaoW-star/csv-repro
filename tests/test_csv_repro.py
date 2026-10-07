import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from csv_repro import ReproError, make_bundle

SCRIPT = Path(__file__).resolve().parents[1] / 'csv_repro.py'

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root / 'out'
    def tearDown(self):
        self.tmp.cleanup()
    def source(self, name, headers, rows, delimiter=',', bom=False):
        p = self.root / name
        with p.open('w', encoding='utf-8-sig' if bom else 'utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(headers); writer.writerows(rows)
        return p
    def read(self, table=1):
        with (self.output / f'table_{table}.csv').open(newline='') as f:
            return list(csv.reader(f))
    def test_default_artifacts_contain_no_original_values_headers_or_paths(self):
        p = self.source('SENSITIVE_SOURCE_NAME.csv', ['CONFIDENTIAL_HEADER', 'email'], [['PRIVATE_SENTINEL', 'secret@example.invalid'], ['PRIVATE_SENTINEL', '']])
        before = p.read_bytes()
        report = make_bundle([p], self.output)
        exported = b'\n'.join(x.read_bytes() for x in self.output.iterdir())
        for raw in [p.name, str(p), 'CONFIDENTIAL_HEADER', 'PRIVATE_SENTINEL', 'secret@example.invalid', 'email']:
            self.assertNotIn(raw.encode(), exported)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(self.read()[1][0], self.read()[2][0])
        self.assertEqual(self.read()[2][1], '')
        self.assertEqual(report['tables'][0]['selected_data_rows'], 2)
    def test_bom_multiline_unicode_and_delimiters(self):
        p = self.source('input.tsv', ['客户', 'note'], [['示例', 'line one\nline two'], ['other', 'a,b']], '\t', True)
        make_bundle([p], self.output, delimiter='\t', keeps=['1:2'])
        self.assertEqual(self.read()[1][1], 'line one\nline two')
        self.assertEqual(self.read()[2][1], 'a,b')
        self.assertIn('line one<br>line two', (self.output / 'example.md').read_text())
    def test_cross_table_links_preserve_equality_without_kept_ids(self):
        a = self.source('a.csv', ['id'], [['X'], ['Y']])
        b = self.source('b.csv', ['id', 'fk'], [['Z', 'X'], ['W', 'Y']])
        make_bundle([a, b], self.output, links=['1:1,2:2'])
        left, right = self.read(1), self.read(2)
        self.assertEqual(left[1][0], right[1][1]); self.assertEqual(left[2][0], right[2][1])
        self.assertNotEqual(right[1][0], right[1][1])
    def test_overlapping_links_are_transitive_and_order_independent(self):
        p = self.source('a.csv', ['a', 'b', 'c'], [['X', 'X', 'X']])
        make_bundle([p], self.output, links=['1:2,1:3', '1:1,1:2'])
        self.assertEqual(len(set(self.read()[1])), 1)
        other = self.root / 'other'
        make_bundle([p], other, links=['1:1,1:2', '1:2,1:3'])
        for name in ['report.json', 'table_1.csv']:
            self.assertEqual((self.output / name).read_bytes(), (other / name).read_bytes())
    def test_include_logical_row_counts_multiline_as_one_and_keeps_order(self):
        p = self.source('a.csv', ['a'], [['line\nline'], ['B'], ['C'], ['D']])
        make_bundle([p], self.output, rows=1, includes=['1:4', '1:2', '1:4'], keeps=['1:1'])
        self.assertEqual([r[0] for r in self.read()[1:]], ['line\nline', 'B', 'D'])
    def test_duplicate_header_names_are_positionally_addressable(self):
        p = self.source('a.csv', ['id', 'id'], [['secret', 'public']])
        make_bundle([p], self.output, keeps=['1:2'])
        self.assertEqual(self.read()[1][1], 'public'); self.assertNotEqual(self.read()[1][0], 'secret')
    def test_existing_output_is_never_overwritten(self):
        p = self.source('a.csv', ['id'], [['X']]); self.output.mkdir()
        sentinel = self.output / 'important'; sentinel.write_text('do not overwrite')
        with self.assertRaises(ReproError): make_bundle([p], self.output)
        self.assertEqual(sentinel.read_text(), 'do not overwrite')
    def test_late_ragged_row_rejected_even_outside_sample(self):
        p = self.source('a.csv', ['a', 'b'], [['X', 'Y'], ['X']])
        with self.assertRaises(ReproError): make_bundle([p], self.output, rows=1)
        self.assertFalse(self.output.exists())
    def test_invalid_policy_and_out_of_range_rows_create_no_output(self):
        p = self.source('a.csv', ['id'], [['X']])
        cases = [dict(keeps=['0:1']), dict(keeps=['1:2']), dict(links=['1:1']), dict(links=['1:1,2:1']), dict(links=['1:1,1:1'], keeps=['1:1']), dict(includes=['1:2']), dict(includes=['2:1']), dict(rows=-1)]
        for kw in cases:
            with self.subTest(kw=kw), self.assertRaises(ReproError): make_bundle([p], self.output, **kw)
            self.assertFalse(self.output.exists())
    def test_exact_keeps_and_opt_in_spreadsheet_escape(self):
        p = self.source('a.csv', ['=HEADER'], [['  =1+1'], ['-10'], ['@SUM(1)'], ['normal']])
        report = make_bundle([p], self.output, keeps=['1:1'], keep_headers=True)
        self.assertEqual(self.read()[1][0], '  =1+1'); self.assertEqual(report['formula_like_cells'], 4)
        escaped = self.root / 'escaped'
        make_bundle([p], escaped, keeps=['1:1'], keep_headers=True, excel_safe=True)
        with (escaped / 'table_1.csv').open(newline='') as f: rows = list(csv.reader(f))
        self.assertEqual(rows[0][0], "'=HEADER"); self.assertEqual(rows[1][0], "'  =1+1")
        self.assertEqual(rows[2][0], "'-10"); self.assertEqual(rows[4][0], 'normal')
    def test_markdown_kept_values_cannot_make_html_links_or_columns(self):
        p = self.source('a.csv', ['a'], [['<script>alert(1)</script>|[link](https://example.invalid)\n`code`']])
        make_bundle([p], self.output, keeps=['1:1']); md = (self.output / 'example.md').read_text()
        self.assertNotIn('<script>', md); self.assertNotIn('[link]', md)
        self.assertIn('&#124;', md); self.assertIn('<br>', md); self.assertIn('&#96;', md)
    def test_cli_failure_does_not_echo_raw_data_or_source_path(self):
        p = self.root / 'SECRET_FILENAME.csv'; p.write_text('header\n"PRIVATE_SENTINEL\n')
        result = subprocess.run([sys.executable, str(SCRIPT), str(p), '-o', str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('PRIVATE_SENTINEL', result.stdout + result.stderr)
        self.assertNotIn('SECRET_FILENAME', result.stdout + result.stderr); self.assertFalse(self.output.exists())
    def test_cli_missing_input_does_not_echo_filename(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.root / 'PERSONAL_NAME.csv'), '-o', str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2); self.assertNotIn('PERSONAL_NAME', result.stdout + result.stderr)
    def test_full_bundle_is_byte_reproducible_for_same_input_and_policy(self):
        p = self.source('a.csv', ['x'], [['A'], ['B'], ['A']]); make_bundle([p], self.output)
        second = self.root / 'second'; make_bundle([p], second)
        for file in self.output.iterdir(): self.assertEqual(file.read_bytes(), (second / file.name).read_bytes())
        run = subprocess.run([sys.executable, str(self.output / 'repro.py')], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0); self.assertIn('data rows: 3', run.stdout)
    def test_header_only_and_zero_row_bundles(self):
        p = self.source('a.csv', ['a', 'b'], []); make_bundle([p], self.output, rows=0)
        self.assertEqual(self.read(), [['col_1', 'col_2']])
        self.assertEqual(json.loads((self.output / 'report.json').read_text())['tables'][0]['selected_data_rows'], 0)

if __name__ == '__main__': unittest.main()
