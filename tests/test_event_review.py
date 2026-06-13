import json
import tempfile
import unittest
from pathlib import Path

from backend.event_review import review_raw_news_item


class EventReviewTest(unittest.TestCase):
    def test_review_raw_news_item_updates_status_and_team(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "raw-news.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "weather-watch",
                            "title": "天气待确认",
                            "summary": "高温影响等待确认",
                            "source": "local-weather",
                            "team": None,
                            "status": "single_source",
                            "published_at": "1 小时前",
                            "url": "https://example.com/weather",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            updated = review_raw_news_item(path, "weather-watch", "confirmed", "brazil")
            rows = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "confirmed")
            self.assertEqual(updated["team"], "brazil")
            self.assertEqual(rows[0]["status"], "confirmed")
            self.assertEqual(rows[0]["team"], "brazil")


if __name__ == "__main__":
    unittest.main()
