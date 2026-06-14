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

ACCESS_CONTENT = [
    {
        "contentKey": "match_prediction",
        "label": "单场胜平负、比分分布和路径传导",
        "requiredProducts": ["single_match", "tournament_pass", "match_pack"],
    },
    {
        "contentKey": "tournament_probabilities",
        "label": "整届晋级概率、冠军概率榜和路径变化",
        "requiredProducts": ["tournament_pass"],
    },
    {
        "contentKey": "key_match_pack",
        "label": "重点场次组包预测和赛后路径复盘",
        "requiredProducts": ["match_pack", "tournament_pass"],
    },
]


def build_access_options(payment_configured: bool = False) -> dict[str, object]:
    product_status = "available" if payment_configured else "payment_pending"
    return {
        "paymentConfigured": payment_configured,
        "products": [{**product, "status": product_status} for product in ACCESS_PRODUCTS],
        "disclaimer": "本产品提供概率分析和模型解释，不提供投注建议。",
    }


def build_access_policy(payment_configured: bool = False) -> dict[str, object]:
    return {
        "paymentConfigured": payment_configured,
        "content": ACCESS_CONTENT,
        "disclaimer": "本产品提供概率分析和模型解释，不提供投注建议。",
    }


def build_access_decision(product_key: str | None, content_key: str, payment_configured: bool = False) -> dict[str, object]:
    content = next((item for item in ACCESS_CONTENT if item["contentKey"] == content_key), None)
    if content is None:
        return {
            "allowed": False,
            "reason": "unknown_content",
            "requiredProducts": [],
        }

    product_keys = {product["key"] for product in ACCESS_PRODUCTS}
    if product_key not in product_keys:
        return {
            "allowed": False,
            "reason": "unknown_product",
            "requiredProducts": content["requiredProducts"],
        }

    if not payment_configured:
        return {
            "allowed": False,
            "reason": "payment_pending",
            "requiredProducts": content["requiredProducts"],
        }

    if product_key not in content["requiredProducts"]:
        return {
            "allowed": False,
            "reason": "product_not_in_scope",
            "requiredProducts": content["requiredProducts"],
        }

    return {
        "allowed": True,
        "reason": "allowed",
        "requiredProducts": content["requiredProducts"],
    }
