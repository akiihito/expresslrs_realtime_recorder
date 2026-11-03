#!/usr/bin/env python3
"""コードとドキュメントの食い違いを機械的に検出する。

CLAUDE.md「開発ルール」の対応表のうち、**列挙できるもの**だけを自動で確かめる。
ピン番号や `921600` のような1つの事実が6つのドキュメントに重複しているため、
コードを1行変えると最大6箇所を直す必要があり、作業中に開くのはCLAUDE.mdだけ
なので残りは次に読む人が困るまで誰も気づかない。そこを埋めるのが目的。

確認するもの:
  1. UARTコマンド   — `dbg_poll_commands()` の case が全ドキュメントに載っているか
  2. GPIO番号       — `*_PIN` の定義が各ドキュメントのピン表に載っているか
  3. 調整パラメータ  — `*_DEFAULT_PCT` がCLAUDE.mdで説明されているか
  4. 既定値そのもの  — CLAUDE.mdの「既定N%」が `*_DEFAULT_PCT` の値と一致するか
  5. 物理ピン番号    — 「GPn (pinM)」のMがPicoの実際のピン番号か
  6. Markdownの表   — 区切り行を欠いた孤立した `|` 行が無いか
  7. リンク切れ      — 相対リンクの先のファイルが存在するか
  8. 部品表          — hardware/README.md の参照記号が基板と一致するか

4〜8 は実際に起きた事故から足した:
  - 4: `STICK_EXPO_DEFAULT_PCT` がCLAUDE.md内で 50% と 85% の両方に書かれていた
  - 5: `docs/perfboard.html` が GP14 を pin18（実際はGND）と書いていた
  - 6: 部品表の途中に見出しを挿し込んで、以降のC1〜C4の行が表から外れ
       「キャパシタの仕様が載っていない」状態になっていた

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


def tunable_values(main_c):
    """#define *_DEFAULT_PCT <数字> を {名前: 値} で返す。"""
    return {n: int(v) for n, v in
            re.findall(r"#define\s+(\w+_DEFAULT_PCT)\s+(\d+)", main_c)}


# Picoの左列 pin1..20。GNDは pin3/8/13/18 で、GPIOはそれ以外。
PICO_LEFT = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND",
             "GP6", "GP7", "GP8", "GP9", "GND", "GP10", "GP11", "GP12",
             "GP13", "GND", "GP14", "GP15"]
GP_TO_PIN = {gp: i + 1 for i, gp in enumerate(PICO_LEFT) if gp != "GND"}

SKIP_DIRS = ("build/", "build_test/", "references/")


def doc_files(*suffixes):
    """リポジトリ内のドキュメント。生成物と第三者のソースは見ない。"""
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT).as_posix()
        if path.is_file() and rel.endswith(suffixes) \
                and not rel.startswith(SKIP_DIRS):
            yield rel, path.read_text(encoding="utf-8")


def check_default_values(main_c, problems):
    """CLAUDE.mdの「既定N%」が実際の #define と合っているか。

    「既定」という語の前後60文字にマクロ名がある組だけを見る。
    `0=線形/100=3乗` のような説明の数字を拾わないため。
    """
    claude = read("CLAUDE.md")
    values = tunable_values(main_c)
    for m in re.finditer(r"既定\s*\**\s*(\d+)\s*%", claude):
        near = claude[max(0, m.start() - 60):m.end() + 60]
        for name, want in values.items():
            if name in near and int(m.group(1)) != want:
                line = claude[:m.start()].count("\n") + 1
                problems.append("CLAUDE.md:%d: %s を 既定%s%% と書いているが "
                                "src/main.c は %d%%"
                                % (line, name, m.group(1), want))


def check_pin_numbers(problems):
    """「GPn (pinM)」のMがPicoの実際の物理ピン番号か。"""
    pat = re.compile(r"GP(\d+)\s*\(?\s*pin\s*(\d+)\s*\)?", re.I)
    for rel, text in doc_files(".md", ".html"):
        for m in pat.finditer(text):
            want = GP_TO_PIN.get("GP" + m.group(1))
            if want is not None and want != int(m.group(2)):
                line = text[:m.start()].count("\n") + 1
                problems.append("%s:%d: %s — GP%s は pin%d"
                                % (rel, line, m.group(0), m.group(1), want))


def check_markdown_tables(problems):
    """表の区切り行（|---|）を欠いたまま始まる `|` 行を見つける。

    見出しや段落を表の途中に挿し込むと以降の行が表から外れ、GitHubでは
    生の `| C1 | ... |` が並ぶ。読む側には「その部品が載っていない」ように見える。
    """
    sep = re.compile(r"\|[\s:|-]+\|")
    for rel, text in doc_files(".md"):
        lines = text.split("\n")
        in_table = False
        for i, raw in enumerate(lines):
            line = raw.strip()
            if line.startswith("|") and line.endswith("|"):
                if not in_table:
                    nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if sep.fullmatch(nxt):
                        in_table = True
                    else:
                        problems.append("%s:%d: 表の外にある `|` 行 — 区切り行が"
                                        "無い（表の途中に見出しを入れた？）: %s"
                                        % (rel, i + 1, line[:40]))
            else:
                in_table = False


def check_links(problems):
    """相対リンクの先が存在するか。"""
    pat = re.compile(r"\]\(([^)#\s]+)|href=\"([^\"#:]+)\"")
    for rel, text in doc_files(".md", ".html"):
        for m in pat.finditer(text):
            target = m.group(1) or m.group(2)
            if target.startswith(("http", "mailto", "#", "data:", "{{")):
                continue
            if not (ROOT / rel).parent.joinpath(target).resolve().exists():
                line = text[:m.start()].count("\n") + 1
                problems.append("%s:%d: リンク切れ %s" % (rel, line, target))


def check_parts_table(problems):
    """hardware/README.md の部品表の参照記号が、基板と過不足なく一致するか。"""
    table = read("hardware/README.md").split("## 部品")[1] \
        .split("### ユニバーサル基板")[0]
    listed = set()
    for cell in re.findall(r"^\|\s*([A-Z][A-Z0-9,–\- ]*?)\s*\|", table, re.M):
        for part in cell.split(","):
            part = part.strip()
            span = re.fullmatch(r"([A-Z]+)(\d+)[–-][A-Z]*(\d+)", part)
            if span:
                listed.update("%s%d" % (span.group(1), i) for i in
                              range(int(span.group(2)), int(span.group(3)) + 1))
            elif re.fullmatch(r"[A-Z]+\d+", part):
                listed.add(part)
    board = set(re.findall(r'\(property "Reference" "([A-Z]+\d+)"',
                           read("hardware/recorder.kicad_pcb")))
    if listed - board:
        problems.append("hardware/README.md: 部品表の %s が基板に無い"
                        % " ".join(sorted(listed - board)))
    if board - listed:
        problems.append("hardware/README.md: 基板の %s が部品表に無い"
                        % " ".join(sorted(board - listed)))


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

    # --- 4〜8. 値・ピン番号・表の構造・リンク・部品表 ---
    check_default_values(main_c, problems)
    check_pin_numbers(problems)
    check_markdown_tables(problems)
    check_links(problems)
    check_parts_table(problems)

    print("検査: UARTコマンド %d個 / GPIO %d本 / 調整パラメータ %d個 / "
          "ドキュメント %d本"
          % (len(cmds), len(pins), len(tunables(main_c)),
             len(list(doc_files(".md", ".html")))))
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
