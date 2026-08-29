"""Comprehensive unit and regression test suite for production-grade candidate-to-JD matching engine."""

import unittest
from dataclasses import dataclass
from typing import List, Optional

from backend.services.matching_engine import (
    SkillTaxonomy,
    LocationMatcher,
    ExperienceEvaluator,
    NoticePeriodEvaluator,
    MatchingConfig,
    score_candidate,
    ENGINE_VERSION,
    EMBEDDING_MODEL_NAME,
)


# Mock Candidate and JobDescription classes for test isolation
@dataclass
class MockCandidate:
    candidate_id: str = "test-cand-01"
    candidate_code: str = "CAND-001"
    full_name: str = "Test Candidate"
    skills: Optional[List[str]] = None
    total_experience: Optional[float] = None
    notice_period_days: Optional[int] = None
    current_location: Optional[str] = None


@dataclass
class MockJD:
    jd_id: int = 1
    jd_code: str = "JD-001"
    role_title: str = "Software Engineer"
    required_skills: Optional[List[str]] = None
    nice_to_have_skills: Optional[List[str]] = None
    mandatory_skills: Optional[List[str]] = None
    experience_min: Optional[float] = None
    experience_max: Optional[float] = None
    notice_period_days: Optional[int] = None
    location: Optional[str] = None


class TestSkillTaxonomy(unittest.TestCase):
    """1. Skill Taxonomy & Synonym Normalization Tests."""

    def test_skill_synonyms_javascript_and_react(self):
        self.assertTrue(SkillTaxonomy.matches("JavaScript", ["JS", "HTML", "CSS"]))
        self.assertTrue(SkillTaxonomy.matches("JS", ["JavaScript", "TypeScript"]))
        self.assertTrue(SkillTaxonomy.matches("React", ["React.js", "Redux"]))
        self.assertTrue(SkillTaxonomy.matches("React.js", ["ReactJS", "Node.js"]))
        self.assertTrue(SkillTaxonomy.matches("TypeScript", ["TS"]))

    def test_skill_synonyms_backend_and_devops(self):
        self.assertTrue(SkillTaxonomy.matches("Python", ["Py", "FastAPI"]))
        self.assertTrue(SkillTaxonomy.matches("FastAPI", ["Fast API", "Docker"]))
        self.assertTrue(SkillTaxonomy.matches("Kubernetes", ["K8s", "Docker"]))
        self.assertTrue(SkillTaxonomy.matches("Golang", ["Go"]))
        self.assertTrue(SkillTaxonomy.matches("Go", ["Golang"]))
        self.assertTrue(SkillTaxonomy.matches("Node.js", ["NodeJS", "Express"]))
        self.assertTrue(SkillTaxonomy.matches("Amazon Web Services", ["AWS"]))

    def test_skill_sql_database_hierarchical_matching(self):
        self.assertTrue(SkillTaxonomy.matches("SQL", ["PostgreSQL", "Python"]))
        self.assertTrue(SkillTaxonomy.matches("SQL", ["MySQL"]))
        self.assertTrue(SkillTaxonomy.matches("PostgreSQL", ["Postgres", "SQL"]))


class TestFalsePositivePrevention(unittest.TestCase):
    """2. False Positive Prevention Tests (Critical Guardrails)."""

    def test_prevent_java_vs_javascript_false_positive(self):
        """Java must NOT match JavaScript and vice versa."""
        self.assertFalse(SkillTaxonomy.matches("Java", ["JavaScript", "React", "Node"]))
        self.assertFalse(SkillTaxonomy.matches("JavaScript", ["Java", "Spring Boot"]))

    def test_prevent_c_vs_cpp_css_false_positive(self):
        """C must NOT match C++, CSS, or HTML."""
        self.assertFalse(SkillTaxonomy.matches("C", ["CSS", "HTML", "JavaScript"]))
        self.assertFalse(SkillTaxonomy.matches("C", ["C++", "Python"]))
        self.assertTrue(SkillTaxonomy.matches("C", ["C", "Linux"]))
        self.assertTrue(SkillTaxonomy.matches("C++", ["CPP"]))

    def test_prevent_go_vs_django_false_positive(self):
        """Go must NOT match Django or Mongo."""
        self.assertFalse(SkillTaxonomy.matches("Go", ["Django", "Python"]))
        self.assertFalse(SkillTaxonomy.matches("Go", ["MongoDB", "Express"]))
        self.assertTrue(SkillTaxonomy.matches("Go", ["Golang", "Docker"]))

    def test_prevent_r_vs_react_false_positive(self):
        """R statistical language must NOT match React."""
        self.assertFalse(SkillTaxonomy.matches("R", ["React", "Redux"]))
        self.assertFalse(SkillTaxonomy.matches("R", ["Ruby", "Rails"]))


class TestExperienceEvaluation(unittest.TestCase):
    """3. Experience Evaluation Tests."""

    def test_experience_within_bracket(self):
        ratio, note = ExperienceEvaluator.evaluate(candidate_years=4.0, minimum=3.0, maximum=6.0)
        self.assertEqual(ratio, 1.0)
        self.assertIn("Optimal", note)

    def test_experience_under_qualified(self):
        ratio, note = ExperienceEvaluator.evaluate(candidate_years=2.0, minimum=4.0, maximum=8.0)
        self.assertEqual(ratio, 0.50)
        self.assertIn("Under-experienced", note)

    def test_experience_over_qualified_within_grace(self):
        ratio, note = ExperienceEvaluator.evaluate(candidate_years=7.5, minimum=3.0, maximum=6.0, grace_years=2.0)
        self.assertEqual(ratio, 1.0)

    def test_experience_unspecified_requirements(self):
        ratio_no_jd_req, _ = ExperienceEvaluator.evaluate(candidate_years=5.0, minimum=None, maximum=None)
        self.assertEqual(ratio_no_jd_req, 1.0)

        ratio_no_cand_stated, _ = ExperienceEvaluator.evaluate(candidate_years=None, minimum=3.0, maximum=5.0)
        self.assertEqual(ratio_no_cand_stated, 0.25)


class TestNoticePeriodEvaluation(unittest.TestCase):
    """4. Notice Period Evaluation Tests."""

    def test_notice_period_immediate_joiner(self):
        ratio, note = NoticePeriodEvaluator.evaluate(candidate_notice=0, required_notice=30)
        self.assertEqual(ratio, 1.0)
        self.assertIn("Immediate", note)

        ratio_strict_zero, _ = NoticePeriodEvaluator.evaluate(candidate_notice=0, required_notice=0)
        self.assertEqual(ratio_strict_zero, 1.0)

    def test_notice_period_within_cap(self):
        ratio, _ = NoticePeriodEvaluator.evaluate(candidate_notice=15, required_notice=30)
        self.assertEqual(ratio, 1.0)

    def test_notice_period_exceeds_cap(self):
        ratio, note = NoticePeriodEvaluator.evaluate(candidate_notice=60, required_notice=30)
        self.assertEqual(ratio, 0.50)
        self.assertIn("Exceeds", note)

    def test_notice_period_missing(self):
        ratio_cand_none, _ = NoticePeriodEvaluator.evaluate(candidate_notice=None, required_notice=30)
        self.assertEqual(ratio_cand_none, 0.50)

        ratio_jd_none, _ = NoticePeriodEvaluator.evaluate(candidate_notice=45, required_notice=None)
        self.assertEqual(ratio_jd_none, 1.0)


class TestLocationMatching(unittest.TestCase):
    """5. Location & Remote Mode Matching Tests."""

    def test_location_remote_jd_accepts_any_candidate(self):
        self.assertEqual(LocationMatcher.evaluate("Chennai", "Remote / India"), 1.0)
        self.assertEqual(LocationMatcher.evaluate("Kolkata", "WFH - Anywhere in India"), 1.0)
        self.assertEqual(LocationMatcher.evaluate(None, "Remote"), 1.0)

    def test_location_city_aliases(self):
        self.assertEqual(LocationMatcher.evaluate("Bengaluru", "Bangalore"), 1.0)
        self.assertEqual(LocationMatcher.evaluate("BLR", "Bengaluru, Karnataka"), 1.0)
        self.assertEqual(LocationMatcher.evaluate("Madras", "Chennai"), 1.0)
        self.assertEqual(LocationMatcher.evaluate("Gurgaon", "Delhi NCR / Noida"), 1.0)
        self.assertEqual(LocationMatcher.evaluate("Gurugram", "Delhi"), 1.0)
        self.assertEqual(LocationMatcher.evaluate("Bombay", "Mumbai"), 1.0)

    def test_location_mismatch(self):
        self.assertEqual(LocationMatcher.evaluate("Chennai", "Pune, Maharashtra"), 0.0)
        self.assertEqual(LocationMatcher.evaluate("Hyderabad", "Kolkata"), 0.0)


class TestMandatoryRequirementsAndEligibility(unittest.TestCase):
    """6. Hard Mandatory Requirements vs Normal Required Skills Tests."""

    def test_hard_mandatory_skill_missing_disqualifies_candidate(self):
        """Missing a hard mandatory skill makes candidate ineligible (is_eligible=False, score=0.0)."""
        cand = MockCandidate(
            skills=["JavaScript", "React", "CSS"],
            total_experience=5.0,
            notice_period_days=15,
            current_location="Chennai",
        )
        # JD specifies Python as hard mandatory via '*' prefix
        jd = MockJD(
            required_skills=["*Python", "React"],
            experience_min=3.0,
            notice_period_days=30,
            location="Chennai",
        )

        score = score_candidate(cand, jd, semantic_relevance=0.70)
        self.assertFalse(score.is_eligible)
        self.assertEqual(score.total, 0.0)
        self.assertIn("Ineligible", score.explanation)
        self.assertIn("Python", score.breakdown["missing_mandatory_skills"])

    def test_hard_mandatory_skill_present_qualifies_candidate(self):
        """Meeting the hard mandatory skill keeps candidate eligible."""
        cand = MockCandidate(
            skills=["Python", "FastAPI"],
            total_experience=4.0,
            notice_period_days=15,
            current_location="Chennai",
        )
        jd = MockJD(
            required_skills=["*Python", "Docker"],
            experience_min=3.0,
            notice_period_days=30,
            location="Chennai",
        )

        score = score_candidate(cand, jd, semantic_relevance=0.80)
        self.assertTrue(score.is_eligible)
        self.assertGreater(score.total, 60.0)

    def test_normal_required_skills_shortfall_penalizes_without_disqualifying(self):
        """Missing normal required skills applies a score penalty rather than hard disqualification."""
        cand = MockCandidate(
            skills=["Marketing", "Excel", "Sales"],
            total_experience=6.0,
            notice_period_days=10,
            current_location="Chennai",
        )
        jd = MockJD(
            required_skills=["Python", "FastAPI", "Kubernetes", "PostgreSQL"],
            experience_min=3.0,
            experience_max=6.0,
            notice_period_days=30,
            location="Chennai",
        )

        score = score_candidate(cand, jd, semantic_relevance=0.10)
        self.assertTrue(score.is_eligible)  # Still eligible, but penalized
        self.assertLess(score.total, 55.0)
        self.assertGreater(score.breakdown["mandatory_penalty_applied"], 0)
        self.assertIn("Penalty", score.explanation)

    def test_hard_mandatory_missing_disqualifies_even_with_perfect_secondary_factors(self):
        """Even with 100% experience, immediate notice, and exact location, missing a mandatory skill zeroes score."""
        cand = MockCandidate(
            skills=["Python", "Django", "PostgreSQL"],
            total_experience=5.0,  # 100% exp
            notice_period_days=0,   # 100% notice (immediate)
            current_location="Bengaluru",  # 100% loc
        )
        jd = MockJD(
            required_skills=["*Kubernetes", "Python"],
            experience_min=3.0,
            notice_period_days=30,
            location="Bengaluru",
        )

        score = score_candidate(cand, jd, semantic_relevance=0.95)
        self.assertFalse(score.is_eligible)
        self.assertEqual(score.total, 0.0)
        self.assertEqual(score.skills, 0.0)
        self.assertEqual(score.experience, 0.0)
        self.assertEqual(score.notice_period, 0.0)
        self.assertEqual(score.location, 0.0)
        self.assertIn("Ineligible", score.explanation)

    def test_skill_deduplication_between_required_and_nice_to_have(self):
        """A skill appearing in both required and nice-to-have must not be double counted."""
        cand = MockCandidate(
            skills=["Python", "FastAPI"],
            total_experience=4.0,
            notice_period_days=15,
            current_location="Chennai",
        )
        jd = MockJD(
            required_skills=["Python", "FastAPI"],
            nice_to_have_skills=["Python", "Py", "AWS"],  # Python and Py overlap with required
            experience_min=3.0,
            notice_period_days=30,
            location="Chennai",
        )

        score = score_candidate(cand, jd, semantic_relevance=0.50)
        # Python/Py should be filtered out from clean_nice_to_have; only AWS remains
        # Candidate does not have AWS, so nice_to_have_ratio should be 0.0
        self.assertEqual(score.breakdown["nice_to_have_ratio"], 0.0)
        self.assertEqual(score.breakdown["matched_nice_to_have_skills"], [])

    def test_nice_to_have_provides_strictly_bounded_bonus(self):
        """Nice to have skills provide a controlled bonus and never artificially exceed maximum bounds."""
        cand_with_bonus = MockCandidate(
            skills=["Python", "FastAPI", "Docker", "AWS"],
            total_experience=4.0,
            notice_period_days=15,
            current_location="Chennai",
        )
        cand_without_bonus = MockCandidate(
            skills=["Python", "FastAPI"],
            total_experience=4.0,
            notice_period_days=15,
            current_location="Chennai",
        )
        jd = MockJD(
            required_skills=["Python", "FastAPI"],
            nice_to_have_skills=["Docker", "AWS"],
            experience_min=3.0,
            notice_period_days=30,
            location="Chennai",
        )

        score_bonus = score_candidate(cand_with_bonus, jd, semantic_relevance=0.80)
        score_base = score_candidate(cand_without_bonus, jd, semantic_relevance=0.80)

        self.assertGreaterEqual(score_bonus.skills, score_base.skills)
        self.assertLessEqual(score_bonus.skills, 40.0)
        self.assertEqual(score_bonus.breakdown["nice_to_have_ratio"], 1.0)
        self.assertIn("Docker", score_bonus.breakdown["matched_nice_to_have_skills"])


class TestScoringIntegrationAndRegressions(unittest.TestCase):
    """7. End-to-End Scoring & Regression Tests."""

    def test_score_candidate_full_match(self):
        cand = MockCandidate(
            skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            total_experience=5.0,
            notice_period_days=15,
            current_location="Bengaluru",
        )
        jd = MockJD(
            required_skills=["Python", "FastAPI", "SQL"],
            nice_to_have_skills=["Docker"],
            experience_min=3.0,
            experience_max=6.0,
            notice_period_days=30,
            location="Bangalore",
        )

        score = score_candidate(cand, jd, semantic_relevance=0.90)
        self.assertTrue(score.is_eligible)
        self.assertGreaterEqual(score.total, 90.0)
        self.assertGreaterEqual(score.skills, 35.0)
        self.assertEqual(score.experience, 25.0)
        self.assertEqual(score.notice_period, 20.0)
        self.assertEqual(score.location, 15.0)
        self.assertIn("Python", score.explanation)
        self.assertEqual(score.audit["engine_version"], ENGINE_VERSION)
        self.assertEqual(score.audit["embedding_model"], EMBEDDING_MODEL_NAME)

    def test_backward_compatibility_positional_args(self):
        """Ensure original function call signature (candidate, jd, relevance, w_skills...) still functions."""
        cand = MockCandidate(skills=["Python"], total_experience=3.0, notice_period_days=15, current_location="Chennai")
        jd = MockJD(required_skills=["Python"], experience_min=2.0, notice_period_days=30, location="Chennai")

        # Calling with legacy positional weights
        score = score_candidate(cand, jd, 0.75, 40.0, 25.0, 20.0, 15.0)
        self.assertTrue(isinstance(score.total, float))
        self.assertTrue(isinstance(score.explanation, str))
        self.assertGreater(score.total, 80.0)

    def test_custom_configurable_weights(self):
        cand = MockCandidate(
            skills=["Python", "FastAPI"],
            total_experience=2.0,  # 50% exp
            notice_period_days=30,
            current_location="Chennai",
        )
        jd = MockJD(
            required_skills=["Python", "FastAPI"],
            experience_min=4.0,
            notice_period_days=30,
            location="Chennai",
        )

        config = MatchingConfig(
            w_skills=70.0,
            w_experience=10.0,
            w_notice=10.0,
            w_location=10.0,
            semantic_weight_in_skills=0.0,
        )

        score = score_candidate(cand, jd, semantic_relevance=0.5, config=config)
        self.assertEqual(score.skills, 70.0)
        self.assertEqual(score.experience, 5.0)
        self.assertEqual(score.total, 95.0)


if __name__ == "__main__":
    unittest.main()
