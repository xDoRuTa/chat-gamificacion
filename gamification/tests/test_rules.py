"""Tests de las reglas de dominio. Ejecutar dentro del contenedor:

    docker compose exec gamification python -m unittest discover -s tests -v
"""
import unittest

from app import rules


class LevelTests(unittest.TestCase):
    def test_level_thresholds(self):
        self.assertEqual(rules.level_for_xp(0), 1)
        self.assertEqual(rules.level_for_xp(24), 1)
        self.assertEqual(rules.level_for_xp(25), 2)
        self.assertEqual(rules.level_for_xp(99), 2)
        self.assertEqual(rules.level_for_xp(100), 3)
        self.assertEqual(rules.level_for_xp(400), 5)

    def test_xp_for_level_matches_level_for_xp(self):
        for level in range(1, 20):
            self.assertEqual(rules.level_for_xp(rules.xp_for_level(level)), level)
            self.assertEqual(rules.level_for_xp(rules.xp_for_level(level + 1) - 1), level)

    def test_three_messages_reach_level_two(self):
        self.assertEqual(rules.level_for_xp(3 * rules.XP_PER_MESSAGE), 2)


class AchievementTests(unittest.TestCase):
    def test_first_message_unlocks(self):
        codes = [a.code for a in rules.newly_unlocked({"messages_sent": 1})]
        self.assertEqual(codes, ["primer_mensaje"])

    def test_owned_achievements_are_not_repeated(self):
        profile = {"messages_sent": 5, "achievements": [{"code": "primer_mensaje"}]}
        self.assertEqual(rules.newly_unlocked(profile), [])

    def test_reaction_and_level_achievements(self):
        profile = {"reactions_received": 100, "level": 5}
        codes = {a.code for a in rules.newly_unlocked(profile)}
        self.assertEqual(codes, {"primera_reaccion", "cien_reacciones", "nivel_5"})


if __name__ == "__main__":
    unittest.main()
