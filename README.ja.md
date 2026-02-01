# RLM - Claude Codeのための無限メモリ

> Claude Codeのセッションは `/compact` のたびにすべてを忘れます。RLMはそれを解決します。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)

[English](README.md) | [Français](README.fr.md) | 日本語

---

## 課題

Claude Codeには**コンテキストウィンドウの制限**があります。上限に達すると：
- `/compact` で会話履歴が消去される
- 過去の決定事項、知見、コンテキストが**失われる**
- 同じことを繰り返し説明する羽目になり、Claudeも同じミスを繰り返す。生産性が低下する。

## 解決策

**RLM** は、Claude Codeに**セッションをまたぐ永続的なメモリ**を提供するMCPサーバーです：

```
あなた: 「クライアントは500mlボトルを希望していることを覚えておいて」
     → 保存完了。永久に。すべてのセッションで。

あなた: 「APIアーキテクチャについて何を決めたっけ？」
     → Claudeがメモリを検索して回答を見つけます。
```

**インストールはたった3行。ツール14個。設定不要。**

---

## クイックインストール

```bash
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude
./install.sh
```

Claude Codeを再起動すれば完了です。

**必要環境**: Python 3.10+、Claude Code CLI

---

## 仕組み

```
                    ┌─────────────────────────┐
                    │     Claude Code CLI      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    RLM MCPサーバー        │
                    │    (14ツール)             │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────▼────────┐ ┌──────▼──────┐ ┌──────────▼─────────┐
    │   インサイト      │ │   チャンク   │ │    リテンション      │
    │ (重要な決定事項、  │ │ (完全な会話  │ │ (自動アーカイブ、    │
    │  事実、設定)      │ │  履歴)       │ │  復元、パージ)       │
    └──────────────────┘ └─────────────┘ └────────────────────┘
```

### コンテキスト消失前の自動保存

RLMはClaude Codeの `/compact` イベントにフックします。コンテキストが消去される前に、RLMが**自動的にスナップショットを保存**します。操作は不要です。

### 2つのメモリシステム

| システム | 保存内容 | 使い方 |
|---------|---------|--------|
| **インサイト** | 重要な決定事項、事実、設定 | `rlm_remember()` / `rlm_recall()` |
| **チャンク** | 完全な会話セグメント | `rlm_chunk()` / `rlm_peek()` / `rlm_grep()` |

---

## 機能

### メモリとインサイト
- **`rlm_remember`** - 決定事項、事実、設定をカテゴリと重要度レベル付きで保存
- **`rlm_recall`** - キーワード、カテゴリ、重要度でインサイトを検索
- **`rlm_forget`** - インサイトを削除
- **`rlm_status`** - システム概要（インサイト数、チャンク統計、アクセスメトリクス）

### 会話履歴
- **`rlm_chunk`** - 会話セグメントを永続ストレージに保存
- **`rlm_peek`** - チャンクを読み取り（全体または行範囲を指定して部分的に）
- **`rlm_grep`** - 全チャンクにわたる正規表現検索（＋タイプミス耐性のあいまい検索）
- **`rlm_search`** - BM25ランキング検索（FR/EN対応、アクセント正規化）
- **`rlm_list_chunks`** - メタデータ付きの全チャンク一覧

### マルチプロジェクト管理
- **`rlm_sessions`** - プロジェクトまたはドメインごとにセッションを閲覧
- **`rlm_domains`** - カテゴリ分類用の利用可能なドメイン一覧
- gitまたは作業ディレクトリからプロジェクトを自動検出
- すべての検索ツールでクロスプロジェクトフィルタリング対応

### スマートリテンション
- **`rlm_retention_preview`** - アーカイブ対象のプレビュー（ドライラン）
- **`rlm_retention_run`** - 古い未使用チャンクをアーカイブし、非常に古いものをパージ
- **`rlm_restore`** - アーカイブされたチャンクを復元
- 3ゾーンライフサイクル: **アクティブ** &rarr; **アーカイブ** (.gz) &rarr; **パージ**
- 免除システム: 重要タグ、頻繁なアクセス、キーワードがチャンクを保護

### 自動チャンキング（フック）
- **PreCompactフック**: `/compact` または自動コンパクト前の自動スナップショット
- **PostToolUseフック**: チャンク操作後の統計追跡
- ユーザー主導の思想: チャンクのタイミングはあなたが決め、システムは消失前に保存

### サブエージェントスキル
- **`/rlm-analyze`** - 隔離されたサブエージェントで単一チャンクを分析
- **`/rlm-parallel`** - 複数チャンクを並列分析（MIT RLM論文のMap-Reduceパターン）

---

## 比較

| 機能 | 素のコンテキスト | Letta/MemGPT | **RLM** |
|------|-----------------|--------------|---------|
| 永続メモリ | なし | あり | **あり** |
| Claude Codeで動作 | N/A | いいえ（独自ランタイム） | **ネイティブMCP** |
| コンパクト前の自動保存 | なし | N/A | **あり（フック）** |
| 検索（正規表現 + BM25） | なし | 基本的 | **あり** |
| あいまい検索（タイプミス耐性） | なし | なし | **あり** |
| マルチプロジェクト対応 | なし | なし | **あり** |
| スマートリテンション（アーカイブ/パージ） | なし | 基本的 | **あり** |
| サブエージェント分析 | なし | なし | **あり** |
| 設定不要のインストール | N/A | 複雑 | **3行** |
| FR/EN対応 | N/A | ENのみ | **両方** |
| コスト | 無料 | セルフホスト | **無料** |

---

## 使用例

### インサイトの保存と呼び出し

```python
# 重要な決定事項を保存
rlm_remember("バックエンドがすべてのデータの信頼できる唯一の情報源",
             category="decision", importance="high",
             tags="architecture,backend")

# 後で検索
rlm_recall(query="信頼できる情報源")
rlm_recall(category="decision")
```

### 会話履歴の管理

```python
# 重要な議論を保存
rlm_chunk("API再設計についての議論... [長いコンテンツ]",
          summary="API v2アーキテクチャの決定事項",
          tags="api,architecture")

# 全履歴を横断検索
rlm_search("APIアーキテクチャの決定事項")      # BM25ランキング
rlm_grep("authentication", fuzzy=True)          # タイプミス耐性

# 特定のチャンクを読み取り
rlm_peek("2026-01-18_MyProject_001")
```

### マルチプロジェクト管理

```python
# プロジェクトでフィルタリング
rlm_search("デプロイの問題", project="MyApp")
rlm_grep("database", project="MyApp", domain="infra")

# セッションを閲覧
rlm_sessions(project="MyApp")
```

---

## プロジェクト構成

```
rlm-claude/
├── mcp_server/
│   ├── server.py              # MCPサーバー（14ツール）
│   └── tools/
│       ├── memory.py          # インサイト（remember/recall/forget）
│       ├── navigation.py      # チャンク（chunk/peek/grep/list）
│       ├── search.py          # BM25検索エンジン
│       ├── tokenizer_fr.py    # FR/ENトークナイゼーション
│       ├── sessions.py        # マルチセッション管理
│       └── retention.py       # アーカイブ/復元/パージのライフサイクル
│
├── hooks/                     # Claude Codeフック
│   ├── pre_compact_chunk.py   # /compact前の自動保存
│   ├── auto_chunk_check.py    # ターン追跡
│   └── reset_chunk_counter.py # チャンク後の統計リセット
│
├── templates/
│   ├── hooks_settings.json    # フック設定テンプレート
│   ├── CLAUDE_RLM_SNIPPET.md  # CLAUDE.md用の指示
│   └── skills/                # サブエージェントスキル
│
├── context/                   # ストレージ（インストール時に作成、git-ignored）
│   ├── session_memory.json    # インサイト
│   ├── index.json             # チャンクインデックス
│   ├── chunks/                # 会話履歴
│   ├── archive/               # 圧縮アーカイブ（.gz）
│   └── sessions.json          # セッションインデックス
│
├── install.sh                 # ワンコマンドインストーラー
└── README.md
```

---

## 設定

### フック設定

インストーラーが `~/.claude/settings.json` にフックを自動設定します：

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "manual",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py" }]
      },
      {
        "matcher": "auto",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py" }]
      }
    ],
    "PostToolUse": [{
      "matcher": "mcp__rlm-server__rlm_chunk",
      "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/reset_chunk_counter.py" }]
    }]
  }
}
```

### カスタムドメイン

カスタムドメインでチャンクをトピックごとに整理：

```json
{
  "domains": {
    "my_project": {
      "description": "プロジェクトのドメイン",
      "list": ["feature", "bugfix", "infra", "docs"]
    }
  }
}
```

インストール後に `context/domains.json` を編集してください。

---

## 手動インストール

手動でインストールする場合：

```bash
pip install -r mcp_server/requirements.txt
claude mcp add rlm-server -- python3 $(pwd)/mcp_server/server.py
mkdir -p ~/.claude/rlm/hooks
cp hooks/*.py ~/.claude/rlm/hooks/
chmod +x ~/.claude/rlm/hooks/*.py
mkdir -p ~/.claude/skills/rlm-analyze ~/.claude/skills/rlm-parallel
cp templates/skills/rlm-analyze/skill.md ~/.claude/skills/rlm-analyze/
cp templates/skills/rlm-parallel/skill.md ~/.claude/skills/rlm-parallel/
```

その後、`~/.claude/settings.json` でフックを設定してください（上記参照）。

---

## トラブルシューティング

### 「MCPサーバーが見つからない」

```bash
claude mcp list                    # サーバーを確認
claude mcp remove rlm-server       # 存在する場合は削除
claude mcp add rlm-server -- python3 /path/to/mcp_server/server.py
```

### 「フックが動作しない」

```bash
python3 ~/.claude/rlm/hooks/auto_chunk_check.py   # 手動でテスト
cat ~/.claude/rlm/chunk_state.json                  # 状態を確認
cat ~/.claude/settings.json | grep -A 10 "hooks"    # 設定を検証
```

---

## ロードマップ

- [x] **フェーズ1**: メモリツール（remember/recall/forget/status）
- [x] **フェーズ2**: ナビゲーションツール（chunk/peek/grep/list）
- [x] **フェーズ3**: 自動チャンキング＋サブエージェントスキル
- [x] **フェーズ4**: プロダクション（自動要約、重複排除、アクセス追跡）
- [x] **フェーズ5**: 高度な機能（BM25検索、あいまいgrep、マルチセッション、リテンション）
- [ ] **フェーズ6**: プロダクションレディ（テスト、CI/CD、PyPI）

---

## インスピレーション

- [RLM論文 (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., 2025年12月 - "Recursive Language Models"
- [Letta/MemGPT](https://github.com/letta-ai/letta) - AIエージェントメモリフレームワーク
- [MCP仕様](https://modelcontextprotocol.io/specification)
- [Claude Codeフック](https://docs.anthropic.com/claude-code/hooks)

---

## 著者

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.5（共同R&D）

## ライセンス

MITライセンス - [LICENSE](LICENSE) を参照
