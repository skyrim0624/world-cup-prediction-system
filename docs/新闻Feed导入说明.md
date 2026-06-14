# 新闻 Feed 导入说明

日期：2026-06-14

## 目标

把公开 RSS / Atom 新闻 Feed 转成 `backend/data_files/raw-news.json` 里的原始新闻线索，再交给来源评级、自动多源交叉验证、人工审核和快照重建流程处理。

Feed 导入不是绕过模型审核的入口。

## 命令

```bash
npm run import:news-feed -- \
  --input /path/to/feed.xml \
  --source reuters \
  --team brazil
```

可选指定 raw-news 路径：

```bash
python3 scripts/import_news_feed.py \
  --input /path/to/feed.xml \
  --raw-news-path backend/data_files/raw-news.json \
  --source reuters \
  --team brazil
```

## 输出字段

导入器会为每条 Feed item 生成：

- `id`：来源 + 链接哈希。
- `title`：Feed 标题。
- `summary`：Feed description / summary。
- `source`：命令传入的来源 key，必须和 `news-sources.json` 对齐。
- `team`：命令传入的球队 key，可为空。
- `status`：默认 `single_source`。
- `published_at`：Feed 发布时间；缺失时为 `待确认`。
- `url`：Feed 链接。

## 去重

导入器按 `url` 跳过已存在条目，避免定时任务重复写入同一新闻。

## 来源校验

- CLI 和日更流水线都会校验 `source` 是否存在于 `backend/data_files/news-sources.json`。
- 未知来源会直接失败，不会写入 `raw-news.json`。
- 这样可以避免未评级来源绕过 S/A/B/C/D 来源权重体系。

## 后续流程

1. 导入 Feed 到 raw-news。
2. 打开事件审核面板查看新增线索。
3. 多源重复线索会自动升级为 `multi_source`。
4. 人工确认或忽略剩余待审核线索。
5. 重建预测快照。
