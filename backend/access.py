from __future__ import annotations


ACCESS_PRODUCTS = [
    {
        "key": "single_match",
        "name": "单场预测",
        "scope": "解锁一场未开赛比赛的胜平负、比分分布和路径传导",
        "status": "payment_pending",
    },
    {
        "key": "tournament_pass",
        "name": "赛事全周期",
        "scope": "解锁整届赛事的冠军概率榜、路径变化和日更摘要",
        "status": "payment_pending",
    },
    {
        "key": "match_pack",
        "name": "重点场次包",
        "scope": "解锁一组重点比赛的赛前预测和赛后路径复盘",
        "status": "payment_pending",
    },
]


def build_access_options(payment_configured: bool = False) -> dict[str, object]:
    product_status = "available" if payment_configured else "payment_pending"
    return {
        "paymentConfigured": payment_configured,
        "products": [{**product, "status": product_status} for product in ACCESS_PRODUCTS],
        "disclaimer": "本产品提供概率分析和模型解释，不提供投注建议。",
    }
