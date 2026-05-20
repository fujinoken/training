# 2026 年間研修管理システム Ver1.0

## 使い方

1. GitHubで新しいリポジトリを作成
2. `app.py` と `requirements.txt` をアップロード
3. Streamlit CloudでDeploy
4. Main file path は `app.py`

## 機能

- 管理者ダッシュボード
- 研修計画管理
- 研修実施入力
- 研修記録の検索・更新・削除
- 実施率自動計算
- 未実施・不足の自動表示
- 年間実施率グラフ
- Excel出力

## 注意

Streamlit Cloudの無料環境では、SQLiteファイルが再起動時に消える場合があります。
安定運用する場合は、次の段階で Neon PostgreSQL への移行がおすすめです。
