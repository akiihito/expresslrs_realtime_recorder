#!/usr/bin/env python3
"""コードとドキュメントの食い違いを機械的に検出する。

CLAUDE.md「開発ルール」の対応表のうち、**列挙できるもの**だけを自動で確かめる。
ピン番号や `921600` のような1つの事実が6つのドキュメントに重複しているため、
コードを1行変えると最大6箇所を直す必要があり、作業中に開くのはCLAUDE.mdだけ
なので残りは次に読む人が困るまで誰も気づかない。そこを埋めるのが目的。

確認するもの:
  1. UARTコマンド  — `dbg_poll_commands()` の case が全ドキュメントに載っているか
  2. GPIO番号      — `*_PIN` の定義が各ドキュメントのピン表に載っているか
  3. 調整パラメータ — `*_DEFAULT_PCT` がCLAUDE.mdで説明されているか

⚠️ ここを通っても「古くない」証明にはならない。文章の中身（挙動の説明や
検証手順の期待値）は人が読むしかない。`printf` の文言を変えた時は、その文言で
リポジトリ全体をgrepして検証手順書の期待値を直すこと。

使い方: python3 scripts/check_docs.py   （食い違いがあれば終了コード1）
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def mentions(doc_text, rel, token):
    """token（1文字のキー or `GP12` のような語）がそのドキュメントに出てくるか。

    Markdownは `` `x` `` 、HTMLは `<td class="k">x</td>` の形で書かれているので
    書式ごとに見る。記号キー（`,` `[` など）を素のまま探すと誤検出するため。
    """
    if len(token) == 1:                      # UARTコマンドのキー
        if rel.endswith(".html"):
            return (">%s<" % token) in doc_text
        return ("`%s`" % token) in doc_text
    # GP番号。GP1 が GP14 に誤マッチしないよう後続の数字を禁止する
    return re.search(r"%s(?![0-9])" % re.escape(token), doc_text) is not None


def uart_commands(main_c):
    """dbg_poll_commands() の case から、小文字・記号のキーを集める。"""
    start = main_c.index("static void dbg_poll_commands")
    end = main_c.index("\n}", start)
    body = main_c[start:end]
    keys = {m.group(1) for m in re.finditer(r"case '(.)':", body)}
    # 'd'/'D' のような大文字別名は同じコマンドなので小文字側だけ見る
    return sorted(k for k in keys if not k.isupper())


def pin_defines(main_c):
    """#define *_PIN <数字> を {定義名: GP番号} で返す。"""
    pins = {}
    for name, num in re.findall(r"#define\s+(\w+_PIN)\s+(\d+)", main_c):
        pins[name] = "GP" + num
    return pins


def tunables(main_c):
    return sorted(set(re.findall(r"#define\s+(\w+_DEFAULT_PCT)\s", main_c)))


def main():
    main_c = read("src/main.c")
    problems = []

    # --- 1. UARTコマンド ---
    cmd_docs = ["CLAUDE.md", "README.md", "docs/controls.html"]
    cmds = uart_commands(main_c)
    for rel in cmd_docs:
        text = read(rel)
        missing = [k for k in cmds if not mentions(text, rel, k)]
        if missing:
            problems.append("%s: UARTコマンド %s の説明が無い"
                            % (rel, " ".join("'%s'" % k for k in missing)))

    # --- 2. GPIO番号 ---
    pin_docs = ["CLAUDE.md", "README.md", "docs/controls.html"]
    pins = pin_defines(main_c)
    for rel in pin_docs:
        text = read(rel)
        missing = sorted({gp for name, gp in pins.items()
                          if not mentions(text, rel, gp)})
        if missing:
            problems.append("%s: %s がピン表に無い" % (rel, " ".join(missing)))

    # --- 3. 調整パラメータ ---
    claude = read("CLAUDE.md")
    missing = [t for t in tunables(main_c) if t not in claude]
    if missing:
        problems.append("CLAUDE.md: %s の説明が無い（既定値を変えられる"
                        "パラメータは仕様節に書く）" % " ".join(missing))

    print("検査: UARTコマンド %d個 / GPIO %d本 / 調整パラメータ %d個"
          % (len(cmds), len(pins), len(tunables(main_c))))
    if problems:
        print("\n食い違いあり:")
        for p in problems:
            print("  - " + p)
        print("\nCLAUDE.md「開発ルール」の影響範囲の対応表も合わせて確認すること。")
        return 1
    print("OK（ただし文章の中身と検証手順の期待値は人が読むこと）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
