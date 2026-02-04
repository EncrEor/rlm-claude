# RLM - Claude Codeのための無限メモリ

> Claude Codeのセッションは `/compact` のたびにすべてを忘れます。RLMはそれを解決します。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)
[![CI](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/EncrEor/rlm-claude/branch/main/graph/badge.svg)](https://codecov.io/gh/EncrEor/rlm-claude)
[![PyPI version](https://img.shields.io/pypi/v/mcp-rlm-server.svg)](https://pypi.org/project/mcp-rlm-server/)

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

### PyPI経由（推奨）

```bash
pip install mcp-rlm-server[all]
```

### Git経由

```bash
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude
./install.sh
```

Claude Codeを再起動すれば完了です。

**必要環境**: Python 3.10+、Claude Code CLI

### v0.9.0以前からのアップグレード

v0.9.1でソースコードが `mcp_server/` から `src/mcp_server/`（PyPAベストプラクティス）に移動しました。互換性のためのシンボリックリンクが含まれていますが、インストーラーの再実行を推奨します：

```bash
cd rlm-claude
git pull
./install.sh          # MCPサーバーパスを再設定
```

データ（`~/.claude/rlm/`）はそのままです。サーバーパスのみ更新されます。

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
- **`rlm_recall`** - キーワード（複数語トークン化対応）、カテゴリ、重要度でインサイトを検索
- **`rlm_forget`** - インサイトを削除
- **`rlm_status`** - システム概要（インサイト数、チャンク統計、アクセスメトリクス）

### 会話履歴
- **`rlm_chunk`** - 型付きカテゴリ分類で会話セグメントを保存（`snapshot`、`session`、`debug`；`insight`は`rlm_remember`にリダイレクト）
- **`rlm_peek`** - チャンクを読み取り（全体または行範囲を指定して部分的に）
- **`rlm_grep`** - 全チャンクにわたる正規表現検索（＋タイプミス耐性のあいまい検索）
- **`rlm_search`** - ハイブリッド検索：BM25 + セマンティックコサイン類似度（FR/EN対応、アクセント正規化、チャンク＋インサイト統合）
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

### セマンティック検索（オプション）
- **ハイブリッドBM25 + コサイン** - キーワードマッチングとベクトル類似度を組み合わせて関連性を向上
- **自動エンベディング** - 新しいチャンクは作成時に自動的にエンベディングされる
- **2つのプロバイダー** - Model2Vec（高速、256次元）またはFastEmbed（高精度、384次元）
- **グレースフルデグラデーション** - セマンティック依存関係がインストールされていない場合、純粋なBM25にフォールバック

#### プロバイダー比較（108チャンクでのベンチマーク）

| | Model2Vec（デフォルト） | FastEmbed |
|---|---|---|
| **モデル** | `potion-multilingual-128M` | `paraphrase-multilingual-MiniLM-L12-v2` |
| **次元数** | 256 | 384 |
| **108チャンクのエンベディング** | 0.06秒 | 1.30秒 |
| **検索レイテンシ** | 0.1ms/クエリ | 1.5ms/クエリ |
| **メモリ** | 0.1 MB | 0.3 MB |
| **ディスク（モデル）** | ~35 MB | ~230 MB |
| **セマンティック品質** | 良好（キーワード寄り） | より高精度（真のセマンティック） |
| **速度** | **21倍高速** | ベースライン |

プロバイダー間のTop-5結果の重複: ~1.6/5（8クエリ中7つで異なる結果）。FastEmbedはよりセマンティックな意味を捉え、Model2Vecはキーワード類似度に寄る傾向があります。ハイブリッドBM25 + コサイン融合が両方の弱点を補います。

**推奨**: Model2Vec（デフォルト）から始めてください。より高いセマンティック精度が必要で、起動の遅さを許容できる場合のみFastEmbedに切り替えてください。

```bash
# Model2Vec（デフォルト）— 高速、~35 MB
pip install mcp-rlm-server[semantic]

# FastEmbed — より高精度、~230 MB、低速
pip install mcp-rlm-server[semantic-fastembed]
export RLM_EMBEDDING_PROVIDER=fastembed

# 自分のデータで両プロバイダーを比較
python3 scripts/benchmark_providers.py

# 既存チャンクのバックフィル（インストール後に一度実行）
python3 scripts/backfill_embeddings.py
```

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
| 検索（正規表現 + BM25 + セマンティック） | なし | 基本的 | **あり** |
| あいまい検索（タイプミス耐性） | なし | なし | **あり** |
| マルチプロジェクト対応 | なし | なし | **あり** |
| スマートリテンション（アーカイブ/パージ） | なし | 基本的 | **あり** |
| サブエージェント分析 | なし | なし | **あり** |
| 設定不要のインストール | N/A | 複雑 | **3行** |
| FR/EN対応 | N/A | ENのみ | **両方** |
| コスト | 無料 | セルフホスト | **無料** |

---

## 使用例

### セッション開始時（推奨）

```python
# ユニバーサルルールを読み込み（トピックに関係なく適用）
rlm_recall(importance="critical")

# 現在のトピックのコンテキストを読み込み
rlm_recall(query="deployment")

# メモリステータスを確認
rlm_status()
```

### インサイトの保存と呼び出し

```python
# ユニバーサルルールを保存（毎セッション読み込み）
rlm_remember("必ずLOCAL→VPSの順でデプロイ、直接デプロイ禁止",
             category="decision", importance="critical",
             tags="deploy,workflow")

# トピック固有のインサイトを保存
rlm_remember("WeasyPrintのPDFレンダリングにはインラインCSSが必要",
             category="finding", importance="high",
             tags="weasyprint,pdf")

# インサイトを検索
rlm_recall(query="信頼できる情報源")
rlm_recall(category="decision")
rlm_recall(importance="critical")    # 全ユニバーサルルール
```

### 重要度レベル

| レベル | 使用場面 | 読み込みタイミング |
|--------|---------|-------------------|
| `critical` | ユニバーサルルール（トピックに関係なく適用） | 毎セッション |
| `high` | トピック固有のルール | そのトピック作業時 |
| `medium` | 有用だがブロッキングではない情報 | 明示的な検索時 |

**判定テスト**：「全く別のトピックで作業していても、このルールは適用されるか？」 → はい なら `critical`。

### 会話履歴の管理

```python
# 重要な議論を保存（型付き）
rlm_chunk("API再設計についての議論... [長いコンテンツ]",
          summary="API v2アーキテクチャの決定事項",
          tags="api,architecture",
          chunk_type="session")        # または "snapshot", "debug"

# 全履歴を横断検索
rlm_search("APIアーキテクチャの決定事項")      # BM25 + セマンティックランキング
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
├── src/mcp_server/
│   ├── server.py              # MCPサーバー（14ツール）
│   └── tools/
│       ├── memory.py          # インサイト（remember/recall/forget）
│       ├── navigation.py      # チャンク（chunk/peek/grep/list）
│       ├── search.py          # BM25 + セマンティック検索エンジン
│       ├── tokenizer_fr.py    # FR/ENトークナイゼーション
│       ├── sessions.py        # マルチセッション管理
│       ├── retention.py       # アーカイブ/復元/パージのライフサイクル
│       ├── embeddings.py      # エンベディングプロバイダー（Model2Vec、FastEmbed）
│       ├── vecstore.py        # ベクトルストア（.npz）セマンティック検索用
│       └── fileutil.py        # 安全なI/O（アトミック書き込み、パス検証、ロック）
│
├── hooks/                     # Claude Codeフック
│   ├── pre_compact_chunk.py   # /compact前の自動保存（PreCompactフック）
│   └── reset_chunk_counter.py # チャンク後の統計リセット（PostToolUseフック）
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
│   ├── embeddings.npz         # セマンティックベクトル（フェーズ8）
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
pip install -e ".[all]"
claude mcp add rlm-server -- python3 -m mcp_server
mkdir -p ~/.claude/rlm/hooks
cp hooks/*.py ~/.claude/rlm/hooks/
chmod +x ~/.claude/rlm/hooks/*.py
mkdir -p ~/.claude/skills/rlm-analyze ~/.claude/skills/rlm-parallel
cp templates/skills/rlm-analyze/skill.md ~/.claude/skills/rlm-analyze/
cp templates/skills/rlm-parallel/skill.md ~/.claude/skills/rlm-parallel/
```

その後、`~/.claude/settings.json` でフックを設定してください（上記参照）。

## アンインストール

```bash
./uninstall.sh              # インタラクティブ（データの保持/削除を選択）
./uninstall.sh --keep-data  # RLM設定を削除、チャンク/インサイトは保持
./uninstall.sh --all        # すべて削除
./uninstall.sh --dry-run    # 削除対象のプレビュー
```

---

## セキュリティ

RLMには安全な運用のための保護機能が組み込まれています：

- **パストラバーサル防止** - チャンクIDは厳格なホワイトリスト（`[a-zA-Z0-9_.-&]`）で検証され、解決済みパスがストレージディレクトリ内に留まることを確認
- **アトミック書き込み** - すべてのJSONファイルとチャンクファイルはwrite-to-temp-then-renameパターンで書き込まれ、中断やクラッシュ時の破損を防止
- **ファイルロック** - 共有インデックスの並行読み取り-変更-書き込み操作は `fcntl.flock` 排他ロックを使用
- **コンテンツサイズ制限** - チャンクは2 MBに制限、gzip解凍（アーカイブ復元）はリソース枯渇防止のため10 MBに制限
- **SHA-256ハッシュ** - コンテンツの重複排除にSHA-256を使用（MD5ではなく）

すべてのI/Oセキュリティプリミティブは `mcp_server/tools/fileutil.py` に集約されています。

---

## トラブルシューティング

### 「MCPサーバーが見つからない」

```bash
claude mcp list                    # サーバーを確認
claude mcp remove rlm-server       # 存在する場合は削除
claude mcp add rlm-server -- python3 -m mcp_server
```

### 「フックが動作しない」

```bash
cat ~/.claude/settings.json | grep -A 10 "PreCompact"  # フック設定を検証
ls ~/.claude/rlm/hooks/                                  # インストール済みフックを確認
```

---

## ロードマップ

- [x] **フェーズ1**: メモリツール（remember/recall/forget/status）
- [x] **フェーズ2**: ナビゲーションツール（chunk/peek/grep/list）
- [x] **フェーズ3**: 自動チャンキング＋サブエージェントスキル
- [x] **フェーズ4**: プロダクション（自動要約、重複排除、アクセス追跡）
- [x] **フェーズ5**: 高度な機能（BM25検索、あいまいgrep、マルチセッション、リテンション）
- [x] **フェーズ6**: プロダクションレディ（テスト、CI/CD、PyPI）
- [x] **フェーズ7**: MAGMA対応（時間フィルタリング、エンティティ抽出）
- [x] **フェーズ8**: ハイブリッドセマンティック検索（BM25 + コサイン、Model2Vec）
- [x] **フェーズ9**: 型付きチャンキング — `chunk_type` パラメータ（snapshot/session/debug/insightリダイレクト）

---

## インスピレーション

### 研究論文
- [RLM論文 (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., 2025年12月 - "Recursive Language Models" — 基盤アーキテクチャ（chunk/peek/grep、サブエージェント分析）
- [MAGMA (arXiv:2601.03236)](https://arxiv.org/abs/2601.03236) - 2026年1月 - "Memory-Augmented Generation with Memory Agents" — 時間フィルタリング、エンティティ抽出（Phase 7）

### ライブラリ & ツール
- [Model2Vec](https://github.com/MinishLab/model2vec) - 高速セマンティック検索用静的埋め込み（Phase 8）
- [BM25S](https://github.com/xhluca/bm25s) - Python純粋実装の高速BM25（Phase 5）
- [FastEmbed](https://github.com/qdrant/fastembed) - ONNXベースの埋め込み、オプションプロバイダー（Phase 8）
- [Letta/MemGPT](https://github.com/letta-ai/letta) - AIエージェントメモリフレームワーク — 初期インスピレーション

### 標準 & プラットフォーム
- [MCP仕様](https://modelcontextprotocol.io/specification) - Model Context Protocol
- [Claude Codeフック](https://docs.anthropic.com/claude-code/hooks) - PreCompact / PostToolUseフック

---

## 著者

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.5（共同R&D）

## ライセンス

MITライセンス - [LICENSE](LICENSE) を参照
