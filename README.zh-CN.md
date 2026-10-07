# csv-repro

把 CSV 中涉及问题的几行数据变成可以检查、再用于提问的示例：生成替换过的 CSV、Markdown 表格和 Python 加载脚本。**本机处理，无上传，无运行时第三方依赖。** Python 3.10+，MIT 许可。

这叫假名化，不等于匿名化。重复次数、空值、行顺序和关联仍可能透露信息；`--keep` 保留原值。发布前必须检查输出，并确认原来的问题仍可复现。

## 先试虚构数据

```bash
git clone https://github.com/ZhihaoW-star/csv-repro.git
cd csv-repro
python3 csv_repro.py examples/customers.csv examples/orders.csv \
  --link 1:1,2:2 --keep 2:3 -o fixture
python3 fixture/repro.py
```

Windows 可以把 `python3` 换成 `py`。

`1:1` 指第一个输入文件的第一列；`2:2` 指第二个输入文件的第二列。编号均从 1 开始。`--link 1:1,2:2` 让客户编号和订单里的客户编号使用同一套替换值；`--keep 2:3` 明确保留订单金额原值。默认替换所有非空单元格和所有列名，不自动猜测哪些字段敏感。

## 选择真正涉及问题的行

```bash
python3 csv_repro.py input.csv --rows 0 --include-row 1:7 \
  --include-row 1:42 -o selected-fixture
```

行号不含表头；一个带引号的多行单元格仍算一条数据记录。输出保持原行顺序。`--rows` 默认 20；`--include-row` 会在这些行之外再添加指定行。

输出目录必须不存在，工具不覆盖源文件或已有目录。输出含 `table_*.csv`、`example.md`、`report.json`、`repro.py`、`README.txt`，不包含原文件路径或替换字典。

## 使用边界

工具不做隐私合规认证、不识别 PII，不保证替换后仍能复现问题。CSV 会统一成 UTF-8 和逗号分隔，原编码、BOM、引号形式和字节布局不会保留。依赖特定数值、日期或解析细节的问题需要自己调整示例并重新确认。

需要原值时用 `--keep 表号:列号`；需要原列名时用 `--keep-headers`，两者都有披露风险。计划用电子表格打开包含原值的输出时可用 `--excel-safe`，但它会改变以 `= + - @` 等开头的值，也不能保证所有电子表格导入方式安全。

支持 UTF-8 BOM、TSV（`--delimiter tab`）、其他单字符分隔符和显式编码。要求表头与一致列数；空白记录、不规则行不会自动修复。最多十个输入文件，每个 50 MiB，还受 Python CSV 单字段长度限制。

完整选项、对比和限制见 [英文说明](README.md)。运行测试：

```bash
python3 -m unittest discover -s tests -v
```

欢迎用**虚构数据**报告问题，并告诉我们生成后的示例是否仍能复现原错误。如果你觉得有用，欢迎在 GitHub 点 Star，方便下次找到。
