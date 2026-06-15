import unittest
from random import Random

import backend.model as model_module
from backend.data import (
    DATASET_META,
    EVENTS,
    FIXTURES,
    RAW_NEWS_ITEMS,
    TEAM_PROFILES,
    THIRD_PLACE_COMBINATIONS,
    Fixture,
    NewsSource,
    RawNewsItem,
    TeamEvent,
    action_for_news_item,
    events_from_raw_news,
)
from backend.team_history import load_team_match_history
from backend.model import (
    ROUND_OF_16_MATCHES,
    advanced_metric_impacts,
    apply_event_adjustments,
    apply_fixture_context_adjustments,
    best_third_place_teams,
    build_fixture_context,
    build_finished_match_records,
    build_round_of_32_matches,
    build_score_sampler,
    build_match_prediction,
    build_standings,
    event_confidence_weight,
    event_factor_impacts,
    expected_goals,
    forced_outcome_score,
    group_names,
    is_fixture_upcoming,
    parse_fixture_kickoff,
    rank_group,
    resolve_current_prediction_fixture,
    sample_fixture_score,
    simulate_tournament,
    score_matrix_for_match,
    win_draw_loss,
)
from backend.post_match_review import build_post_match_review


class PredictionModelTest(unittest.TestCase):
    def test_win_draw_loss_sums_to_one(self):
        teams = apply_event_adjustments()
        probabilities = win_draw_loss("brazil", "argentina", teams)
        total = probabilities["home"] + probabilities["draw"] + probabilities["away"]
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_low_reliability_event_does_not_change_team(self):
        teams = apply_event_adjustments()
        self.assertEqual(teams["argentina"].squad, TEAM_PROFILES["argentina"].squad)

    def test_prediction_response_has_core_fields(self):
        prediction = build_match_prediction(1200)
        self.assertIn("scoreOutcomes", prediction)
        self.assertIn("scoreMatrix", prediction)
        self.assertIn("goalMarkets", prediction)
        self.assertIn("fairPrices", prediction)
        self.assertIn("marketSource", prediction)
        self.assertIn("creatorTopics", prediction)
        self.assertIn("scenarioImpacts", prediction)
        self.assertIn("teams", prediction)
        self.assertIn("modelMeta", prediction)
        self.assertGreater(len(prediction["scoreOutcomes"]), 0)
        self.assertGreater(len(prediction["scoreMatrix"]), 0)
        self.assertEqual(len(prediction["goalMarkets"]), 4)
        self.assertEqual(len(prediction["fairPrices"]), 3)
        self.assertEqual(prediction["modelMeta"]["lockedResults"], 9)
        self.assertIn("liveMatches", prediction["modelMeta"])

    def test_post_match_review_identifies_blowout_tail_error_and_target_functions(self):
        fixture = Fixture("germany", "curacao", "小组赛 E 组", "6月14日 13:00 ET", "finished", 7, 1)
        snapshot = {
            "homeTeam": "germany",
            "awayTeam": "curacao",
            "scoreOutcomes": [
                {"score": "2-0", "probability": 11.7},
                {"score": "3-0", "probability": 10.8},
                {"score": "1-0", "probability": 8.4},
            ],
            "scoreMatrix": [
                {"score": "4-0", "homeGoals": 4, "awayGoals": 0, "probability": 7.2},
            ],
        }

        review = build_post_match_review(fixture, snapshot)

        self.assertEqual(review["status"], "reviewed")
        self.assertEqual(review["actualScore"], "7-1")
        self.assertEqual(review["predictedTopScore"], "2-0")
        self.assertEqual(review["severity"], "high")
        self.assertIn("large_score_tail_underestimated", review["rootCauses"])
        self.assertIn("score_matrix_truncated_tail", review["rootCauses"])
        self.assertIn("expected_goals", review["targetFunctions"])
        self.assertIn("score_distribution_from_lambdas", review["targetFunctions"])
        self.assertIn("score_matrix_for_match", review["targetFunctions"])

    def test_finished_match_records_include_post_match_review_when_snapshot_matches(self):
        records = build_finished_match_records(
            limit=1,
            prediction_snapshot={
                "homeTeam": "germany",
                "awayTeam": "curacao",
                "scoreOutcomes": [{"score": "2-0", "probability": 11.7}],
                "scoreMatrix": [{"score": "4-0", "homeGoals": 4, "awayGoals": 0, "probability": 7.2}],
            },
        )

        self.assertEqual(records["items"][0]["homeTeam"], "germany")
        self.assertEqual(records["items"][0]["awayTeam"], "curacao")
        self.assertEqual(records["items"][0]["postMatchReview"]["severity"], "high")

    def test_et_kickoff_is_parsed_as_eastern_daylight_time(self):
        kickoff = parse_fixture_kickoff("6月15日 12:00 ET")

        self.assertIsNotNone(kickoff)
        self.assertEqual(kickoff.isoformat(), "2026-06-15T16:00:00+00:00")

    def test_scheduled_fixture_after_kickoff_is_not_upcoming(self):
        fixture = Fixture("germany", "curacao", "小组赛 E 组", "6月14日 13:00 ET", "scheduled")
        before_kickoff = parse_fixture_kickoff("6月14日 12:30 ET")
        after_kickoff = parse_fixture_kickoff("6月14日 13:30 ET")

        self.assertTrue(is_fixture_upcoming(fixture, before_kickoff))
        self.assertFalse(is_fixture_upcoming(fixture, after_kickoff))

    def test_expired_configured_current_match_rolls_to_next_upcoming_fixture(self):
        fixture = resolve_current_prediction_fixture(parse_fixture_kickoff("6月15日 00:00 ET"))

        self.assertEqual((fixture.home, fixture.away), ("spain", "cape-verde"))

    def test_dataset_is_loaded_from_local_json_files(self):
        self.assertEqual(DATASET_META["source"], "fifa-official-match-schedule-2026")
        self.assertEqual(len(TEAM_PROFILES), 48)
        self.assertEqual(DATASET_META["placeholderSlots"], 0)
        self.assertFalse(any(team.key.startswith("slot-") for team in TEAM_PROFILES.values()))
        self.assertEqual(len(group_names(TEAM_PROFILES)), 12)
        self.assertTrue(all(len([team for team in TEAM_PROFILES.values() if team.group == group]) == 4 for group in group_names(TEAM_PROFILES)))
        self.assertEqual(len(FIXTURES), 72)
        self.assertTrue(all(fixture.match_no is not None for fixture in FIXTURES))
        self.assertGreaterEqual(len(EVENTS), 7)
        self.assertGreaterEqual(len(RAW_NEWS_ITEMS), 4)

    def test_prediction_exposes_model_transparency_meta(self):
        prediction = build_match_prediction(1200)
        self.assertEqual(prediction["modelMeta"]["dataset"]["source"], "fifa-official-match-schedule-2026")
        self.assertEqual(prediction["modelMeta"]["events"]["watched"], 7)
        self.assertEqual(prediction["modelMeta"]["events"]["applied"], 3)
        self.assertEqual(prediction["modelMeta"]["events"]["ignored"], 2)
        self.assertEqual(prediction["modelMeta"]["events"]["reviewRequired"], 1)
        self.assertEqual(prediction["modelMeta"]["advancedMetrics"]["source"], "verified_layered_inputs")
        self.assertEqual(prediction["modelMeta"]["advancedMetricDataQuality"]["status"], "pass")
        self.assertEqual(prediction["modelMeta"]["historicalEloBlend"]["source"], "cc0_international_results_latest_elo")
        self.assertEqual(prediction["modelMeta"]["eventConfidenceWeights"]["single_source"], 0.45)

    def test_advanced_metrics_cover_all_teams_and_enter_model_meta(self):
        impacts = advanced_metric_impacts()
        prediction = build_match_prediction(1200)

        self.assertEqual(set(impacts), set(TEAM_PROFILES))
        self.assertIn("elo", impacts["brazil"])
        self.assertIn("attack", impacts["brazil"])
        self.assertIn("defense", impacts["brazil"])
        self.assertIn("goalkeeper", impacts["brazil"])
        self.assertIn("squad", impacts["brazil"])
        self.assertEqual(prediction["modelMeta"]["advancedMetricImpacts"]["brazil"]["overall"], impacts["brazil"]["overall"])

    def test_team_factors_use_five_product_plates(self):
        prediction = build_match_prediction(1200)
        first_team = prediction["teams"][0]
        self.assertEqual(set(first_team["factors"]), {"strength", "form", "path", "squad", "margin"})

    def test_champion_change_uses_unadjusted_model_baseline(self):
        prediction = build_match_prediction(1200)
        baseline = simulate_tournament(TEAM_PROFILES, simulation_count=1200)
        first_team = prediction["teams"][0]
        expected_change = round(first_team["tournament"]["champion"] - baseline[first_team["key"]]["champion"], 1)

        self.assertEqual(first_team["tournament"]["change"], expected_change)
        self.assertEqual(prediction["modelMeta"]["changeBaseline"], "unadjusted_model")

    def test_group_ranking_only_uses_teams_from_that_group(self):
        standings = build_standings(FIXTURES)
        ranked = rank_group(standings, "E")
        self.assertEqual({TEAM_PROFILES[key].group for key in ranked}, {"E"})

    def test_best_third_place_selects_eight_teams(self):
        standings = build_standings(FIXTURES)
        third_place = best_third_place_teams(standings, TEAM_PROFILES)
        self.assertEqual(len(third_place), 8)

    def test_annex_c_third_place_table_is_loaded(self):
        self.assertEqual(len(THIRD_PLACE_COMBINATIONS), 495)
        self.assertEqual(
            THIRD_PLACE_COMBINATIONS["EFGHIJKL"],
            {"A": "E", "B": "J", "D": "I", "E": "F", "G": "H", "I": "G", "K": "L", "L": "K"},
        )

    def test_round_of_32_uses_fifa_fixed_slots(self):
        standings = build_standings(FIXTURES)
        rankings = {group: rank_group(standings, group, teams=TEAM_PROFILES) for group in group_names(TEAM_PROFILES)}
        third_place = best_third_place_teams(standings, TEAM_PROFILES, rankings=rankings)
        matches = build_round_of_32_matches(rankings, third_place, TEAM_PROFILES)
        self.assertEqual(matches[73], (rankings["A"][1], rankings["B"][1]))
        self.assertEqual(matches[74][0], rankings["E"][0])
        self.assertEqual(len(matches), 16)
        self.assertEqual(len({team for match in matches.values() for team in match}), 32)
        self.assertEqual(ROUND_OF_16_MATCHES[0], (89, 74, 77))

    def test_tournament_outputs_32_team_path_stages(self):
        teams = apply_event_adjustments()
        result = simulate_tournament(teams, simulation_count=1200)
        self.assertIn("roundOf32", result["brazil"])
        self.assertIn("roundOf16", result["brazil"])
        self.assertIn("quarterfinal", result["brazil"])

    def test_score_sampler_precomputes_cumulative_distribution(self):
        teams = apply_event_adjustments()
        sampler = build_score_sampler("brazil", "argentina", teams)
        self.assertGreater(len(sampler), 0)
        self.assertAlmostEqual(sampler[-1][0], 1.0, places=6)

    def test_expected_goals_can_use_historical_scoring_environment(self):
        teams = apply_event_adjustments()
        default_home, default_away = expected_goals(teams["brazil"], teams["argentina"])
        historical_home, historical_away = expected_goals(
            teams["brazil"],
            teams["argentina"],
            {
                "status": "active",
                "neutralHomeGoalsPerMatch": 1.05,
                "neutralAwayGoalsPerMatch": 0.95,
                "homeGoalsPerMatch": 1.2,
                "awayGoalsPerMatch": 1.0,
            },
        )

        self.assertNotEqual((round(default_home, 3), round(default_away, 3)), (round(historical_home, 3), round(historical_away, 3)))

    def test_expected_goals_expands_high_mismatch_blowout_tail(self):
        teams = apply_event_adjustments()

        home_lambda, away_lambda = expected_goals(teams["germany"], teams["curacao"])

        self.assertGreater(home_lambda, 3.25)
        self.assertLess(away_lambda, 0.9)

    def test_score_matrix_expands_to_seven_goals_for_large_mismatch(self):
        teams = apply_event_adjustments()
        matrix = score_matrix_for_match("germany", "curacao", teams)

        self.assertTrue(any(cell["homeGoals"] == 7 for cell in matrix))

    def test_historical_latest_elo_updates_team_strength_baseline(self):
        history = load_team_match_history()
        teams = apply_event_adjustments()
        static_elo = TEAM_PROFILES["brazil"].elo
        latest_elo = float(history["teams"]["brazil"]["latestElo"])

        self.assertNotEqual(teams["brazil"].elo, static_elo)
        self.assertLess(abs(teams["brazil"].elo - latest_elo), abs(static_elo - latest_elo))

    def test_live_fixture_score_is_used_as_simulation_floor(self):
        teams = apply_event_adjustments()
        fixture = Fixture("brazil", "argentina", "小组赛 E 组", "进行中", "live", 2, 0)
        rng = Random(20260614)

        scores = [sample_fixture_score(fixture, teams, rng) for _ in range(20)]

        self.assertTrue(all(home_score >= 2 for home_score, _ in scores))
        self.assertTrue(all(away_score >= 0 for _, away_score in scores))

    def test_forced_outcome_preserves_live_fixture_score(self):
        fixture = Fixture("brazil", "argentina", "小组赛 E 组", "进行中", "live", 2, 0)

        self.assertEqual(forced_outcome_score(fixture, "home"), (2, 0))
        self.assertEqual(forced_outcome_score(fixture, "draw"), (2, 2))
        self.assertEqual(forced_outcome_score(fixture, "away"), (2, 3))

    def test_events_generate_factor_impact_details(self):
        impacts = event_factor_impacts()
        self.assertLess(impacts["brazil"]["attack"], 0)
        self.assertEqual(impacts["argentina"]["squad"], 0)

    def test_event_confirmation_status_scales_model_impact(self):
        confirmed = TeamEvent("确认伤情", "", "brazil", "B", "attack", -1, 0.05, "now", status="confirmed")
        single_source = TeamEvent("单源伤情", "", "brazil", "B", "attack", -1, 0.05, "now", status="single_source")
        self.assertGreater(event_confidence_weight(confirmed), event_confidence_weight(single_source))

        original_events = model_module.EVENTS
        model_module.EVENTS = [confirmed, single_source]
        try:
            impacts = event_factor_impacts()
        finally:
            model_module.EVENTS = original_events

        self.assertLess(impacts["brazil"]["attack"], -2.0)
        self.assertGreater(impacts["brazil"]["attack"], -4.0)

    def test_public_proxy_news_fields_drive_event_strength(self):
        item = RawNewsItem(
            id="france-defender-public-proxy",
            title="France defender injury doubt before opener",
            summary="France defender trained alone and remains a doubt before kickoff.",
            source="bbc",
            team="france",
            status="multi_source",
            published_at="2026-06-15T09:00:00Z",
            url="https://example.com/france-defender-public-proxy",
            category="injury",
            factor="defense",
            direction=-1,
            confidence=0.92,
            players=["france-defender"],
            kind="rss",
            sourceRegistryId="bbc-football-rss",
        )

        events = events_from_raw_news(
            [item],
            {"bbc": NewsSource("bbc", "BBC Sport Football", "A", "https://www.bbc.com/sport/football")},
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].factor, "defense")
        self.assertEqual(events[0].direction, -1)
        self.assertEqual(events[0].status, "multi_source")
        self.assertGreater(events[0].strength, 0.06)

    def test_fixture_context_detects_short_rest_and_city_change(self):
        fixtures = [
            Fixture(
                "brazil",
                "spain",
                "小组赛 E 组",
                "2026-06-12T08:00:00-05:00",
                "finished",
                1,
                1,
                city="Los Angeles",
                stadium="SoFi Stadium",
            ),
            Fixture(
                "argentina",
                "france",
                "小组赛 E 组",
                "2026-06-10T08:00:00-05:00",
                "finished",
                2,
                0,
                city="Mexico City",
                stadium="Estadio Azteca",
            ),
            Fixture(
                "brazil",
                "argentina",
                "小组赛 E 组",
                "2026-06-15T08:00:00-05:00",
                "scheduled",
                city="Mexico City",
                stadium="Estadio Azteca",
            ),
        ]

        context = build_fixture_context(fixtures[-1], fixtures)

        self.assertEqual(context["home"]["restDays"], 3.0)
        self.assertTrue(context["home"]["cityChange"])
        self.assertLess(context["home"]["impact"], 0)
        self.assertEqual(context["away"]["restDays"], 5.0)
        self.assertFalse(context["away"]["cityChange"])
        self.assertEqual(context["away"]["impact"], 0)

    def test_fixture_context_adjustments_lower_path_and_squad_for_affected_team(self):
        teams = apply_event_adjustments()
        fixture = Fixture("brazil", "argentina", "小组赛 E 组", "2026-06-15T08:00:00-05:00", "scheduled")
        context = {
            "home": {"team": "brazil", "impact": -1.6},
            "away": {"team": "argentina", "impact": 0},
        }

        adjusted = apply_fixture_context_adjustments(teams, fixture, context)

        self.assertEqual(adjusted["brazil"].path, teams["brazil"].path - 2)
        self.assertEqual(adjusted["brazil"].squad, teams["brazil"].squad - 2)
        self.assertEqual(adjusted["argentina"].path, teams["argentina"].path)

    def test_prediction_meta_exposes_fixture_context_plate_impacts(self):
        original_fixtures = model_module.FIXTURES
        original_current_match = model_module.CURRENT_MATCH
        model_module.FIXTURES = [
            Fixture("brazil", "spain", "小组赛 E 组", "2026-06-12T08:00:00-05:00", "finished", 1, 1, city="Los Angeles"),
            Fixture("argentina", "france", "小组赛 E 组", "2026-06-10T08:00:00-05:00", "finished", 2, 0, city="Mexico City"),
            Fixture("brazil", "argentina", "小组赛 E 组", "2026-06-15T08:00:00-05:00", "scheduled", city="Mexico City"),
        ]
        model_module.CURRENT_MATCH = ("brazil", "argentina")
        try:
            prediction = build_match_prediction(1200)
        finally:
            model_module.FIXTURES = original_fixtures
            model_module.CURRENT_MATCH = original_current_match

        impacts = prediction["modelMeta"]["fixtureContextImpacts"]
        self.assertLess(impacts["brazil"]["path"], 0)
        self.assertLess(impacts["brazil"]["squad"], 0)
        self.assertEqual(impacts["argentina"]["path"], 0)

    def test_finished_match_records_lock_real_scores_as_dynamic_inputs(self):
        records = build_finished_match_records(limit=3)

        self.assertEqual(records["count"], 3)
        first = records["items"][0]
        self.assertEqual(first["matchNo"], 10)
        self.assertEqual(first["status"], "finished")
        self.assertEqual(first["homeScore"], 7)
        self.assertEqual(first["awayScore"], 1)
        self.assertEqual(first["modelUse"], "locked_result_weight")
        self.assertIn("后续路径", first["modelUseLabel"])
        self.assertIn("postMatchReview", first)
        third = records["items"][2]
        self.assertEqual(third["homeName"], "海地")
        self.assertEqual(third["homeScore"], 0)
        self.assertEqual(third["awayScore"], 1)
        self.assertEqual(third["awayName"], "苏格兰")

    def test_multi_source_c_level_news_can_enter_reviewed_model_flow(self):
        source = NewsSource(
            key="local-weather",
            name="本地天气观察",
            source_level="C",
            url="https://example.com/weather",
        )
        item = RawNewsItem(
            id="weather-watch",
            title="比赛日高温多源确认",
            summary="官方和本地气象均确认比赛日高温。",
            source="local-weather",
            team="brazil",
            status="multi_source",
            published_at="6 小时前",
            url="https://example.com/weather",
        )
        self.assertEqual(action_for_news_item(item, source), "apply")

    def test_two_c_level_sources_cross_verify_same_event(self):
        sources = {
            "weather-a": NewsSource(
                key="weather-a",
                name="天气观察 A",
                source_level="C",
                url="https://example.com/a",
            ),
            "weather-b": NewsSource(
                key="weather-b",
                name="天气观察 B",
                source_level="C",
                url="https://example.com/b",
            ),
        }
        items = [
            RawNewsItem(
                id="weather-a-heat",
                title="比赛日高温待确认",
                summary="本地天气观察提示巴西比赛日可能高温。",
                source="weather-a",
                team="brazil",
                status="single_source",
                published_at="6 小时前",
                url="https://example.com/a",
            ),
            RawNewsItem(
                id="weather-b-heat",
                title="比赛日高温继续升温",
                summary="另一家本地天气观察也提示巴西比赛日可能高温。",
                source="weather-b",
                team="brazil",
                status="single_source",
                published_at="5 小时前",
                url="https://example.com/b",
            ),
        ]

        events = events_from_raw_news(items, sources)

        self.assertTrue(all(event.status == "multi_source" for event in events))
        self.assertTrue(all(event.action == "apply" for event in events))


if __name__ == "__main__":
    unittest.main()
